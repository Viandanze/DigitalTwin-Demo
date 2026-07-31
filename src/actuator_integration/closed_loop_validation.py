#!/usr/bin/env python3
"""
闭环控制场景验证脚本
功能：验证自动避障小车和智能温室两个闭环控制场景
作者：数字孪生学习项目
日期：2026年4月3日
"""

import time
import random
import json
from datetime import datetime
import logging
from typing import Dict, List, Tuple
import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入模拟模块
try:
    from sensor_simulator import SensorSimulator, SimpleSensorSimulator
    from control_engine import ControlEngine, SimpleControlEngine
    from serial_manager import SerialManager, MockSerialManager
except ImportError:
    # 使用简化实现
    pass

logger = logging.getLogger(__name__)

class ClosedLoopValidator:
    """闭环控制验证器"""
    
    def __init__(self):
        """初始化验证器"""
        # 测试配置
        self.config = {
            'autonomous_vehicle': {
                'emergency_stop_distance': 20.0,
                'test_scenarios': [
                    {'distance': 30.0, 'expected_action': '前进'},
                    {'distance': 15.0, 'expected_action': '停止'},
                    {'distance': 8.0, 'expected_action': '紧急停止'}
                ]
            },
            'smart_greenhouse': {
                'temperature_threshold_high': 28.0,
                'temperature_threshold_low': 18.0,
                'humidity_threshold_high': 80.0,
                'humidity_threshold_low': 40.0,
                'test_scenarios': [
                    {'temperature': 25.0, 'humidity': 60.0, 'expected_actions': ['最小通风']},
                    {'temperature': 30.0, 'humidity': 35.0, 'expected_actions': ['通风扇', '加湿器']},
                    {'temperature': 15.0, 'humidity': 85.0, 'expected_actions': ['加热器', '除湿器']}
                ]
            }
        }
        
        # 测试结果
        self.test_results = {
            'autonomous_vehicle': [],
            'smart_greenhouse': []
        }
        
        # 统计信息
        self.stats = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'start_time': None,
            'end_time': None
        }
        
        logger.info("闭环控制验证器初始化完成")
    
    def validate_vehicle_scenario(self):
        """验证自动避障小车场景"""
        logger.info("开始验证自动避障小车场景...")
        
        # 创建简化的控制引擎
        control_config = {
            'emergency_stop_distance': 20.0,
            'decision_interval': 1.0
        }
        
        try:
            from control_engine import ControlEngine
            control_engine = ControlEngine(control_config)
        except ImportError:
            control_engine = SimpleControlEngine(control_config)
        
        test_scenarios = self.config['autonomous_vehicle']['test_scenarios']
        
        for i, scenario in enumerate(test_scenarios):
            logger.info(f"测试场景 {i+1}: 距离={scenario['distance']}cm")
            
            # 创建传感器数据
            sensor_data = {
                'distance': scenario['distance'],
                'temperature': 25.0,
                'humidity': 60.0
            }
            
            # 获取控制决策
            commands = control_engine.decide_vehicle_control(sensor_data)
            
            # 分析结果
            test_passed = self._analyze_vehicle_test(scenario, commands, sensor_data)
            
            # 记录结果
            test_result = {
                'scenario': scenario,
                'sensor_data': sensor_data,
                'commands': commands,
                'passed': test_passed,
                'timestamp': datetime.now().isoformat()
            }
            
            self.test_results['autonomous_vehicle'].append(test_result)
            
            # 更新统计
            self._update_stats(test_passed)
            
            # 打印结果
            if test_passed:
                logger.info(f"✓ 场景 {i+1} 通过")
            else:
                logger.warning(f"✗ 场景 {i+1} 失败")
            
            # 短暂延迟，使输出更清晰
            time.sleep(0.5)
        
        logger.info("自动避障小车场景验证完成")
    
    def _analyze_vehicle_test(self, scenario, commands, sensor_data) -> bool:
        """分析小车测试结果
        
        Args:
            scenario: 测试场景
            commands: 生成的命令
            sensor_data: 传感器数据
            
        Returns:
            测试是否通过
        """
        distance = sensor_data['distance']
        expected_action = scenario['expected_action']
        
        # 分析命令
        if not commands:
            return expected_action == '无动作'
        
        # 检查是否有紧急停止
        has_emergency_stop = any(cmd.startswith('MOTOR:') and ':0' in cmd.split(':')[2] for cmd in commands)
        has_stop = any('MOTOR:0:0' in cmd for cmd in commands)
        
        # 检查是否有转向
        has_steering = any(cmd.startswith('SERVO:') and '90' not in cmd for cmd in commands)
        
        # 根据距离判断预期行为
        if distance >= 30:
            # 正常前进：应该有前进命令，无停止，无大角度转向
            return (any('MOTOR:0:' in cmd for cmd in commands) and 
                   not has_stop and
                   not has_emergency_stop and
                   not (has_steering and abs(int(commands[0].split(':')[1]) - 90) > 30))
        
        elif distance >= 15:
            # 接近障碍物：应该减速，可能有轻微转向
            return (any('MOTOR:0:' in cmd for cmd in commands) and
                   any('SERVO:' in cmd for cmd in commands))
        
        else:
            # 紧急情况：应该停止，可能有避障转向
            return (has_stop or has_emergency_stop)
    
    def validate_greenhouse_scenario(self):
        """验证智能温室场景"""
        logger.info("开始验证智能温室场景...")
        
        # 创建控制引擎配置
        control_config = {
            'temperature_threshold_high': 28.0,
            'temperature_threshold_low': 18.0,
            'humidity_threshold_high': 80.0,
            'humidity_threshold_low': 40.0,
            'decision_interval': 1.0
        }
        
        try:
            from control_engine import ControlEngine
            control_engine = ControlEngine(control_config)
        except ImportError:
            control_engine = SimpleControlEngine(control_config)
        
        test_scenarios = self.config['smart_greenhouse']['test_scenarios']
        
        for i, scenario in enumerate(test_scenarios):
            logger.info(f"测试场景 {i+1}: 温度={scenario['temperature']}℃，湿度={scenario['humidity']}%")
            
            # 创建传感器数据
            sensor_data = {
                'temperature': scenario['temperature'],
                'humidity': scenario['humidity'],
                'light': 50.0,
                'pressure': 1013.0
            }
            
            # 获取控制决策
            commands = control_engine.decide_greenhouse_control(sensor_data)
            
            # 分析结果
            test_passed = self._analyze_greenhouse_test(scenario, commands, sensor_data)
            
            # 记录结果
            test_result = {
                'scenario': scenario,
                'sensor_data': sensor_data,
                'commands': commands,
                'passed': test_passed,
                'timestamp': datetime.now().isoformat()
            }
            
            self.test_results['smart_greenhouse'].append(test_result)
            
            # 更新统计
            self._update_stats(test_passed)
            
            # 打印结果
            if test_passed:
                logger.info(f"✓ 场景 {i+1} 通过")
            else:
                logger.warning(f"✗ 场景 {i+1} 失败")
            
            # 短暂延迟
            time.sleep(0.5)
        
        logger.info("智能温室场景验证完成")
    
    def _analyze_greenhouse_test(self, scenario, commands, sensor_data) -> bool:
        """分析温室测试结果
        
        Args:
            scenario: 测试场景
            commands: 生成的命令
            sensor_data: 传感器数据
            
        Returns:
            测试是否通过
        """
        temperature = sensor_data['temperature']
        humidity = sensor_data['humidity']
        expected_actions = scenario['expected_actions']
        
        # 分析命令
        if not commands:
            return expected_actions == ['无动作']
        
        # 检查温度控制
        temp_control_expected = False
        temp_control_detected = False
        
        if temperature > 28:
            # 应该启动通风扇
            temp_control_expected = True
            temp_control_detected = any('MOTOR:0:' in cmd and int(cmd.split(':')[2]) > 0 for cmd in commands)
        
        elif temperature < 18:
            # 应该启动加热器（模拟）
            temp_control_expected = True
            temp_control_detected = any('MOTOR:1:' in cmd for cmd in commands)
        
        # 检查湿度控制
        humidity_control_expected = False
        humidity_control_detected = False
        
        if humidity < 40:
            # 应该启动加湿器（舵机控制阀门）
            humidity_control_expected = True
            humidity_control_detected = any('SERVO:' in cmd and int(cmd.split(':')[1]) < 90 for cmd in commands)
        
        elif humidity > 80:
            # 应该启动除湿器（舵机控制阀门）
            humidity_control_expected = True
            humidity_control_detected = any('SERVO:' in cmd and int(cmd.split(':')[1]) > 90 for cmd in commands)
        
        # 综合判断
        if temp_control_expected and not temp_control_detected:
            return False
        
        if humidity_control_expected and not humidity_control_detected:
            return False
        
        return True
    
    def _update_stats(self, test_passed: bool):
        """更新统计信息
        
        Args:
            test_passed: 测试是否通过
        """
        self.stats['total_tests'] += 1
        
        if test_passed:
            self.stats['passed_tests'] += 1
        else:
            self.stats['failed_tests'] += 1
    
    def run_validation(self):
        """运行所有验证"""
        logger.info("开始闭环控制场景验证...")
        
        # 记录开始时间
        self.stats['start_time'] = datetime.now().isoformat()
        
        # 验证自动避障小车场景
        self.validate_vehicle_scenario()
        
        # 验证智能温室场景
        self.validate_greenhouse_scenario()
        
        # 记录结束时间
        self.stats['end_time'] = datetime.now().isoformat()
        
        # 生成验证报告
        report = self.generate_report()
        
        # 保存报告
        self.save_report(report)
        
        # 打印摘要
        self.print_summary()
        
        return report
    
    def generate_report(self) -> Dict:
        """生成验证报告
        
        Returns:
            验证报告字典
        """
        report = {
            'metadata': {
                'title': '数字孪生执行器控制系统闭环验证报告',
                'date': datetime.now().isoformat(),
                'version': '1.0.0'
            },
            'summary': {
                'total_tests': self.stats['total_tests'],
                'passed_tests': self.stats['passed_tests'],
                'failed_tests': self.stats['failed_tests'],
                'pass_rate': (self.stats['passed_tests'] / self.stats['total_tests'] * 100) 
                            if self.stats['total_tests'] > 0 else 0,
                'start_time': self.stats['start_time'],
                'end_time': self.stats['end_time']
            },
            'detailed_results': {
                'autonomous_vehicle': {
                    'scenario_count': len(self.test_results['autonomous_vehicle']),
                    'passed_count': sum(1 for r in self.test_results['autonomous_vehicle'] if r['passed']),
                    'failed_count': sum(1 for r in self.test_results['autonomous_vehicle'] if not r['passed']),
                    'scenarios': self.test_results['autonomous_vehicle']
                },
                'smart_greenhouse': {
                    'scenario_count': len(self.test_results['smart_greenhouse']),
                    'passed_count': sum(1 for r in self.test_results['smart_greenhouse'] if r['passed']),
                    'failed_count': sum(1 for r in self.test_results['smart_greenhouse'] if not r['passed']),
                    'scenarios': self.test_results['smart_greenhouse']
                }
            },
            'verification_criteria': {
                'autonomous_vehicle': {
                    'description': '基于超声波测距的自动避障小车控制',
                    'required_actions': [
                        '距离≥30cm: 正常前进',
                        '20cm≤距离<30cm: 减速并准备转向',
                        '距离<20cm: 紧急停止并避障转向'
                    ]
                },
                'smart_greenhouse': {
                    'description': '基于温湿度的智能温室环境控制',
                    'required_actions': [
                        '温度>28℃: 启动通风扇',
                        '温度<18℃: 启动加热器',
                        '湿度<40%: 启动加湿器',
                        '湿度>80%: 启动除湿器'
                    ]
                }
            }
        }
        
        return report
    
    def save_report(self, report: Dict):
        """保存验证报告
        
        Args:
            report: 验证报告字典
        """
        # 创建报告目录
        report_dir = 'outputs/验证报告'
        os.makedirs(report_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = os.path.join(report_dir, f'闭环控制验证_{timestamp}.json')
        
        # 保存为JSON
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"验证报告已保存: {report_file}")
        
        # 同时保存为文本格式
        txt_file = os.path.join(report_dir, f'闭环控制验证_{timestamp}.txt')
        self._save_text_report(report, txt_file)
    
    def _save_text_report(self, report: Dict, file_path: str):
        """保存文本格式报告
        
        Args:
            report: 验证报告字典
            file_path: 文件路径
        """
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("数字孪生执行器控制系统闭环验证报告\n")
            f.write("=" * 60 + "\n\n")
            
            # 摘要
            summary = report['summary']
            f.write("验证摘要:\n")
            f.write(f"  总测试数: {summary['total_tests']}\n")
            f.write(f"  通过数: {summary['passed_tests']}\n")
            f.write(f"  失败数: {summary['failed_tests']}\n")
            f.write(f"  通过率: {summary['pass_rate']:.1f}%\n")
            f.write(f"  开始时间: {summary['start_time']}\n")
            f.write(f"  结束时间: {summary['end_time']}\n\n")
            
            # 详细结果 - 自动避障小车
            f.write("-" * 40 + "\n")
            f.write("自动避障小车场景验证结果:\n")
            f.write("-" * 40 + "\n")
            
            vehicle_results = report['detailed_results']['autonomous_vehicle']
            for i, scenario in enumerate(vehicle_results['scenarios']):
                f.write(f"\n场景 {i+1}:\n")
                f.write(f"  距离: {scenario['sensor_data']['distance']}cm\n")
                f.write(f"  生成指令: {scenario['commands']}\n")
                f.write(f"  状态: {'通过' if scenario['passed'] else '失败'}\n")
            
            # 详细结果 - 智能温室
            f.write("\n" + "-" * 40 + "\n")
            f.write("智能温室场景验证结果:\n")
            f.write("-" * 40 + "\n")
            
            greenhouse_results = report['detailed_results']['smart_greenhouse']
            for i, scenario in enumerate(greenhouse_results['scenarios']):
                f.write(f"\n场景 {i+1}:\n")
                f.write(f"  温度: {scenario['sensor_data']['temperature']}℃\n")
                f.write(f"  湿度: {scenario['sensor_data']['humidity']}%\n")
                f.write(f"  生成指令: {scenario['commands']}\n")
                f.write(f"  状态: {'通过' if scenario['passed'] else '失败'}\n")
            
            # 验证标准
            f.write("\n" + "=" * 60 + "\n")
            f.write("验证标准\n")
            f.write("=" * 60 + "\n\n")
            
            for scenario_name, criteria in report['verification_criteria'].items():
                f.write(f"{scenario_name}:\n")
                f.write(f"  描述: {criteria['description']}\n")
                f.write("  要求动作:\n")
                for action in criteria['required_actions']:
                    f.write(f"    • {action}\n")
                f.write("\n")
    
    def print_summary(self):
        """打印验证摘要"""
        summary = self.stats
        
        print("\n" + "=" * 60)
        print("闭环控制场景验证摘要")
        print("=" * 60)
        
        print(f"\n总体统计:")
        print(f"  总测试数: {summary['total_tests']}")
        print(f"  通过数: {summary['passed_tests']}")
        print(f"  失败数: {summary['failed_tests']}")
        
        pass_rate = (summary['passed_tests'] / summary['total_tests'] * 100) if summary['total_tests'] > 0 else 0
        print(f"  通过率: {pass_rate:.1f}%")
        
        print(f"\n按场景统计:")
        
        # 自动避障小车
        vehicle_results = self.test_results['autonomous_vehicle']
        vehicle_passed = sum(1 for r in vehicle_results if r['passed'])
        vehicle_total = len(vehicle_results)
        vehicle_rate = (vehicle_passed / vehicle_total * 100) if vehicle_total > 0 else 0
        
        print(f"  自动避障小车: {vehicle_passed}/{vehicle_total} ({vehicle_rate:.1f}%)")
        
        # 智能温室
        greenhouse_results = self.test_results['smart_greenhouse']
        greenhouse_passed = sum(1 for r in greenhouse_results if r['passed'])
        greenhouse_total = len(greenhouse_results)
        greenhouse_rate = (greenhouse_passed / greenhouse_total * 100) if greenhouse_total > 0 else 0
        
        print(f"  智能温室: {greenhouse_passed}/{greenhouse_total} ({greenhouse_rate:.1f}%)")
        
        print(f"\n时间信息:")
        print(f"  开始时间: {summary['start_time']}")
        print(f"  结束时间: {summary['end_time']}")
        
        # 总体评价
        print(f"\n总体评价:")
        if pass_rate >= 90:
            print(f"  ✓ 优秀 - 系统闭环控制功能验证通过")
        elif pass_rate >= 70:
            print(f"  ⚠ 良好 - 主要功能验证通过，部分边缘情况需优化")
        else:
            print(f"  ✗ 需改进 - 关键功能验证未通过，需重新设计")
        
        print("\n详细报告已保存至 outputs/验证报告/ 目录")
        print("=" * 60)

# 测试函数
def test_validation():
    """测试验证功能"""
    print("测试闭环控制场景验证...")
    
    # 创建验证器
    validator = ClosedLoopValidator()
    
    # 运行验证
    report = validator.run_validation()
    
    print("\n测试完成")
    return report

# 主程序入口
def main():
    """主函数"""
    print("=" * 60)
    print("数字孪生执行器控制系统闭环验证")
    print("=" * 60)
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/validation.log'),
            logging.StreamHandler()
        ]
    )
    
    # 运行验证
    validator = ClosedLoopValidator()
    report = validator.run_validation()
    
    # 返回退出码（用于自动化测试）
    if report['summary']['pass_rate'] >= 70:
        return 0  # 成功
    else:
        return 1  # 失败

if __name__ == "__main__":
    sys.exit(main())