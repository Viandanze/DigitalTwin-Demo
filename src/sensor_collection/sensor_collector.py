#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数字孪生传感器采集模块
文件名: sensor_collector.py
版本: v1.0
创建时间: 2026-04-11
描述: 整合Arduino固件接口，提供传感器数据的高层抽象
      支持数据缓存、异常检测、统计分析
"""

import time
import threading
from collections import deque
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
import statistics
import json
import logging

from arduino_bridge import ArduinoBridge, SensorData, ActuatorState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SensorStats:
    """传感器统计信息"""
    count: int = 0
    min_val: float = float('inf')
    max_val: float = float('-inf')
    mean_val: float = 0.0
    std_val: float = 0.0
    last_update: float = 0.0
    
    def update(self, value: float):
        """更新统计"""
        self.count += 1
        self.min_val = min(self.min_val, value)
        self.max_val = max(self.max_val, value)
        
        if self.count > 1:
            self.mean_val = (self.mean_val * (self.count - 1) + value) / self.count
        else:
            self.mean_val = value
        
        self.last_update = time.time()
    
    def reset(self):
        """重置统计"""
        self.count = 0
        self.min_val = float('inf')
        self.max_val = float('-inf')
        self.mean_val = 0.0
        self.std_val = 0.0
        self.last_update = 0.0


class SensorCollector:
    """
    传感器数据采集器
    
    功能：
    1. 管理Arduino连接和通信
    2. 实时数据缓存（滑动窗口）
    3. 异常值检测
    4. 统计分析
    5. 数据导出
    """
    
    # 缓存配置
    DEFAULT_BUFFER_SIZE = 100      # 默认缓存大小
    STATS_WINDOW_SIZE = 50        # 统计窗口大小
    
    # 异常检测阈值
    OUTLIER_THRESHOLD_STD = 3.0   # 标准差倍数阈值
    
    def __init__(self,
                 port: Optional[str] = None,
                 baud_rate: int = 115200,
                 buffer_size: int = DEFAULT_BUFFER_SIZE):
        """
        初始化采集器
        
        参数：
            port: 串口路径，None则自动检测
            baud_rate: 波特率
            buffer_size: 环形缓冲区大小
        """
        self.bridge = ArduinoBridge(port=port, baud_rate=baud_rate, auto_detect=True)
        self.buffer_size = buffer_size
        
        # 数据缓冲
        self._data_buffer: deque = deque(maxlen=buffer_size)
        self._buffer_lock = threading.Lock()
        
        # 统计信息
        self._stats: Dict[str, SensorStats] = {
            "humidity": SensorStats(),
            "temp_dht": SensorStats(),
            "temp_bmp": SensorStats(),
            "pressure": SensorStats(),
            "distance": SensorStats(),
            "light": SensorStats()
        }
        self._stats_lock = threading.Lock()
        
        # 异常检测
        self._outlier_threshold = self.OUTLIER_THRESHOLD_STD
        self._recent_values: Dict[str, deque] = {
            key: deque(maxlen=self.STATS_WINDOW_SIZE)
            for key in self._stats.keys()
        }
        
        # 回调
        self._callbacks: List[Callable[[SensorData], None]] = []
        
        # 运行状态
        self._running = False
        self._collection_thread: Optional[threading.Thread] = None
        
        # 启动时间
        self._start_time = 0.0
    
    # =========================================================================
    # 连接管理
    # =========================================================================
    
    def connect(self) -> bool:
        """连接到Arduino"""
        success = self.bridge.connect()
        
        if success:
            # 设置数据回调
            self.bridge.on_sensor_data(self._on_sensor_data)
            self.bridge.on_error(self._on_error)
            
            # 请求初始状态
            self.bridge.get_status()
        
        return success
    
    def disconnect(self):
        """断开连接"""
        self.stop_collection()
        self.bridge.disconnect()
    
    def is_connected(self) -> bool:
        """是否已连接"""
        return self.bridge.is_connected
    
    # =========================================================================
    # 数据采集控制
    # =========================================================================
    
    def start_collection(self):
        """启动数据采集"""
        if self._running:
            logger.warning("数据采集已在运行")
            return
        
        self._running = True
        self._start_time = time.time()
        
        self._collection_thread = threading.Thread(
            target=self._collection_loop,
            daemon=True
        )
        self._collection_thread.start()
        
        logger.info("启动数据采集")
    
    def stop_collection(self):
        """停止数据采集"""
        self._running = False
        
        if self._collection_thread and self._collection_thread.is_alive():
            self._collection_thread.join(timeout=2.0)
        
        logger.info("停止数据采集")
    
    def _collection_loop(self):
        """采集主循环（定期请求状态）"""
        while self._running and self.is_connected():
            self.bridge.get_status()
            time.sleep(5.0)  # 每5秒请求一次状态
    
    # =========================================================================
    # 数据处理
    # =========================================================================
    
    def _on_sensor_data(self, data: SensorData):
        """处理传感器数据"""
        # 更新缓冲
        with self._buffer_lock:
            self._data_buffer.append(data)
        
        # 更新统计
        self._update_stats(data)
        
        # 调用回调
        for callback in self._callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"回调执行错误: {e}")
    
    def _on_error(self, error_msg: str):
        """处理错误"""
        logger.error(f"Arduino错误: {error_msg}")
    
    def _update_stats(self, data: SensorData):
        """更新统计信息"""
        values = data.to_dict()
        
        with self._stats_lock:
            for key, value in values.items():
                if key == "timestamp":
                    continue
                
                if not isinstance(value, (int, float)) or value < 0:
                    continue
                
                # 更新统计
                if key in self._stats:
                    self._stats[key].update(float(value))
                
                # 更新历史值
                if key in self._recent_values:
                    self._recent_values[key].append(float(value))
    
    def _is_outlier(self, key: str, value: float) -> bool:
        """检测异常值"""
        if key not in self._recent_values:
            return False
        
        history = list(self._recent_values[key])
        if len(history) < 10:
            return False
        
        mean = statistics.mean(history)
        stdev = statistics.stdev(history)
        
        if stdev == 0:
            return False
        
        z_score = abs(value - mean) / stdev
        return z_score > self._outlier_threshold
    
    # =========================================================================
    # 数据访问
    # =========================================================================
    
    def get_latest(self) -> Optional[SensorData]:
        """获取最新数据"""
        with self._buffer_lock:
            if len(self._data_buffer) > 0:
                return self._data_buffer[-1]
        return None
    
    def get_buffer(self, count: Optional[int] = None) -> List[SensorData]:
        """
        获取缓冲数据
        
        参数：
            count: 返回数量，None则返回全部
            
        返回：
            传感器数据列表
        """
        with self._buffer_lock:
            data_list = list(self._data_buffer)
        
        if count is not None:
            return data_list[-count:]
        return data_list
    
    def get_stats(self, sensor: str) -> Optional[SensorStats]:
        """获取传感器统计"""
        with self._stats_lock:
            return self._stats.get(sensor)
    
    def get_all_stats(self) -> Dict[str, SensorStats]:
        """获取所有统计"""
        with self._stats_lock:
            return self._stats.copy()
    
    def get_actuator_state(self) -> ActuatorState:
        """获取执行器状态"""
        return self.bridge.get_actuator_state()
    
    # =========================================================================
    # 执行器控制
    # =========================================================================
    
    def set_motor(self, speed: int, direction: int) -> bool:
        """设置电机"""
        return self.bridge.set_motor(speed, direction)
    
    def set_servo(self, angle: int) -> bool:
        """设置舵机"""
        return self.bridge.set_servo(angle)
    
    # =========================================================================
    # 回调管理
    # =========================================================================
    
    def add_callback(self, callback: Callable[[SensorData], None]):
        """添加数据回调"""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[SensorData], None]):
        """移除回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    # =========================================================================
    # 数据导出
    # =========================================================================
    
    def export_json(self, filepath: str, count: Optional[int] = None):
        """
        导出数据为JSON
        
        参数：
            filepath: 文件路径
            count: 导出数量，None则导出全部
        """
        data_list = self.get_buffer(count)
        
        export_data = {
            "export_time": datetime.now().isoformat(),
            "start_time": datetime.fromtimestamp(self._start_time).isoformat(),
            "record_count": len(data_list),
            "data": [d.to_dict() for d in data_list]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"导出{len(data_list)}条记录到 {filepath}")
    
    def export_csv(self, filepath: str, count: Optional[int] = None):
        """
        导出数据为CSV
        
        参数：
            filepath: 文件路径
            count: 导出数量，None则导出全部
        """
        data_list = self.get_buffer(count)
        
        headers = ["timestamp", "humidity", "temp_dht", "temp_bmp", 
                   "pressure", "distance", "light"]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(",".join(headers) + "\n")
            
            for data in data_list:
                row = [
                    str(data.timestamp),
                    str(data.humidity),
                    str(data.temp_dht),
                    str(data.temp_bmp),
                    str(data.pressure),
                    str(data.distance),
                    str(data.light)
                ]
                f.write(",".join(row) + "\n")
        
        logger.info(f"导出{len(data_list)}条记录到 {filepath}")
    
    # =========================================================================
    # 上下文管理
    # =========================================================================
    
    def __enter__(self):
        self.connect()
        self.start_collection()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False
    
    def __repr__(self) -> str:
        return f"SensorCollector(buffer={len(self._data_buffer)}/{self.buffer_size})"


# ============================================================================
# 使用示例
# ============================================================================

def example_basic():
    """基础使用示例"""
    with SensorCollector() as collector:
        if not collector.is_connected():
            print("连接失败!")
            return
        
        # 添加自定义回调
        def on_data(data: SensorData):
            # 过滤异常值
            if data.temp_dht > 0:
                print(f"温度: {data.temp_dht:.1f}°C, 湿度: {data.humidity:.1f}%")
        
        collector.add_callback(on_data)
        
        # 采集30秒
        print("开始采集30秒...")
        time.sleep(30)
        
        # 导出数据
        collector.export_json("sensor_data.json")
        
        # 打印统计
        stats = collector.get_all_stats()
        print("\n统计信息:")
        for name, stat in stats.items():
            if stat.count > 0:
                print(f"  {name}: min={stat.min_val:.1f}, max={stat.max_val:.1f}, avg={stat.mean_val:.1f}")


def example_control():
    """执行器控制示例"""
    with SensorCollector() as collector:
        if not collector.is_connected():
            print("连接失败!")
            return
        
        # 测试电机
        print("测试电机...")
        collector.set_motor(100, 1)  # 半速正转
        time.sleep(2)
        collector.set_motor(0, 0)    # 停止
        
        # 测试舵机
        print("测试舵机...")
        collector.set_servo(90)     # 居中
        time.sleep(1)
        collector.set_servo(0)      # 左转
        time.sleep(1)
        collector.set_servo(180)    # 右转
        time.sleep(1)
        collector.set_servo(90)     # 回到居中
        
        print("执行器测试完成")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "control":
            example_control()
        else:
            example_basic()
    else:
        example_basic()
