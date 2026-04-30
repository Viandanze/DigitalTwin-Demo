#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数字孪生系统集成测试
文件名: integration_test.py
版本: v1.0
创建时间: 2026-04-12
描述: 使用模拟器测试整个数字孪生系统的完整功能
"""

import sys
import time
import unittest
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from arduino_simulator import ArduinoSimulator
from arduino_bridge import ArduinoBridge, SensorData
from sensor_collector import SensorCollector


class TestArduinoSimulator(unittest.TestCase):
    """Arduino模拟器测试"""
    
    def setUp(self):
        self.sim = ArduinoSimulator(sensor_interval=0.1, noise_level=0.01)
        self.output_data = []
        self.sim.set_output_callback(lambda d: self.output_data.append(d))
    
    def tearDown(self):
        self.sim.stop()
    
    def test_startup(self):
        """测试启动"""
        self.sim.start()
        time.sleep(0.5)
        
        # 应该收到系统消息
        system_msgs = [d for d in self.output_data if '"type":"system"' in d]
        self.assertGreater(len(system_msgs), 0)
        print("✓ 启动测试通过")
    
    def test_ping(self):
        """测试心跳"""
        self.sim.start()
        time.sleep(0.3)
        
        self.sim.send_input('PING')
        time.sleep(0.2)
        
        pong_msgs = [d for d in self.output_data if '"type":"pong"' in d]
        self.assertGreater(len(pong_msgs), 0)
        print("✓ PING测试通过")
    
    def test_motor_control(self):
        """测试电机控制"""
        self.sim.start()
        time.sleep(0.3)
        
        self.sim.send_input('SET_MOTOR 128 1')
        time.sleep(0.2)
        
        motor_msgs = [d for d in self.output_data if '"type":"motor"' in d]
        self.assertGreater(len(motor_msgs), 0)
        
        status = self.sim.get_status()
        self.assertEqual(status['motor']['speed'], 128)
        self.assertEqual(status['motor']['direction'], 1)
        print("✓ 电机控制测试通过")
    
    def test_servo_control(self):
        """测试舵机控制"""
        self.sim.start()
        time.sleep(0.3)
        
        self.sim.send_input('SET_SERVO 90')
        time.sleep(0.2)
        
        servo_msgs = [d for d in self.output_data if '"type":"servo"' in d]
        self.assertGreater(len(servo_msgs), 0)
        
        status = self.sim.get_status()
        self.assertEqual(status['servo_angle'], 90)
        print("✓ 舵机控制测试通过")
    
    def test_emergency_stop(self):
        """测试紧急停止"""
        self.sim.start()
        time.sleep(0.3)
        
        # 先启动电机
        self.sim.send_input('SET_MOTOR 200 2')
        time.sleep(0.2)
        
        # 紧急停止
        self.sim.send_input('STOP_ALL')
        time.sleep(0.2)
        
        status = self.sim.get_status()
        self.assertTrue(status['emergency_stop'])
        self.assertEqual(status['motor']['speed'], 0)
        print("✓ 紧急停止测试通过")
    
    def test_calibration(self):
        """测试校准"""
        self.sim.start()
        time.sleep(0.3)
        
        self.sim.send_input('CALIB_SET TEMP 2.5')
        time.sleep(0.2)
        
        status = self.sim.get_status()
        self.assertEqual(status['calib']['temp'], 2.5)
        print("✓ 校准测试通过")
    
    def test_sensor_data(self):
        """测试传感器数据"""
        self.sim.start()
        time.sleep(1)  # 等待几个采样周期
        
        sensor_msgs = [d for d in self.output_data if '"type":"sensor"' in d]
        self.assertGreater(len(sensor_msgs), 0)
        
        # 验证数据结构
        import json
        last_sensor = json.loads(sensor_msgs[-1])
        data = last_sensor.get('data', last_sensor)
        
        self.assertIn('temp_dht', data)
        self.assertIn('humidity', data)
        self.assertIn('distance', data)
        print("✓ 传感器数据测试通过")


class TestArduinoBridge(unittest.TestCase):
    """Arduino桥接器测试（使用模拟器）"""
    
    def test_bridge_with_simulator(self):
        """测试桥接器与模拟器集成"""
        sim = ArduinoSimulator(sensor_interval=0.1)
        
        received_data = []
        
        def on_sensor(data: SensorData):
            received_data.append(data)
        
        # 创建桥接器（模拟模式）
        bridge = ArduinoBridge(auto_detect=False)
        bridge._simulator = sim  # 注入模拟器
        bridge._running = True
        
        # 模拟连接
        bridge.state = type('obj', (object,), {'value': 'connected'})()
        bridge.state.value = 'connected'
        
        sim.set_output_callback(lambda d: bridge._parse_and_handle(d))
        bridge.sensor_callback = on_sensor
        
        # 启动模拟器
        sim.start()
        time.sleep(2)
        
        # 发送命令
        bridge.set_motor(100, 1)
        time.sleep(0.3)
        bridge.set_servo(45)
        time.sleep(0.3)
        bridge.get_status()
        time.sleep(0.3)
        
        # 验证
        self.assertGreater(len(received_data), 0)
        print(f"✓ 桥接器接收到 {len(received_data)} 条传感器数据")
        
        # 清理
        sim.stop()
        bridge._running = False
        print("✓ 桥接器集成测试通过")


class TestSensorCollector(unittest.TestCase):
    """传感器采集器测试（使用模拟器）"""
    
    def test_collector_with_simulator(self):
        """测试采集器与模拟器集成"""
        sim = ArduinoSimulator(sensor_interval=0.1)
        
        collected = []
        
        def on_data(data: SensorData):
            collected.append(data)
        
        # 创建采集器
        collector = SensorCollector()
        collector.bridge._simulator = sim
        collector.bridge._running = True
        
        sim.set_output_callback(lambda d: collector.bridge._parse_and_handle(d))
        collector.on_data_callback = on_data
        
        # 启动
        sim.start()
        collector.start_collection()
        time.sleep(3)
        
        # 验证
        self.assertGreater(len(collected), 0)
        print(f"✓ 采集器收集了 {len(collected)} 条数据")
        
        # 获取统计
        stats = collector.get_all_stats()
        print(f"  温度平均值: {stats['temp_dht'].mean_val:.1f}°C")
        print(f"  湿度平均值: {stats['humidity'].mean_val:.1f}%")
        
        # 清理
        sim.stop()
        collector.stop_collection()
        collector.bridge._running = False
        print("✓ 采集器集成测试通过")


def run_integration_test():
    """运行集成测试"""
    print("=" * 60)
    print("数字孪生系统集成测试")
    print("=" * 60 + "\n")
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试
    suite.addTests(loader.loadTestsFromTestCase(TestArduinoSimulator))
    suite.addTests(loader.loadTestsFromTestCase(TestArduinoBridge))
    suite.addTests(loader.loadTestsFromTestCase(TestSensorCollector))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"  运行: {result.testsRun}")
    print(f"  成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  失败: {len(result.failures)}")
    print(f"  错误: {len(result.errors)}")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_integration_test()
    sys.exit(0 if success else 1)
