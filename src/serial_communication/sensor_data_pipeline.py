#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
传感器数据采集Pipeline
文件名: sensor_data_pipeline.py
版本: v1.0
创建时间: 2026-04-13
描述: 完整的传感器数据采集、处理、存储Pipeline

功能:
1. 多传感器数据实时采集
2. 数据滤波与平滑处理
3. 数据标准化与异常检测
4. 实时可视化
5. 数据持久化
"""

import sys
import os
import time
import json
import threading
import statistics
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Arduino'))

from arduino_simulator import ArduinoSimulator


class DataQuality(Enum):
    """数据质量等级"""
    EXCELLENT = "excellent"  # 波动<5%
    GOOD = "good"            # 波动<10%
    FAIR = "fair"            # 波动<20%
    POOR = "poor"            # 波动>=20%


@dataclass
class ProcessedData:
    """处理后的传感器数据"""
    # 原始值
    raw: Dict[str, float]
    
    # 滤波后值
    filtered: Dict[str, float]
    
    # 统计信息
    stats: Dict[str, Dict[str, float]]
    
    # 质量等级
    quality: DataQuality
    
    # 时间戳
    timestamp: float
    
    # 异常标记
    anomalies: List[str]


class MovingAverageFilter:
    """移动平均滤波器"""
    
    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.buffers: Dict[str, deque] = {}
    
    def add(self, sensor_id: str, value: float) -> float:
        """添加值并返回滤波结果"""
        if sensor_id not in self.buffers:
            self.buffers[sensor_id] = deque(maxlen=self.window_size)
        
        self.buffers[sensor_id].append(value)
        
        if len(self.buffers[sensor_id]) < 2:
            return value
        
        return sum(self.buffers[sensor_id]) / len(self.buffers[sensor_id])
    
    def reset(self, sensor_id: Optional[str] = None):
        """重置滤波器"""
        if sensor_id:
            if sensor_id in self.buffers:
                self.buffers[sensor_id].clear()
        else:
            self.buffers.clear()
    
    def get_buffer_size(self, sensor_id: str) -> int:
        """获取缓冲区大小"""
        return len(self.buffers.get(sensor_id, []))


class KalmanFilter:
    """简单卡尔曼滤波器（用于单变量）"""
    
    def __init__(self, process_noise: float = 0.1, measurement_noise: float = 1.0):
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise
        self.estimate = 0.0
        self.error_covariance = 1.0
        self.initialized = False
    
    def update(self, measurement: float) -> float:
        """更新估计值"""
        if not self.initialized:
            self.estimate = measurement
            self.initialized = True
            return measurement
        
        # 预测步骤
        predicted_estimate = self.estimate
        predicted_error_covariance = self.error_covariance + self.process_noise
        
        # 更新步骤
        kalman_gain = predicted_error_covariance / (predicted_error_covariance + self.measurement_noise)
        self.estimate = predicted_estimate + kalman_gain * (measurement - predicted_estimate)
        self.error_covariance = (1 - kalman_gain) * predicted_error_covariance
        
        return self.estimate
    
    def reset(self):
        """重置滤波器"""
        self.estimate = 0.0
        self.error_covariance = 1.0
        self.initialized = False


class AnomalyDetector:
    """异常检测器"""
    
    def __init__(self, 
                 z_score_threshold: float = 3.0,
                 delta_threshold: float = 10.0):
        self.z_score_threshold = z_score_threshold
        self.delta_threshold = delta_threshold
        self.history: Dict[str, List[float]] = {}
        self.baseline: Dict[str, float] = {}
    
    def add_baseline(self, sensor_id: str, value: float):
        """添加基线值"""
        if sensor_id not in self.history:
            self.history[sensor_id] = []
            self.baseline[sensor_id] = value
        else:
            self.history[sensor_id].append(value)
            
            # 保持历史记录在合理范围
            if len(self.history[sensor_id]) > 100:
                self.history[sensor_id].pop(0)
    
    def detect(self, sensor_id: str, value: float) -> List[str]:
        """检测异常"""
        anomalies = []
        
        if sensor_id not in self.baseline:
            self.baseline[sensor_id] = value
            return anomalies
        
        # 计算与基线的差异
        delta = abs(value - self.baseline[sensor_id])
        if delta > self.delta_threshold:
            anomalies.append(f"{sensor_id}: delta={delta:.2f}超过阈值")
        
        # Z-score检测
        if len(self.history.get(sensor_id, [])) >= 10:
            mean = statistics.mean(self.history[sensor_id])
            stdev = statistics.stdev(self.history[sensor_id])
            
            if stdev > 0:
                z_score = abs(value - mean) / stdev
                if z_score > self.z_score_threshold:
                    anomalies.append(f"{sensor_id}: z_score={z_score:.2f}超过阈值")
        
        return anomalies


class DataQualityAnalyzer:
    """数据质量分析器"""
    
    def __init__(self, window_size: int = 20):
        self.window_size = window_size
        self.data_buffers: Dict[str, deque] = {}
    
    def analyze(self, sensor_id: str, values: List[float]) -> DataQuality:
        """分析数据质量"""
        if len(values) < 5:
            return DataQuality.GOOD
        
        mean = statistics.mean(values)
        
        if mean == 0:
            return DataQuality.GOOD
        
        # 计算变异系数(CV)
        stdev = statistics.stdev(values) if len(values) > 1 else 0
        cv = abs(stdev / mean)
        
        if cv < 0.05:
            return DataQuality.EXCELLENT
        elif cv < 0.10:
            return DataQuality.GOOD
        elif cv < 0.20:
            return DataQuality.FAIR
        else:
            return DataQuality.POOR
    
    def add_data(self, sensor_id: str, value: float):
        """添加数据"""
        if sensor_id not in self.data_buffers:
            self.data_buffers[sensor_id] = deque(maxlen=self.window_size)
        
        self.data_buffers[sensor_id].append(value)


class SensorDataPipeline:
    """
    传感器数据采集Pipeline
    
    功能:
    1. 多传感器数据实时采集
    2. 移动平均滤波
    3. 卡尔曼滤波
    4. 异常检测
    5. 数据质量评估
    6. 数据持久化
    """
    
    def __init__(self,
                 arduino_simulator: Optional[ArduinoSimulator] = None,
                 sample_interval: float = 1.0,
                 use_kalman: bool = True):
        """
        初始化Pipeline
        
        参数:
            arduino_simulator: Arduino模拟器实例
            sample_interval: 采样间隔(秒)
            use_kalman: 是否使用卡尔曼滤波
        """
        self.simulator = arduino_simulator
        self.sample_interval = sample_interval
        self.use_kalman = use_kalman
        
        # 滤波器
        self.moving_avg = MovingAverageFilter(window_size=5)
        self.kalman_filters: Dict[str, KalmanFilter] = {}
        self.anomaly_detector = AnomalyDetector()
        self.quality_analyzer = DataQualityAnalyzer()
        
        # 数据缓冲
        self.data_buffer: deque = deque(maxlen=1000)
        
        # 控制
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # 回调
        self.data_callback: Optional[Callable[[ProcessedData], None]] = None
        self.anomaly_callback: Optional[Callable[[str, float, List[str]], None]] = None
        
        # 统计
        self.stats = {
            "samples_processed": 0,
            "anomalies_detected": 0,
            "quality_excellent": 0,
            "quality_good": 0,
            "quality_fair": 0,
            "quality_poor": 0
        }
    
    def _get_kalman_filter(self, sensor_id: str) -> KalmanFilter:
        """获取或创建卡尔曼滤波器"""
        if sensor_id not in self.kalman_filters:
            self.kalman_filters[sensor_id] = KalmanFilter()
        return self.kalman_filters[sensor_id]
    
    def _process_sensor_data(self, raw_data: Dict[str, float]) -> ProcessedData:
        """处理传感器数据"""
        timestamp = time.time()
        
        # 移动平均滤波
        filtered = {}
        for sensor_id, value in raw_data.items():
            ma_value = self.moving_avg.add(sensor_id, value)
            
            if self.use_kalman:
                kalman_value = self._get_kalman_filter(sensor_id).update(ma_value)
                filtered[sensor_id] = kalman_value
            else:
                filtered[sensor_id] = ma_value
            
            # 添加到质量分析器
            self.quality_analyzer.add_data(sensor_id, value)
            
            # 添加到异常检测器
            self.anomaly_detector.add_baseline(sensor_id, value)
        
        # 计算统计信息
        stats = {}
        for sensor_id in raw_data.keys():
            values = list(self.quality_analyzer.data_buffers.get(sensor_id, []))
            if len(values) >= 2:
                stats[sensor_id] = {
                    "mean": statistics.mean(values),
                    "stdev": statistics.stdev(values),
                    "min": min(values),
                    "max": max(values),
                    "cv": statistics.stdev(values) / statistics.mean(values) if statistics.mean(values) != 0 else 0
                }
        
        # 异常检测
        anomalies = []
        for sensor_id, value in filtered.items():
            sensor_anomalies = self.anomaly_detector.detect(sensor_id, value)
            anomalies.extend(sensor_anomalies)
            
            if sensor_anomalies and self.anomaly_callback:
                self.anomaly_callback(sensor_id, value, sensor_anomalies)
        
        # 数据质量评估
        all_values = list(self.quality_analyzer.data_buffers.values())
        if all_values:
            quality = self.quality_analyzer.analyze("all", [v for buf in all_values for v in buf])
        else:
            quality = DataQuality.GOOD
        
        # 更新统计
        self.stats["samples_processed"] += 1
        if anomalies:
            self.stats["anomalies_detected"] += len(anomalies)
        
        quality_counts = {
            DataQuality.EXCELLENT: "quality_excellent",
            DataQuality.GOOD: "quality_good",
            DataQuality.FAIR: "quality_fair",
            DataQuality.POOR: "quality_poor"
        }
        self.stats[quality_counts[quality]] += 1
        
        return ProcessedData(
            raw=raw_data,
            filtered=filtered,
            stats=stats,
            quality=quality,
            timestamp=timestamp,
            anomalies=anomalies
        )
    
    def _collection_loop(self):
        """数据采集循环"""
        last_sample_time = 0
        
        while self._running:
            current_time = time.time()
            
            if current_time - last_sample_time >= self.sample_interval:
                # 获取传感器数据
                if self.simulator:
                    raw_data = self.simulator.get_sensor_data()
                else:
                    # 模拟数据
                    raw_data = {
                        "temp_dht": 25.0 + (hash(str(current_time)) % 100) / 50,
                        "temp_bmp": 25.2 + (hash(str(current_time+1)) % 100) / 50,
                        "humidity": 60.0 + (hash(str(current_time+2)) % 100) / 20,
                        "pressure": 1013.25 + (hash(str(current_time+3)) % 100) / 10,
                        "distance": 100 + (hash(str(current_time+4)) % 200),
                        "light": 500 + (hash(str(current_time+5)) % 500)
                    }
                
                # 处理数据
                processed = self._process_sensor_data(raw_data)
                
                # 存储到缓冲
                self.data_buffer.append(processed)
                
                # 触发回调
                if self.data_callback:
                    self.data_callback(processed)
                
                last_sample_time = current_time
            
            time.sleep(0.01)
    
    def start(self):
        """启动Pipeline"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._collection_loop, daemon=True)
        self._thread.start()
        print("传感器数据Pipeline已启动")
    
    def stop(self):
        """停止Pipeline"""
        self._running = False
        
        if self._thread:
            self._thread.join(timeout=2.0)
        
        print("传感器数据Pipeline已停止")
    
    def on_data(self, callback: Callable[[ProcessedData], None]):
        """设置数据回调"""
        self.data_callback = callback
    
    def on_anomaly(self, callback: Callable[[str, float, List[str]], None]):
        """设置异常回调"""
        self.anomaly_callback = callback
    
    def get_latest(self, count: int = 10) -> List[ProcessedData]:
        """获取最新的N条数据"""
        return list(self.data_buffer)[-count:]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats.copy()
    
    def export_data(self, filepath: str, format: str = "json"):
        """导出数据"""
        data_list = []
        
        for processed in self.data_buffer:
            data_list.append({
                "timestamp": processed.timestamp,
                "datetime": datetime.fromtimestamp(processed.timestamp).isoformat(),
                "raw": processed.raw,
                "filtered": processed.filtered,
                "stats": processed.stats,
                "quality": processed.quality.value,
                "anomalies": processed.anomalies
            })
        
        with open(filepath, 'w') as f:
            if format == "json":
                json.dump(data_list, f, indent=2)
            elif format == "csv":
                # CSV格式
                if not data_list:
                    return
                
                headers = ["timestamp", "datetime", "quality"] + \
                          [f"raw_{k}" for k in data_list[0]["raw"].keys()] + \
                          [f"filtered_{k}" for k in data_list[0]["filtered"].keys()]
                
                f.write(",".join(headers) + "\n")
                
                for data in data_list:
                    row = [
                        str(data["timestamp"]),
                        data["datetime"],
                        data["quality"]
                    ] + [str(data["raw"].get(k, "")) for k in data_list[0]["raw"].keys()] + \
                        [str(data["filtered"].get(k, "")) for k in data_list[0]["filtered"].keys()]
                    f.write(",".join(row) + "\n")
        
        print(f"数据已导出到: {filepath}")


def console_display_demo():
    """控制台显示演示"""
    print("\n" + "="*60)
    print("传感器数据采集Pipeline演示")
    print("="*60)
    
    # 初始化
    sim = ArduinoSimulator(sensor_interval=1.0, noise_level=0.1)
    pipeline = SensorDataPipeline(
        arduino_simulator=sim,
        sample_interval=1.0,
        use_kalman=True
    )
    
    # 统计计数
    sample_count = 0
    
    # 设置回调
    def on_data(processed: ProcessedData):
        nonlocal sample_count
        sample_count += 1
        
        print(f"\n[{sample_count}] 传感器数据 ({datetime.now().strftime('%H:%M:%S')})")
        print("-" * 50)
        
        # 显示滤波后数据
        print("滤波后数据:")
        for sensor_id, value in processed.filtered.items():
            quality_icon = {
                DataQuality.EXCELLENT: "🟢",
                DataQuality.GOOD: "🔵",
                DataQuality.FAIR: "🟡",
                DataQuality.POOR: "🔴"
            }.get(processed.quality, "⚪")
            print(f"  {sensor_id:12s}: {value:8.2f} {quality_icon}")
        
        # 显示质量
        print(f"数据质量: {processed.quality.value}")
        
        # 显示异常
        if processed.anomalies:
            print(f"⚠️ 异常: {', '.join(processed.anomalies)}")
        
        # 显示统计
        if processed.stats:
            print("统计:")
            for sensor_id, stat in processed.stats.items():
                print(f"  {sensor_id}: μ={stat['mean']:.2f}, σ={stat['stdev']:.2f}")
    
    def on_anomaly(sensor_id: str, value: float, anomalies: List[str]):
        print(f"\n🚨 异常检测 [{sensor_id}]: value={value:.2f}")
        for anomaly in anomalies:
            print(f"   {anomaly}")
    
    pipeline.on_data(on_data)
    pipeline.on_anomaly(on_anomaly)
    
    # 启动
    sim.start()
    pipeline.start()
    
    print("\n开始采集数据 (按Ctrl+C停止)...")
    
    try:
        while sample_count < 20:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n正在停止...")
    finally:
        pipeline.stop()
        sim.stop()
        
        # 显示统计
        print("\n" + "="*60)
        print("采集统计")
        print("="*60)
        stats = pipeline.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # 导出数据
        output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_path = os.path.join(output_dir, f'sensor_data_{timestamp}.json')
        pipeline.export_data(json_path, format='json')
        
        print("\n演示完成!")


if __name__ == "__main__":
    console_display_demo()
