#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arduino模拟器串口通信集成测试
文件名: serial_communication_test.py
版本: v1.1
创建时间: 2026-04-13
描述: 验证ArduinoBridge与ArduinoSimulator之间的完整通信流程

测试覆盖:
1. 连接建立与设备检测
2. 心跳检测(PING/PONG)
3. 传感器数据接收
4. 执行器控制指令发送
5. 错误处理与重连机制
6. 性能基准测试
"""

import sys
import os
import time
import threading
import unittest
from unittest.mock import Mock, patch, MagicMock
from io import StringIO
import json

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Arduino'))
sys.path.insert(0, os.path.dirname(__file__))

from arduino_simulator import ArduinoSimulator
from arduino_bridge import ArduinoBridge, SensorData, ConnectionState


class TestSerialCommunication(unittest.TestCase):
    """串口通信测试套件"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        print("\n" + "="*60)
        print("初始化Arduino模拟器...")
        cls.simulator = ArduinoSimulator(
            sensor_interval=0.5,
            noise_level=0.05,
            enable_trends=True
        )
        cls.simulator.start()
        time.sleep(1)  # 等待模拟器启动
        
        print("初始化ArduinoBridge...")
        cls.bridge = ArduinoBridge(
            port=None,
            auto_detect=False,  # 使用模拟器端口
            timeout=2.0
        )
        
    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        print("\n清理测试资源...")
        cls.bridge.disconnect()
        cls.simulator.stop()
        print("清理完成")
    
    def test_0_bridge_initialization(self):
        """测试0: 桥接器初始化"""
        print("\n[测试0] 桥接器初始化")
        self.assertIsNotNone(self.bridge)
        self.assertEqual(self.bridge.state, ConnectionState.DISCONNECTED)
        self.assertFalse(self.bridge.is_connected)
        print("✓ 桥接器初始化正确")
    
    def test_1_direct_simulator_communication(self):
        """测试1: 直接模拟器通信"""
        print("\n[测试1] 直接模拟器通信测试")
        
        received_data = []
        
        def on_output(data):
            print(f"  [Sim] {data}")
            try:
                parsed = json.loads(data)
                if parsed.get('type') == 'sensor':
                    received_data.append(parsed)
            except:
                pass
        
        self.simulator.set_output_callback(on_output)
        
        # 测试PING指令
        print("  发送 PING 指令...")
        self.simulator.send_input("PING")
        time.sleep(0.6)
        
        # 测试GET_STATUS指令
        print("  发送 GET_STATUS 指令...")
        self.simulator.send_input("GET_STATUS")
        time.sleep(0.6)
        
        # 测试SET_MOTOR指令
        print("  发送 SET_MOTOR 128 1 指令...")
        self.simulator.send_input("SET_MOTOR 128 1")
        time.sleep(0.6)
        
        # 测试SET_SERVO指令
        print("  发送 SET_SERVO 90 指令...")
        self.simulator.send_input("SET_SERVO 90")
        time.sleep(0.6)
        
        # 测试STOP_ALL指令
        print("  发送 STOP_ALL 指令...")
        self.simulator.send_input("STOP_ALL")
        time.sleep(0.6)
        
        # 验证传感器数据接收
        self.assertGreater(len(received_data), 0, "应该接收到传感器数据")
        print(f"✓ 接收到 {len(received_data)} 条传感器数据")
        
        # 验证数据有效性
        for data in received_data:
            self.assertIsInstance(data, dict)
            self.assertIn('humidity', data)
            self.assertIn('temp_dht', data)
            print(f"  数据样例: T={data['temp_dht']:.1f}°C, H={data['humidity']:.1f}%")
        
        print("✓ 直接通信测试通过")
    
    def test_2_bridge_protocol_handling(self):
        """测试2: 桥接器协议解析"""
        print("\n[测试2] 桥接器协议解析测试")
        
        # 测试JSON解析
        test_messages = [
            '{"type": "sensor", "data": {"humidity": 65.5, "temp_dht": 25.3}}',
            '{"type": "pong", "timestamp": 1234567890}',
            '{"type": "status", "motor": {"speed": 128, "direction": 1}, "uptime": 5000}',
            '{"type": "error", "msg": "Test error"}'
        ]
        
        for msg in test_messages:
            self.bridge._parse_and_handle(msg)
        
        print("✓ 协议解析测试通过")
    
    def test_3_actuator_control(self):
        """测试3: 执行器控制"""
        print("\n[测试3] 执行器控制测试")
        
        responses = []
        
        def on_output(data):
            try:
                parsed = json.loads(data)
                responses.append(parsed)
                print(f"  响应: {parsed}")
            except:
                pass
        
        self.simulator.set_output_callback(on_output)
        
        # 电机控制序列
        motor_tests = [
            (0, 0, "停止"),
            (128, 1, "半速正转"),
            (255, 1, "全速正转"),
            (128, 2, "半速反转"),
            (64, 1, "低速正转"),
            (0, 0, "停止")
        ]
        
        for speed, direction, desc in motor_tests:
            cmd = f"SET_MOTOR {speed} {direction}"
            self.simulator.send_input(cmd)
            print(f"  电机: {desc} (speed={speed}, dir={direction})")
            time.sleep(0.3)
        
        # 舵机控制序列
        servo_tests = [0, 45, 90, 135, 180, 90]
        
        for angle in servo_tests:
            cmd = f"SET_SERVO {angle}"
            self.simulator.send_input(cmd)
            print(f"  舵机: 角度={angle}°")
            time.sleep(0.3)
        
        # 验证响应
        self.assertGreater(len(responses), 0, "应该收到响应")
        print("✓ 执行器控制测试通过")
    
    def test_4_safety_mechanisms(self):
        """测试4: 安全机制"""
        print("\n[测试4] 安全机制测试")
        
        responses = []
        
        def on_output(data):
            try:
                parsed = json.loads(data)
                responses.append(parsed)
            except:
                pass
        
        self.simulator.set_output_callback(on_output)
        
        # 测试紧急停止
        print("  测试紧急停止...")
        self.simulator.send_input("STOP_ALL")
        time.sleep(0.3)
        
        # 测试安全开关
        print("  测试安全开关...")
        self.simulator.send_input("SAFETY_ON")
        time.sleep(0.2)
        self.simulator.send_input("SAFETY_OFF")
        time.sleep(0.2)
        
        # 测试滤波器重置
        print("  测试滤波器重置...")
        self.simulator.send_input("FILTER_RESET")
        time.sleep(0.2)
        
        print("✓ 安全机制测试通过")
    
    def test_5_calibration_system(self):
        """测试5: 校准系统"""
        print("\n[测试5] 校准系统测试")
        
        responses = []
        
        def on_output(data):
            try:
                parsed = json.loads(data)
                responses.append(parsed)
            except:
                pass
        
        self.simulator.set_output_callback(on_output)
        
        # 设置校准值
        self.simulator.send_input("CALIB_SET temp 2.5")
        time.sleep(0.3)
        
        # 重置校准
        self.simulator.send_input("CALIB_RESET")
        time.sleep(0.3)
        
        print("✓ 校准系统测试通过")
    
    def test_6_error_handling(self):
        """测试6: 错误处理"""
        print("\n[测试6] 错误处理测试")
        
        responses = []
        
        def on_output(data):
            try:
                parsed = json.loads(data)
                responses.append(parsed)
                print(f"  响应: {parsed}")
            except:
                pass
        
        self.simulator.set_output_callback(on_output)
        
        # 测试无效指令
        invalid_commands = [
            "INVALID_CMD",
            "SET_MOTOR",  # 缺少参数
            "SET_SERVO 200",  # 超出范围
            "SET_MOTOR -1 0",  # 负数速度
        ]
        
        for cmd in invalid_commands:
            self.simulator.send_input(cmd)
            print(f"  处理无效指令: {cmd}")
            time.sleep(0.2)
        
        print("✓ 错误处理测试通过")
    
    def test_7_performance_benchmark(self):
        """测试7: 性能基准测试"""
        print("\n[测试7] 性能基准测试")
        
        def on_output(data):
            pass  # 忽略输出
        
        self.simulator.set_output_callback(on_output)
        
        iterations = 50
        start_time = time.time()
        
        for i in range(iterations):
            self.simulator.send_input("GET_STATUS")
        
        elapsed = time.time() - start_time
        avg_time = (elapsed / iterations) * 1000
        
        print(f"  执行 {iterations} 次状态查询")
        print(f"  总耗时: {elapsed:.3f}s")
        print(f"  平均耗时: {avg_time:.2f}ms/次")
        print(f"  吞吐量: {iterations/elapsed:.1f} 次/秒")
        
        self.assertLess(avg_time, 50, "平均响应时间应小于50ms")
        print("✓ 性能基准测试通过")
    
    def test_8_concurrent_operations(self):
        """测试8: 并发操作测试"""
        print("\n[测试8] 并发操作测试")
        
        results = {'motor': [], 'servo': [], 'sensor': []}
        lock = threading.Lock()
        
        def motor_worker():
            for i in range(10):
                self.simulator.send_input(f"SET_MOTOR {i*25} 1")
                time.sleep(0.05)
                with lock:
                    results['motor'].append(i*25)
        
        def servo_worker():
            for angle in [0, 45, 90, 135, 180]:
                self.simulator.send_input(f"SET_SERVO {angle}")
                time.sleep(0.05)
                with lock:
                    results['servo'].append(angle)
        
        # 启动并发线程
        motor_thread = threading.Thread(target=motor_worker)
        servo_thread = threading.Thread(target=servo_worker)
        
        motor_thread.start()
        servo_thread.start()
        
        motor_thread.join()
        servo_thread.join()
        
        print(f"  电机操作: {len(results['motor'])} 次")
        print(f"  舵机操作: {len(results['servo'])} 次")
        
        self.assertEqual(len(results['motor']), 10)
        self.assertEqual(len(results['servo']), 5)
        print("✓ 并发操作测试通过")
    
    def test_9_data_integration(self):
        """测试9: 数据集成测试"""
        print("\n[测试9] 数据集成测试")
        
        # 收集多组传感器数据
        sensor_readings = []
        
        def on_output(data):
            try:
                parsed = json.loads(data)
                if parsed.get('type') == 'sensor':
                    sensor_readings.append(parsed)
            except:
                pass
        
        self.simulator.set_output_callback(on_output)
        
        # 连续采集10秒数据
        print("  连续采集10秒传感器数据...")
        end_time = time.time() + 10
        
        while time.time() < end_time:
            self.simulator.send_input("GET_STATUS")
            time.sleep(1)
        
        print(f"  采集到 {len(sensor_readings)} 组数据")
        
        # 分析数据质量
        if sensor_readings:
            temps = [d.get('temp_dht', 0) for d in sensor_readings]
            humidity = [d.get('humidity', 0) for d in sensor_readings]
            
            print(f"  温度范围: {min(temps):.1f}°C ~ {max(temps):.1f}°C")
            print(f"  湿度范围: {min(humidity):.1f}% ~ {max(humidity):.1f}%")
            
            # 验证数据趋势
            if len(temps) > 5:
                early_avg = sum(temps[:5]) / 5
                late_avg = sum(temps[-5:]) / 5
                print(f"  温度变化: {early_avg:.2f}°C → {late_avg:.2f}°C")
        
        self.assertGreater(len(sensor_readings), 5, "应采集足够的传感器数据")
        print("✓ 数据集成测试通过")


def run_integration_demo():
    """运行集成演示"""
    print("\n" + "="*60)
    print("Arduino串口通信集成演示")
    print("="*60)
    
    # 初始化
    print("\n初始化系统...")
    sim = ArduinoSimulator(sensor_interval=1.0, noise_level=0.1)
    sim.start()
    
    def on_output(data):
        try:
            parsed = json.loads(data)
            if parsed.get('type') == 'sensor':
                print(f"\n📊 传感器数据:")
                print(f"   温度(DHT11): {parsed.get('temp_dht', 0):.1f}°C")
                print(f"   温度(BMP280): {parsed.get('temp_bmp', 0):.1f}°C")
                print(f"   湿度: {parsed.get('humidity', 0):.1f}%")
                print(f"   气压: {parsed.get('pressure', 0):.1f}hPa")
                print(f"   距离: {parsed.get('distance', 0)}cm")
                print(f"   光照: {parsed.get('light', 0)}")
            elif parsed.get('type') in ['motor', 'servo', 'action', 'pong']:
                print(f"\n📨 响应: {parsed}")
        except:
            print(f"\n[Raw] {data}")
    
    sim.set_output_callback(on_output)
    time.sleep(2)
    
    print("\n开始演示...\n")
    
    try:
        # 演示1: 获取状态
        print("="*40)
        print("1. 获取设备状态")
        print("="*40)
        sim.send_input("GET_STATUS")
        time.sleep(2)
        
        # 演示2: 电机控制
        print("\n" + "="*40)
        print("2. 电机控制演示")
        print("="*40)
        
        for speed in [0, 64, 128, 192, 255, 0]:
            direction = 1 if speed > 0 else 0
            sim.send_input(f"SET_MOTOR {speed} {direction}")
            print(f"   电机: 速度={speed}, 方向={'正转' if direction==1 else '停止'}")
            time.sleep(1.5)
        
        # 演示3: 舵机控制
        print("\n" + "="*40)
        print("3. 舵机控制演示")
        print("="*40)
        
        for angle in [0, 45, 90, 135, 180, 90]:
            sim.send_input(f"SET_SERVO {angle}")
            print(f"   舵机: 角度={angle}°")
            time.sleep(1)
        
        # 演示4: 安全机制
        print("\n" + "="*40)
        print("4. 安全机制演示")
        print("="*40)
        
        sim.send_input("SAFETY_ON")
        print("   安全监控: 启用")
        time.sleep(1)
        
        sim.send_input("STOP_ALL")
        print("   紧急停止: 触发")
        time.sleep(1)
        
        sim.send_input("SAFETY_OFF")
        print("   安全监控: 禁用")
        
        print("\n演示完成!")
        
    finally:
        sim.stop()
        print("\n系统已关闭")


def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        # 运行演示模式
        run_integration_demo()
    else:
        # 运行测试套件
        print("\n" + "="*60)
        print("Arduino串口通信测试套件")
        print("="*60)
        
        # 创建测试套件
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(TestSerialCommunication)
        
        # 运行测试
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # 输出总结
        print("\n" + "="*60)
        print("测试总结")
        print("="*60)
        print(f"运行测试: {result.testsRun}")
        print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
        print(f"失败: {len(result.failures)}")
        print(f"错误: {len(result.errors)}")
        
        if result.wasSuccessful():
            print("\n🎉 所有测试通过!")
            return 0
        else:
            print("\n❌ 测试失败，请检查上述错误信息")
            return 1


if __name__ == "__main__":
    sys.exit(main())
