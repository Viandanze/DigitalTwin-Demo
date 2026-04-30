#!/usr/bin/env python3
"""
传感器模拟器模块
功能：生成模拟传感器数据，支持多传感器类型、可控噪声和异常注入
作者：数字孪生学习项目
日期：2026年4月3日
"""

import time
import random
import threading
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SensorSimulator:
    """多传感器数据模拟器"""
    
    def __init__(self, sensor_config: Dict):
        """初始化传感器模拟器
        
        Args:
            sensor_config: 传感器配置字典
        """
        self.config = sensor_config
        self.sensors = {}
        self.current_data = {}
        self.last_update_time = {}
        self.running = False
        self.simulation_thread = None
        
        self._initialize_sensors()
        logger.info(f"传感器模拟器初始化完成，共 {len(self.sensors)} 个传感器")
    
    def _initialize_sensors(self):
        """根据配置初始化各传感器"""
        for sensor_name, config in self.config.items():
            sensor_type = config.get('type', 'generic')
            
            # 根据传感器类型创建不同的模拟器
            if sensor_type == 'temperature':
                self.sensors[sensor_name] = TemperatureSensor(config)
            elif sensor_type == 'humidity':
                self.sensors[sensor_name] = HumiditySensor(config)
            elif sensor_type == 'distance':
                self.sensors[sensor_name] = DistanceSensor(config)
            elif sensor_type == 'light':
                self.sensors[sensor_name] = LightSensor(config)
            elif sensor_type == 'pressure':
                self.sensors[sensor_name] = PressureSensor(config)
            else:
                self.sensors[sensor_name] = GenericSensor(config)
    
    def start(self):
        """启动传感器数据更新线程"""
        if self.running:
            return
        
        logger.info("启动传感器模拟器...")
        self.running = True
        self.simulation_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.simulation_thread.start()
    
    def stop(self):
        """停止传感器数据更新"""
        logger.info("停止传感器模拟器...")
        self.running = False
        if self.simulation_thread:
            self.simulation_thread.join(timeout=2.0)
    
    def _update_loop(self):
        """传感器数据更新循环"""
        logger.info("传感器数据更新循环启动")
        
        while self.running:
            try:
                # 更新每个传感器的数据
                for sensor_name, sensor in self.sensors.items():
                    update_interval = self.config.get(sensor_name, {}).get('update_interval', 1.0)
                    
                    # 检查是否需要更新
                    current_time = time.time()
                    last_time = self.last_update_time.get(sensor_name, 0)
                    
                    if current_time - last_time >= update_interval:
                        # 生成新数据
                        new_value = sensor.generate_data()
                        self.current_data[sensor_name] = new_value
                        self.last_update_time[sensor_name] = current_time
                
                # 短暂休眠
                time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"传感器更新循环错误: {e}")
                time.sleep(1.0)
        
        logger.info("传感器数据更新循环结束")
    
    def get_current_data(self) -> Dict:
        """获取当前所有传感器数据
        
        Returns:
            传感器数据字典 {传感器名: 值}
        """
        # 如果模拟器未启动，立即生成数据
        if not self.running:
            for sensor_name, sensor in self.sensors.items():
                self.current_data[sensor_name] = sensor.generate_data()
        
        return self.current_data.copy()
    
    def get_sensor_data(self, sensor_name: str) -> Optional[float]:
        """获取指定传感器数据
        
        Args:
            sensor_name: 传感器名称
            
        Returns:
            传感器值，如果传感器不存在返回None
        """
        return self.current_data.get(sensor_name)
    
    def inject_anomaly(self, sensor_name: str, anomaly_type: str = 'spike', magnitude: float = None):
        """向指定传感器注入异常
        
        Args:
            sensor_name: 传感器名称
            anomaly_type: 异常类型 ('spike', 'drift', 'noise', 'stuck')
            magnitude: 异常幅度（可选）
        """
        if sensor_name not in self.sensors:
            logger.warning(f"传感器 {sensor_name} 不存在")
            return
        
        sensor = self.sensors[sensor_name]
        sensor.inject_anomaly(anomaly_type, magnitude)
        logger.info(f"向传感器 {sensor_name} 注入 {anomaly_type} 异常")
    
    def get_sensor_status(self) -> Dict:
        """获取所有传感器状态
        
        Returns:
            传感器状态字典
        """
        status = {}
        for sensor_name, sensor in self.sensors.items():
            status[sensor_name] = {
                'type': sensor.__class__.__name__,
                'config': sensor.config,
                'has_anomaly': sensor.has_anomaly,
                'last_value': self.current_data.get(sensor_name)
            }
        
        return status

# 基础传感器类
class BaseSensor:
    """传感器基类"""
    
    def __init__(self, config: Dict):
        """初始化传感器
        
        Args:
            config: 传感器配置
        """
        self.config = config
        self.value_range = config.get('range', [0.0, 100.0])
        self.unit = config.get('unit', '')
        self.update_interval = config.get('update_interval', 1.0)
        self.noise_level = config.get('noise_level', 0.05)  # 5%噪声
        self.has_anomaly = False
        self.anomaly_type = None
        self.anomaly_magnitude = 0.0
        self.base_value = np.mean(self.value_range)
        self.trend_direction = random.choice([-1, 1])
        self.trend_rate = random.uniform(0.01, 0.05)
        
        # 模拟真实传感器的特性
        self.response_time = config.get('response_time', 0.1)
        self.hysteresis = config.get('hysteresis', 0.02)
        self.calibration_error = config.get('calibration_error', 0.01)
        
        # 历史数据用于趋势分析
        self.history = []
        self.max_history = 100
    
    def generate_data(self) -> float:
        """生成传感器数据
        
        Returns:
            传感器值
        """
        # 基础值加上趋势变化
        trend_change = self.trend_direction * self.trend_rate * random.random()
        self.base_value += trend_change
        
        # 确保在合理范围内
        if self.base_value < self.value_range[0]:
            self.base_value = self.value_range[0]
            self.trend_direction = 1  # 反转趋势方向
        elif self.base_value > self.value_range[1]:
            self.base_value = self.value_range[1]
            self.trend_direction = -1
        
        # 添加随机噪声
        noise = random.gauss(0, self.noise_level * (self.value_range[1] - self.value_range[0]))
        
        # 计算最终值
        value = self.base_value + noise
        
        # 添加传感器特性
        value = self._apply_sensor_characteristics(value)
        
        # 应用异常（如果有）
        if self.has_anomaly:
            value = self._apply_anomaly(value)
        
        # 记录历史
        self.history.append(value)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        return round(value, 2)
    
    def _apply_sensor_characteristics(self, value: float) -> float:
        """应用传感器特性（响应时间、迟滞等）
        
        Args:
            value: 原始值
            
        Returns:
            处理后的值
        """
        # 简化实现：添加一些随机波动
        if self.history:
            last_value = self.history[-1]
            # 模拟响应时间：不能突变
            max_change = (self.value_range[1] - self.value_range[0]) * self.response_time
            change = value - last_value
            if abs(change) > max_change:
                value = last_value + np.sign(change) * max_change
        
        # 添加校准误差
        value *= (1 + random.uniform(-self.calibration_error, self.calibration_error))
        
        return value
    
    def _apply_anomaly(self, value: float) -> float:
        """应用异常
        
        Args:
            value: 正常值
            
        Returns:
            异常值
        """
        if self.anomaly_type == 'spike':
            # 尖峰异常：突然的大幅变化
            spike = self.anomaly_magnitude * random.choice([-1, 1])
            return value + spike
        
        elif self.anomaly_type == 'drift':
            # 漂移异常：持续的小幅变化
            drift = self.anomaly_magnitude * random.random()
            return value + drift
        
        elif self.anomaly_type == 'noise':
            # 噪声异常：增加噪声水平
            extra_noise = random.gauss(0, self.anomaly_magnitude)
            return value + extra_noise
        
        elif self.anomaly_type == 'stuck':
            # 卡死异常：值不再变化
            if self.history:
                return self.history[-1]
            return value
        
        else:
            return value
    
    def inject_anomaly(self, anomaly_type: str, magnitude: float = None):
        """注入异常
        
        Args:
            anomaly_type: 异常类型
            magnitude: 异常幅度（可选）
        """
        self.has_anomaly = True
        self.anomaly_type = anomaly_type
        
        if magnitude is None:
            # 根据传感器范围自动设置幅度
            range_size = self.value_range[1] - self.value_range[0]
            if anomaly_type == 'spike':
                self.anomaly_magnitude = range_size * 0.5  # 50%范围
            elif anomaly_type == 'drift':
                self.anomaly_magnitude = range_size * 0.05  # 5%范围
            elif anomaly_type == 'noise':
                self.anomaly_magnitude = range_size * 0.1  # 10%范围
            else:
                self.anomaly_magnitude = 0.0
        else:
            self.anomaly_magnitude = magnitude
    
    def clear_anomaly(self):
        """清除异常"""
        self.has_anomaly = False
        self.anomaly_type = None
        self.anomaly_magnitude = 0.0

# 具体传感器实现
class TemperatureSensor(BaseSensor):
    """温度传感器模拟器"""
    
    def __init__(self, config: Dict):
        default_config = {
            'range': [15.0, 35.0],
            'unit': '℃',
            'update_interval': 2.0,
            'noise_level': 0.03,
            'response_time': 0.2,  # 温度响应较慢
            'calibration_error': 0.02
        }
        config = {**default_config, **config}
        super().__init__(config)
        
        # 温度特定参数
        self.diurnal_variation = config.get('diurnal_variation', True)
        self.day_temperature = np.mean([self.value_range[0], self.value_range[1]])
        self.night_temperature = self.day_temperature - 5.0
    
    def generate_data(self) -> float:
        """生成温度数据，考虑昼夜变化"""
        current_hour = datetime.now().hour
        
        if self.diurnal_variation:
            # 模拟昼夜温度变化（简单正弦波）
            hour_rad = (current_hour / 24.0) * 2 * np.pi
            diurnal_variation = 5.0 * np.sin(hour_rad - np.pi/2)  # 峰值在下午2点
            
            # 调整基础值
            temp_base = self.base_value + diurnal_variation
        else:
            temp_base = self.base_value
        
        # 添加随机波动
        fluctuation = random.gauss(0, self.noise_level * 5.0)
        value = temp_base + fluctuation
        
        # 确保在合理范围内
        value = max(self.value_range[0], min(self.value_range[1], value))
        
        # 记录历史
        self.history.append(value)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        return round(value, 1)

class HumiditySensor(BaseSensor):
    """湿度传感器模拟器"""
    
    def __init__(self, config: Dict):
        default_config = {
            'range': [30.0, 90.0],
            'unit': '%',
            'update_interval': 2.0,
            'noise_level': 0.02,
            'response_time': 0.3,  # 湿度响应较慢
            'hysteresis': 0.05     # 湿度迟滞较明显
        }
        config = {**default_config, **config}
        super().__init__(config)
        
        # 湿度与温度的相关性
        self.temperature_influence = config.get('temperature_influence', 0.1)
    
    def generate_data(self) -> float:
        """生成湿度数据，考虑温度影响"""
        # 模拟湿度随温度变化（负相关）
        temp_factor = random.uniform(-0.5, 0.5)
        humidity_base = self.base_value + temp_factor * self.temperature_influence * 10
        
        # 添加随机噪声
        noise = random.gauss(0, self.noise_level * (self.value_range[1] - self.value_range[0]))
        value = humidity_base + noise
        
        # 确保在合理范围内
        value = max(self.value_range[0], min(self.value_range[1], value))
        
        # 记录历史
        self.history.append(value)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        return round(value, 1)

class DistanceSensor(BaseSensor):
    """超声波距离传感器模拟器"""
    
    def __init__(self, config: Dict):
        default_config = {
            'range': [5.0, 45.0],
            'unit': 'cm',
            'update_interval': 1.0,
            'noise_level': 0.05,
            'response_time': 0.05,  # 快速响应
            'temperature_compensation': True  # 温度补偿
        }
        config = {**default_config, **config}
        super().__init__(config)
        
        # 距离特定参数
        self.object_present = True  # 默认有物体
        self.object_moving = False
        self.move_speed = 0.0
    
    def generate_data(self) -> float:
        """生成距离数据"""
        if not self.object_present:
            # 无物体时返回最大距离
            return self.value_range[1]
        
        # 基础距离
        distance_base = self.base_value
        
        # 模拟物体移动
        if self.object_moving and self.move_speed > 0:
            movement = self.move_speed * random.random()
            distance_base += movement * random.choice([-1, 1])
        
        # 添加测量噪声（超声波特性）
        measurement_noise = random.gauss(0, self.noise_level * distance_base)
        value = distance_base + measurement_noise
        
        # 确保在有效范围内
        value = max(self.value_range[0], min(self.value_range[1], value))
        
        # 记录历史
        self.history.append(value)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        return round(value, 2)
    
    def set_object_state(self, present: bool, moving: bool = False, speed: float = 0.0):
        """设置物体状态
        
        Args:
            present: 物体是否存在
            moving: 物体是否移动
            speed: 移动速度（单位/秒）
        """
        self.object_present = present
        self.object_moving = moving
        self.move_speed = speed

class LightSensor(BaseSensor):
    """光照传感器模拟器"""
    
    def __init__(self, config: Dict):
        default_config = {
            'range': [0.0, 100.0],
            'unit': '%',
            'update_interval': 0.5,
            'noise_level': 0.03,
            'response_time': 0.1,
            'diurnal_pattern': True  # 昼夜模式
        }
        config = {**default_config, **config}
        super().__init__(config)
        
        # 光照特定参数
        self.sunrise_hour = 6
        self.sunset_hour = 18
        self.max_intensity = self.value_range[1]
    
    def generate_data(self) -> float:
        """生成光照数据，考虑昼夜模式"""
        current_hour = datetime.now().hour
        current_minute = datetime.now().minute
        time_decimal = current_hour + current_minute / 60.0
        
        if self.config.get('diurnal_pattern', True):
            # 模拟日出日落的光照变化
            if time_decimal < self.sunrise_hour or time_decimal > self.sunset_hour:
                # 夜间：低光照
                light_base = random.uniform(0, 10)
            elif time_decimal < self.sunrise_hour + 2:
                # 日出时段：逐渐增强
                progress = (time_decimal - self.sunrise_hour) / 2.0
                light_base = 10 + progress * 70
            elif time_decimal > self.sunset_hour - 2:
                # 日落时段：逐渐减弱
                progress = (self.sunset_hour - time_decimal) / 2.0
                light_base = 10 + progress * 70
            else:
                # 白天：高光照，有波动
                light_base = 80 + random.uniform(-10, 10)
        else:
            light_base = self.base_value
        
        # 添加随机变化
        variation = random.gauss(0, self.noise_level * 20)
        value = light_base + variation
        
        # 确保在合理范围内
        value = max(self.value_range[0], min(self.value_range[1], value))
        
        # 记录历史
        self.history.append(value)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        return round(value, 1)

class PressureSensor(BaseSensor):
    """气压传感器模拟器"""
    
    def __init__(self, config: Dict):
        default_config = {
            'range': [950.0, 1050.0],
            'unit': 'hPa',
            'update_interval': 1.0,
            'noise_level': 0.01,  # 气压相对稳定
            'response_time': 0.15,
            'weather_influence': True  # 天气影响
        }
        config = {**default_config, **config}
        super().__init__(config)
        
        # 气压特定参数
        self.weather_trend = random.choice(['rising', 'falling', 'stable'])
        self.trend_strength = random.uniform(0.1, 0.5)
    
    def generate_data(self) -> float:
        """生成气压数据，考虑天气趋势"""
        # 基础气压
        pressure_base = self.base_value
        
        # 添加天气趋势
        if self.weather_trend == 'rising':
            trend_change = random.uniform(0, self.trend_strength)
        elif self.weather_trend == 'falling':
            trend_change = random.uniform(-self.trend_strength, 0)
        else:  # stable
            trend_change = random.uniform(-self.trend_strength/2, self.trend_strength/2)
        
        pressure_base += trend_change
        
        # 添加测量噪声
        noise = random.gauss(0, self.noise_level * 5)
        value = pressure_base + noise
        
        # 确保在合理范围内
        value = max(self.value_range[0], min(self.value_range[1], value))
        
        # 记录历史
        self.history.append(value)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        return round(value, 2)

class GenericSensor(BaseSensor):
    """通用传感器模拟器"""
    
    def __init__(self, config: Dict):
        super().__init__(config)

# 测试函数
def test_sensor_simulator():
    """测试传感器模拟器"""
    print("测试传感器模拟器...")
    
    # 创建配置
    sensor_config = {
        'temperature': {
            'type': 'temperature',
            'range': [15.0, 35.0],
            'unit': '℃',
            'update_interval': 2.0
        },
        'humidity': {
            'type': 'humidity',
            'range': [30.0, 90.0],
            'unit': '%',
            'update_interval': 2.0
        },
        'distance': {
            'type': 'distance',
            'range': [5.0, 45.0],
            'unit': 'cm',
            'update_interval': 1.0
        }
    }
    
    # 创建模拟器
    simulator = SensorSimulator(sensor_config)
    
    # 启动模拟器
    simulator.start()
    
    try:
        # 测试数据获取
        for i in range(5):
            data = simulator.get_current_data()
            print(f"第{i+1}次数据: {data}")
            time.sleep(2)
        
        # 测试异常注入
        print("\n注入尖峰异常...")
        simulator.inject_anomaly('temperature', 'spike', 10.0)
        time.sleep(2)
        data = simulator.get_current_data()
        print(f"异常后数据: {data}")
        
    finally:
        # 停止模拟器
        simulator.stop()

if __name__ == "__main__":
    test_sensor_simulator()