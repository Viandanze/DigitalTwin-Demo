#!/usr/bin/env python3
"""
执行器集成实战项目 - 主控制程序
功能：模拟传感器数据、决策控制指令、串口通信、状态可视化
作者：数字孪生学习项目
日期：2026年4月3日
"""

import time
import random
import threading
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

# 导入自定义模块
try:
    from sensor_simulator import SensorSimulator
    from control_engine import ControlEngine
    from serial_manager import SerialManager
    from data_logger import DataLogger
except ImportError:
    # 如果模块不存在，将在后续创建
    pass

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/control_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ControlSystem:
    """主控制系统类"""
    
    def __init__(self, config_file: str = None):
        """初始化控制系统
        
        Args:
            config_file: 配置文件路径
        """
        logger.info("初始化控制系统...")
        
        # 加载配置
        self.config = self._load_config(config_file)
        
        # 系统状态
        self.running = False
        self.current_scenario = self.config.get('default_scenario', 'autonomous_vehicle')
        
        # 初始化各模块
        self.sensor_simulator = None
        self.control_engine = None
        self.serial_manager = None
        self.data_logger = None
        
        self._initialize_modules()
        
        # 数据存储
        self.sensor_data = {}
        self.control_commands = []
        self.actuator_status = {}
        
        logger.info("控制系统初始化完成")
    
    def _load_config(self, config_file: str) -> Dict:
        """加载配置文件
        
        Args:
            config_file: 配置文件路径
            
        Returns:
            配置字典
        """
        default_config = {
            'system': {
                'name': '数字孪生执行器控制系统',
                'version': '1.0.0',
                'description': '基于树莓派+Arduino的执行器集成演示系统'
            },
            'sensors': {
                'temperature': {'range': [15.0, 35.0], 'unit': '℃', 'update_interval': 2.0},
                'humidity': {'range': [30.0, 90.0], 'unit': '%', 'update_interval': 2.0},
                'distance': {'range': [5.0, 45.0], 'unit': 'cm', 'update_interval': 1.0},
                'light': {'range': [0.0, 100.0], 'unit': '%', 'update_interval': 0.5},
                'pressure': {'range': [950.0, 1050.0], 'unit': 'hPa', 'update_interval': 1.0}
            },
            'actuators': {
                'dc_motor': {'type': 'L298N', 'channels': ['MOTOR1', 'MOTOR2']},
                'servo': {'type': 'SG90', 'channels': ['SERVO1']},
                'stepper': {'type': '28BYJ-48', 'channels': ['STEPPER1']}
            },
            'serial': {
                'port': '/dev/ttyAMA0',  # 树莓派默认串口
                'baudrate': 115200,
                'timeout': 1.0,
                'retry_count': 3
            },
            'control': {
                'decision_interval': 1.0,  # 决策间隔（秒）
                'emergency_stop_distance': 20.0,  # 紧急停止距离（cm）
                'temperature_threshold_high': 28.0,  # 温度高阈值（℃）
                'temperature_threshold_low': 18.0,   # 温度低阈值（℃）
                'humidity_threshold_high': 80.0,     # 湿度高阈值（%）
                'humidity_threshold_low': 40.0       # 湿度低阈值（%）
            },
            'default_scenario': 'autonomous_vehicle',
            'logging': {
                'enabled': True,
                'file_path': 'logs/system_log.jsonl',
                'max_size_mb': 10
            }
        }
        
        # TODO: 如果提供了配置文件，则合并配置
        return default_config
    
    def _initialize_modules(self):
        """初始化各功能模块"""
        logger.info("初始化功能模块...")
        
        # 初始化传感器模拟器
        try:
            from sensor_simulator import SensorSimulator
            self.sensor_simulator = SensorSimulator(self.config['sensors'])
            logger.info("传感器模拟器初始化成功")
        except ImportError:
            logger.warning("传感器模拟器模块未找到，将使用简化模拟")
            self.sensor_simulator = SimpleSensorSimulator(self.config['sensors'])
        
        # 初始化控制引擎
        try:
            from control_engine import ControlEngine
            self.control_engine = ControlEngine(self.config['control'])
            logger.info("控制引擎初始化成功")
        except ImportError:
            logger.warning("控制引擎模块未找到，将使用简化决策")
            self.control_engine = SimpleControlEngine(self.config['control'])
        
        # 初始化串口管理器
        try:
            from serial_manager import SerialManager
            self.serial_manager = SerialManager(self.config['serial'])
            logger.info("串口管理器初始化成功")
        except ImportError:
            logger.warning("串口管理器模块未找到，将使用模拟通信")
            self.serial_manager = MockSerialManager(self.config['serial'])
        
        # 初始化数据记录器
        try:
            from data_logger import DataLogger
            self.data_logger = DataLogger(self.config['logging'])
            logger.info("数据记录器初始化成功")
        except ImportError:
            logger.warning("数据记录器模块未找到，将使用简化记录")
            self.data_logger = SimpleDataLogger()
    
    def start(self):
        """启动控制系统"""
        if self.running:
            logger.warning("控制系统已经在运行中")
            return
        
        logger.info("启动控制系统...")
        self.running = True
        
        # 启动串口通信
        if self.serial_manager:
            self.serial_manager.start()
        
        # 启动数据记录
        if self.data_logger:
            self.data_logger.start()
        
        # 启动主控制循环
        control_thread = threading.Thread(target=self._control_loop, daemon=True)
        control_thread.start()
        
        # 启动状态监控线程
        monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        monitor_thread.start()
        
        logger.info("控制系统启动完成")
    
    def stop(self):
        """停止控制系统"""
        logger.info("停止控制系统...")
        self.running = False
        
        # 停止各模块
        if self.serial_manager:
            self.serial_manager.stop()
        
        if self.data_logger:
            self.data_logger.stop()
        
        # 发送停止指令
        self._send_emergency_stop()
        
        logger.info("控制系统已停止")
    
    def switch_scenario(self, scenario_name: str):
        """切换控制场景
        
        Args:
            scenario_name: 场景名称 ('autonomous_vehicle' 或 'smart_greenhouse')
        """
        if scenario_name not in ['autonomous_vehicle', 'smart_greenhouse']:
            logger.error(f"未知场景: {scenario_name}")
            return
        
        self.current_scenario = scenario_name
        logger.info(f"切换到场景: {scenario_name}")
        
        # 记录场景切换事件
        event_data = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'scenario_switch',
            'scenario': scenario_name,
            'message': f'切换到 {scenario_name} 场景'
        }
        
        if self.data_logger:
            self.data_logger.log_event(event_data)
    
    def _control_loop(self):
        """主控制循环"""
        logger.info("主控制循环启动")
        
        last_decision_time = time.time()
        
        while self.running:
            try:
                current_time = time.time()
                
                # 检查是否到达决策间隔
                if current_time - last_decision_time >= self.config['control']['decision_interval']:
                    # 更新传感器数据
                    self._update_sensor_data()
                    
                    # 生成控制决策
                    self._make_control_decision()
                    
                    # 发送控制指令
                    self._send_control_commands()
                    
                    # 更新最后决策时间
                    last_decision_time = current_time
                
                # 短暂休眠，避免CPU过度占用
                time.sleep(0.01)
                
            except KeyboardInterrupt:
                logger.info("接收到中断信号，准备退出")
                self.running = False
                break
            except Exception as e:
                logger.error(f"控制循环发生错误: {e}")
                time.sleep(1.0)  # 错误后等待1秒再继续
        
        logger.info("主控制循环结束")
    
    def _update_sensor_data(self):
        """更新传感器数据"""
        if self.sensor_simulator:
            self.sensor_data = self.sensor_simulator.get_current_data()
            
            # 记录传感器数据
            if self.data_logger:
                self.data_logger.log_sensor_data(self.sensor_data)
            
            # 打印当前传感器数据（调试用）
            self._print_sensor_status()
    
    def _make_control_decision(self):
        """生成控制决策"""
        if not self.control_engine:
            logger.warning("控制引擎未初始化，无法生成决策")
            return
        
        # 根据当前场景选择决策逻辑
        if self.current_scenario == 'autonomous_vehicle':
            commands = self.control_engine.decide_vehicle_control(self.sensor_data)
        elif self.current_scenario == 'smart_greenhouse':
            commands = self.control_engine.decide_greenhouse_control(self.sensor_data)
        else:
            commands = []
        
        self.control_commands = commands
        
        # 记录控制决策
        if self.data_logger and commands:
            self.data_logger.log_control_decision(commands)
    
    def _send_control_commands(self):
        """发送控制指令到Arduino"""
        if not self.serial_manager or not self.control_commands:
            return
        
        for command in self.control_commands:
            success = self.serial_manager.send_command(command)
            
            if success:
                logger.debug(f"指令发送成功: {command}")
            else:
                logger.warning(f"指令发送失败: {command}")
    
    def _send_emergency_stop(self):
        """发送紧急停止指令"""
        emergency_commands = [
            "MOTOR:0:0",      # 停止直流电机
            "SERVO:90",       # 舵机回到中立位
            "STEPPER:0:0"     # 停止步进电机
        ]
        
        if self.serial_manager:
            for cmd in emergency_commands:
                self.serial_manager.send_command(cmd)
                logger.info(f"发送紧急停止指令: {cmd}")
    
    def _monitor_loop(self):
        """状态监控循环"""
        logger.info("状态监控循环启动")
        
        while self.running:
            try:
                # 接收Arduino状态反馈
                self._receive_actuator_status()
                
                # 更新执行器状态显示
                self._update_actuator_display()
                
                # 检查系统健康状况
                self._check_system_health()
                
                # 监控间隔
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"状态监控循环发生错误: {e}")
                time.sleep(1.0)
        
        logger.info("状态监控循环结束")
    
    def _receive_actuator_status(self):
        """接收Arduino状态反馈"""
        if not self.serial_manager:
            return
        
        # 查询设备状态
        self.serial_manager.send_command("STATUS:ALL")
        
        # 读取反馈（模拟实现）
        feedback = self.serial_manager.receive_feedback()
        
        if feedback:
            # 解析反馈数据
            for line in feedback.split('\n'):
                if line.strip():
                    parts = line.strip().split(':')
                    if len(parts) >= 3:
                        device = parts[0]
                        status_type = parts[1]
                        value = parts[2]
                        
                        if device not in self.actuator_status:
                            self.actuator_status[device] = {}
                        
                        self.actuator_status[device][status_type] = value
    
    def _update_actuator_display(self):
        """更新执行器状态显示"""
        # 这里可以更新GUI或Web界面
        # 目前仅打印日志
        if self.actuator_status:
            logger.debug(f"执行器状态: {self.actuator_status}")
    
    def _check_system_health(self):
        """检查系统健康状况"""
        # 检查传感器数据有效性
        for sensor_name, value in self.sensor_data.items():
            if value is None:
                logger.warning(f"传感器 {sensor_name} 数据无效")
        
        # 检查通信状态
        if self.serial_manager and not self.serial_manager.is_connected():
            logger.error("串口通信断开，尝试重连...")
            self.serial_manager.reconnect()
    
    def _print_sensor_status(self):
        """打印当前传感器状态（调试用）"""
        if not self.sensor_data:
            return
        
        status_lines = []
        for sensor, value in self.sensor_data.items():
            if value is not None:
                unit = self.config['sensors'].get(sensor, {}).get('unit', '')
                status_lines.append(f"{sensor}: {value:.1f}{unit}")
        
        if status_lines:
            logger.info(f"传感器状态: {', '.join(status_lines)}")
    
    def get_system_status(self) -> Dict:
        """获取系统状态
        
        Returns:
            系统状态字典
        """
        status = {
            'running': self.running,
            'current_scenario': self.current_scenario,
            'sensor_data': self.sensor_data,
            'actuator_status': self.actuator_status,
            'last_commands': self.control_commands[-5:] if self.control_commands else [],
            'timestamp': datetime.now().isoformat()
        }
        
        # 添加模块状态
        if self.serial_manager:
            status['serial_connected'] = self.serial_manager.is_connected()
        
        return status

# 简化模块实现（用于测试）
class SimpleSensorSimulator:
    """简化传感器模拟器"""
    
    def __init__(self, sensor_config):
        self.config = sensor_config
    
    def get_current_data(self):
        data = {}
        for sensor_name, config in self.config.items():
            if 'range' in config:
                min_val, max_val = config['range']
                # 添加一些随机变化
                value = random.uniform(min_val, max_val)
                # 偶尔添加异常值
                if random.random() < 0.05:  # 5%概率异常
                    value = random.uniform(min_val - 10, max_val + 10)
                data[sensor_name] = value
        return data

class SimpleControlEngine:
    """简化控制引擎"""
    
    def __init__(self, control_config):
        self.config = control_config
    
    def decide_vehicle_control(self, sensor_data):
        """自动避障小车控制决策"""
        commands = []
        distance = sensor_data.get('distance', 100.0)
        
        # 紧急停止规则
        if distance < self.config['emergency_stop_distance']:
            commands.append("MOTOR:0:0")  # 停止
            commands.append("SERVO:45")   # 右转舵机
            logger.warning(f"检测到障碍物: {distance:.1f}cm，执行紧急停止")
        else:
            # 正常前进
            speed = min(80, int(distance / 2))
            commands.append(f"MOTOR:0:{speed}")
        
        return commands
    
    def decide_greenhouse_control(self, sensor_data):
        """智能温室控制决策"""
        commands = []
        temperature = sensor_data.get('temperature', 25.0)
        humidity = sensor_data.get('humidity', 60.0)
        
        # 温度控制
        if temperature > self.config['temperature_threshold_high']:
            commands.append("MOTOR:0:60")  # 启动通风扇
            logger.info(f"温度过高 ({temperature:.1f}℃)，启动通风扇")
        elif temperature < self.config['temperature_threshold_low']:
            commands.append("MOTOR:0:40")  # 启动加热器（模拟）
            logger.info(f"温度过低 ({temperature:.1f}℃)，启动加热器")
        
        # 湿度控制
        if humidity < self.config['humidity_threshold_low']:
            commands.append("SERVO:30")   # 调整加湿器阀门
            logger.info(f"湿度过低 ({humidity:.1f}%)，启动加湿器")
        elif humidity > self.config['humidity_threshold_high']:
            commands.append("SERVO:150")  # 调整除湿器阀门
            logger.info(f"湿度过高 ({humidity:.1f}%)，启动除湿器")
        
        return commands

class MockSerialManager:
    """模拟串口管理器"""
    
    def __init__(self, serial_config):
        self.config = serial_config
        self.connected = True
    
    def start(self):
        logger.info("模拟串口管理器启动")
    
    def stop(self):
        logger.info("模拟串口管理器停止")
    
    def send_command(self, command):
        logger.debug(f"模拟发送指令: {command}")
        return True
    
    def receive_feedback(self):
        # 模拟反馈数据
        feedback_lines = [
            "MOTOR:SPEED:50",
            "SERVO:ANGLE:90",
            "STEPPER:POS:1024"
        ]
        return '\n'.join(feedback_lines)
    
    def is_connected(self):
        return self.connected
    
    def reconnect(self):
        logger.info("模拟重连串口")
        self.connected = True

class SimpleDataLogger:
    """简化数据记录器"""
    
    def start(self):
        logger.info("简化数据记录器启动")
    
    def stop(self):
        logger.info("简化数据记录器停止")
    
    def log_sensor_data(self, data):
        pass
    
    def log_control_decision(self, commands):
        pass
    
    def log_event(self, event):
        logger.info(f"事件记录: {event.get('event_type')} - {event.get('message')}")

# 主程序入口
def main():
    """主函数"""
    print("=" * 60)
    print("数字孪生执行器控制系统 v1.0")
    print("=" * 60)
    
    # 创建控制系统实例
    system = ControlSystem()
    
    # 启动系统
    system.start()
    
    try:
        # 交互式命令循环
        while system.running:
            print("\n可用命令:")
            print("  1. 显示系统状态")
            print("  2. 切换场景 (1:自动避障小车, 2:智能温室)")
            print("  3. 手动发送指令")
            print("  4. 退出系统")
            
            choice = input("\n请输入命令编号 (1-4): ").strip()
            
            if choice == '1':
                status = system.get_system_status()
                print(f"\n系统状态:")
                print(f"  运行状态: {'运行中' if status['running'] else '已停止'}")
                print(f"  当前场景: {status['current_scenario']}")
                print(f"  传感器数据: {status['sensor_data']}")
                print(f"  执行器状态: {status['actuator_status']}")
                
            elif choice == '2':
                print("\n选择场景:")
                print("  1. 自动避障小车 (autonomous_vehicle)")
                print("  2. 智能温室 (smart_greenhouse)")
                scenario_choice = input("请输入场景编号 (1-2): ").strip()
                
                if scenario_choice == '1':
                    system.switch_scenario('autonomous_vehicle')
                elif scenario_choice == '2':
                    system.switch_scenario('smart_greenhouse')
                else:
                    print("无效选择")
            
            elif choice == '3':
                command = input("请输入指令 (如 MOTOR:0:50): ").strip()
                if command:
                    if system.serial_manager:
                        success = system.serial_manager.send_command(command)
                        print(f"指令发送 {'成功' if success else '失败'}")
            
            elif choice == '4':
                print("正在停止系统...")
                system.stop()
                break
            
            else:
                print("无效命令")
            
            # 短暂延迟
            time.sleep(0.1)
                
    except KeyboardInterrupt:
        print("\n接收到中断信号，停止系统...")
        system.stop()
    
    print("系统已退出")
    print("=" * 60)

if __name__ == "__main__":
    main()