#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arduino数字孪生模拟器
文件名: arduino_simulator.py
版本: v1.0
创建时间: 2026-04-12
描述: 在没有硬件的情况下模拟Arduino行为，用于测试上位机代码
"""

import time
import random
import threading
import json
from collections import deque
from typing import Callable, Optional, Dict, Any, List
from dataclasses import dataclass, asdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SimulatedSensorData:
    """模拟传感器数据"""
    humidity: float = 55.0
    temp_dht: float = 25.0
    temp_bmp: float = 25.2
    pressure: float = 1013.25
    distance: int = 50
    light: int = 512
    current: int = 0
    uptime: int = 0


class ArduinoSimulator:
    """
    Arduino模拟器 - 模拟真实Arduino的行为
    
    功能：
    1. 模拟传感器数据（可配置噪声和趋势）
    2. 响应上位机指令
    3. 模拟执行器状态
    4. 支持多种故障场景模拟
    """
    
    def __init__(self,
                 sensor_interval: float = 1.0,
                 noise_level: float = 0.05,
                 enable_trends: bool = True):
        """
        初始化模拟器
        
        参数：
            sensor_interval: 传感器采样间隔（秒）
            noise_level: 噪声级别（0-1）
            enable_trends: 是否启用数据趋势
        """
        self.sensor_interval = sensor_interval
        self.noise_level = noise_level
        self.enable_trends = enable_trends
        
        # 模拟状态
        self.start_time = time.time()
        self.sensor_data = SimulatedSensorData()
        
        # 执行器状态
        self.motor_speed = 0
        self.motor_direction = 0
        self.servo_angle = 90
        self.emergency_stop = False
        self.safety_enabled = True
        
        # 校准偏移
        self.calib = {
            'temp': 0.0,
            'humidity': 0.0,
            'pressure': 0.0,
            'distance': 0.0,
            'light': 0.0
        }
        
        # 滤波器
        self.filter_buffer: deque = deque(maxlen=5)
        
        # 回调和数据队列
        self._running = False
        self._output_callback: Optional[Callable[[str], None]] = None
        self._input_queue: List[str] = []
        self._lock = threading.Lock()
        
        # 数据趋势参数
        self._trend_params = {
            'temp': {'base': 25.0, 'amplitude': 2.0, 'period': 60},
            'humidity': {'base': 55.0, 'amplitude': 10.0, 'period': 120},
            'distance': {'base': 50.0, 'amplitude': 10.0, 'period': 30},
            'light': {'base': 512, 'amplitude': 200, 'period': 45}
        }
        
        # 故障模拟
        self.fault_mode: Optional[str] = None
        self.fault_start_time: float = 0
        
        logger.info("Arduino模拟器初始化完成")
    
    def set_output_callback(self, callback: Callable[[str], None]):
        """设置输出回调（模拟串口输出）"""
        self._output_callback = callback
    
    def send_input(self, data: str):
        """模拟接收到上位机数据"""
        with self._lock:
            self._input_queue.append(data)
    
    def start(self):
        """启动模拟器"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        # 发送启动消息
        self._send_output({
            'type': 'system',
            'msg': 'Arduino Digital Twin Firmware Ready',
            'version': 'v2.0-sim'
        })
        
        logger.info("Arduino模拟器已启动")
    
    def stop(self):
        """停止模拟器"""
        self._running = False
        if hasattr(self, '_thread'):
            self._thread.join(timeout=2)
        logger.info("Arduino模拟器已停止")
    
    def _run_loop(self):
        """主模拟循环"""
        last_sensor_read = time.time()
        
        while self._running:
            current_time = time.time()
            
            # 传感器采样
            if current_time - last_sensor_read >= self.sensor_interval:
                last_sensor_read = current_time
                self._update_sensors()
                self._send_sensor_data()
            
            # 处理输入指令
            self._process_inputs()
            
            # 安全检查
            if self.safety_enabled:
                self._check_safety()
            
            time.sleep(0.01)
    
    def _update_sensors(self):
        """更新模拟传感器数据"""
        elapsed = time.time() - self.start_time
        
        # 生成带趋势和噪声的数据
        for sensor, params in self._trend_params.items():
            if self.enable_trends:
                trend = params['amplitude'] * (0.5 - 0.5 * (elapsed / params['period'] % 1))
            else:
                trend = 0
            
            noise = (random.random() - 0.5) * 2 * self.noise_level * params['amplitude']
            value = params['base'] + trend + noise
            
            if sensor == 'temp':
                self.sensor_data.temp_dht = value + self.calib['temp']
            elif sensor == 'humidity':
                self.sensor_data.humidity = max(0, min(100, value + self.calib['humidity']))
            elif sensor == 'distance':
                self.sensor_data.distance = max(2, int(value + self.calib['distance']))
            elif sensor == 'light':
                self.sensor_data.light = max(0, min(1023, int(value + self.calib['light'])))
        
        # BMP280温度（略高于DHT11）
        self.sensor_data.temp_bmp = self.sensor_data.temp_dht + 0.3 + self.calib['temp']
        
        # 气压（变化缓慢）
        pressure_noise = random.gauss(0, 0.5)
        self.sensor_data.pressure = 1013.25 + pressure_noise + self.calib['pressure']
        
        # 电流（根据电机状态）
        if self.motor_speed > 0:
            self.sensor_data.current = int(self.motor_speed * 10 + random.gauss(0, 50))
        else:
            self.sensor_data.current = random.randint(10, 50)
        
        # 运行时间
        self.sensor_data.uptime = int((time.time() - self.start_time) * 1000)
    
    def _send_sensor_data(self):
        """发送传感器数据"""
        data = {
            'type': 'sensor',
            'humidity': round(self.sensor_data.humidity, 1),
            'temp_dht': round(self.sensor_data.temp_dht, 1),
            'temp_bmp': round(self.sensor_data.temp_bmp, 1),
            'pressure': round(self.sensor_data.pressure, 1),
            'distance': self.sensor_data.distance,
            'light': self.sensor_data.light,
            'current': self.sensor_data.current,
            'uptime': self.sensor_data.uptime
        }
        self._send_output(data)
    
    def _process_inputs(self):
        """处理输入指令"""
        with self._lock:
            inputs = self._input_queue.copy()
            self._input_queue.clear()
        
        for cmd in inputs:
            self._handle_command(cmd.strip())
    
    def _handle_command(self, cmd: str):
        """处理单条指令"""
        cmd = cmd.upper()
        
        # PING
        if cmd == 'PING':
            self._send_output({
                'type': 'pong',
                'timestamp': self.sensor_data.uptime
            })
            return
        
        # GET_STATUS
        if cmd == 'GET_STATUS':
            self._send_output({
                'type': 'status',
                'motor': {
                    'speed': self.motor_speed,
                    'direction': self.motor_direction
                },
                'servo': {'angle': self.servo_angle},
                'safety': {
                    'enabled': self.safety_enabled,
                    'emergency': self.emergency_stop
                },
                'calib': self.calib,
                'uptime': self.sensor_data.uptime
            })
            return
        
        # STOP_ALL
        if cmd == 'STOP_ALL':
            self.emergency_stop = True
            self.motor_speed = 0
            self.motor_direction = 0
            self.servo_angle = 90
            self._send_output({'type': 'action', 'result': 'STOP_ALL_OK'})
            return
        
        # RESUME
        if cmd == 'RESUME':
            self.emergency_stop = False
            self._send_output({'type': 'action', 'result': 'RESUME_OK'})
            return
        
        # SET_MOTOR
        if cmd.startswith('SET_MOTOR'):
            if self.emergency_stop:
                self._send_output({'type': 'error', 'reason': 'EMERGENCY_STOP_ACTIVE'})
                return
            
            parts = cmd.split()
            if len(parts) >= 3:
                speed = max(0, min(255, int(parts[1])))
                direction = max(0, min(2, int(parts[2])))
                
                self.motor_speed = speed
                self.motor_direction = direction
                
                self._send_output({
                    'type': 'motor',
                    'speed': speed,
                    'direction': direction
                })
            return
        
        # SET_SERVO
        if cmd.startswith('SET_SERVO'):
            if self.emergency_stop:
                self._send_output({'type': 'error', 'reason': 'EMERGENCY_STOP_ACTIVE'})
                return
            
            parts = cmd.split()
            if len(parts) >= 2:
                angle = max(0, min(180, int(parts[1])))
                self.servo_angle = angle
                self._send_output({
                    'type': 'servo',
                    'angle': angle
                })
            return
        
        # CALIB_SET
        if cmd.startswith('CALIB_SET'):
            parts = cmd.split()
            if len(parts) >= 3:
                sensor = parts[1].lower()
                value = float(parts[2])
                
                if sensor in self.calib:
                    self.calib[sensor] = value
                    self._send_output({
                        'type': 'calib',
                        'sensor': sensor.upper(),
                        'offset': value
                    })
            return
        
        # CALIB_RESET
        if cmd == 'CALIB_RESET':
            for key in self.calib:
                self.calib[key] = 0.0
            self._send_output({'type': 'calib', 'action': 'RESET'})
            return
        
        # FILTER_RESET
        if cmd == 'FILTER_RESET':
            self._send_output({'type': 'filter', 'action': 'RESET'})
            return
        
        # SAFETY_ON/OFF
        if cmd == 'SAFETY_ON':
            self.safety_enabled = True
            self._send_output({'type': 'safety', 'enabled': True})
            return
        if cmd == 'SAFETY_OFF':
            self.safety_enabled = False
            self._send_output({'type': 'safety', 'enabled': False})
            return
        
        # GET_INFO
        if cmd == 'GET_INFO':
            self._send_output({
                'type': 'system',
                'version': 'v2.0-sim',
                'build': '2026-04-12',
                'uptime': self.sensor_data.uptime,
                'filter_window': 5
            })
            return
        
        # 未知指令
        self._send_output({
            'type': 'error',
            'cmd': 'UNKNOWN',
            'received': cmd
        })
    
    def _check_safety(self):
        """安全检查"""
        # 温度超限
        if self.sensor_data.temp_dht > 60 or self.sensor_data.temp_dht < -10:
            self._send_output({
                'type': 'safety',
                'level': 'WARNING',
                'reason': 'TEMP_OUT_OF_RANGE',
                'temp': self.sensor_data.temp_dht
            })
        
        # 电流超限
        if self.sensor_data.current > 2000:
            self._send_output({
                'type': 'safety',
                'level': 'CRITICAL',
                'reason': 'CURRENT_OVERLOAD',
                'current': self.sensor_data.current
            })
            # 停止电机
            self.motor_speed = 0
            self.motor_direction = 0
            self._send_output({'type': 'safety', 'action': 'MOTOR_EMERGENCY_STOP'})
    
    def _send_output(self, data: dict):
        """发送输出数据"""
        json_str = json.dumps(data)
        logger.debug(f"模拟器输出: {json_str}")
        
        if self._output_callback:
            self._output_callback(json_str)
    
    # ========== 故障模拟方法 ==========
    
    def enable_fault(self, fault_type: str):
        """
        启用故障模拟
        
        fault_type:
            - 'sensor_dropout': 传感器数据丢失
            - 'random_spike': 随机数据突变
            - 'comm_lag': 通信延迟
            - 'actuator_jam': 执行器卡滞
        """
        self.fault_mode = fault_type
        self.fault_start_time = time.time()
        logger.warning(f"启用故障模拟: {fault_type}")
    
    def disable_fault(self):
        """禁用故障模拟"""
        self.fault_mode = None
        logger.info("故障模拟已禁用")
    
    # ========== 状态查询方法 ==========
    
    def get_status(self) -> Dict[str, Any]:
        """获取模拟器状态"""
        return {
            'running': self._running,
            'motor': {
                'speed': self.motor_speed,
                'direction': self.motor_direction
            },
            'servo_angle': self.servo_angle,
            'emergency_stop': self.emergency_stop,
            'safety_enabled': self.safety_enabled,
            'calib': self.calib.copy(),
            'uptime_sec': int(time.time() - self.start_time),
            'fault_mode': self.fault_mode
        }
    
    def set_sensor_value(self, sensor: str, value: float):
        """手动设置传感器值（用于测试）"""
        if sensor in self._trend_params:
            self._trend_params[sensor]['base'] = value


# ============================================================================
# 测试程序
# ============================================================================

def run_test():
    """运行模拟器测试"""
    print("=" * 60)
    print("Arduino数字孪生模拟器测试")
    print("=" * 60)
    
    # 创建模拟器
    sim = ArduinoSimulator(
        sensor_interval=1.0,
        noise_level=0.1,
        enable_trends=True
    )
    
    # 打印回调
    def on_output(data: str):
        print(f"[Arduino] {data}")
    
    sim.set_output_callback(on_output)
    
    # 启动
    sim.start()
    print("\n模拟器已启动，等待3秒...\n")
    time.sleep(3)
    
    # 测试指令
    test_commands = [
        'PING',
        'GET_STATUS',
        'GET_INFO',
        'SET_MOTOR 128 1',
        'SET_SERVO 45',
        'GET_STATUS',
        'STOP_ALL',
        'CALIB_SET TEMP 1.5',
        'CALIB_READ',
        'SAFETY_OFF',
        'RESUME',
    ]
    
    print("\n" + "-" * 60)
    print("发送测试指令:")
    print("-" * 60)
    
    for cmd in test_commands:
        print(f">>> {cmd}")
        sim.send_input(cmd)
        time.sleep(0.5)
    
    # 运行一段时间
    print("\n" + "-" * 60)
    print("持续运行10秒，观察传感器数据...")
    print("-" * 60 + "\n")
    time.sleep(10)
    
    # 打印状态
    print("\n" + "=" * 60)
    print("模拟器最终状态:")
    print("=" * 60)
    status = sim.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    # 停止
    print("\n停止模拟器...")
    sim.stop()
    print("测试完成!")


if __name__ == '__main__':
    run_test()
