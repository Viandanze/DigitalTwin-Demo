#!/usr/bin/env python3
"""
控制引擎模块
功能：基于传感器数据生成控制决策，支持多场景控制逻辑
作者：数字孪生学习项目
日期：2026年4月3日
"""

import time
import random
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging
import math

logger = logging.getLogger(__name__)

class ControlEngine:
    """控制决策引擎"""
    
    def __init__(self, control_config: Dict):
        """初始化控制引擎
        
        Args:
            control_config: 控制配置字典
        """
        self.config = control_config
        self.last_commands = []
        self.system_state = 'normal'  # normal, warning, emergency
        self.control_modes = {
            'autonomous_vehicle': self._vehicle_control_logic,
            'smart_greenhouse': self._greenhouse_control_logic
        }
        
        # 状态历史
        self.command_history = []
        self.max_history = 50
        
        logger.info("控制引擎初始化完成")
    
    def decide_vehicle_control(self, sensor_data: Dict) -> List[str]:
        """自动避障小车控制决策
        
        Args:
            sensor_data: 传感器数据字典
            
        Returns:
            控制指令列表
        """
        return self._execute_control_logic('autonomous_vehicle', sensor_data)
    
    def decide_greenhouse_control(self, sensor_data: Dict) -> List[str]:
        """智能温室控制决策
        
        Args:
            sensor_data: 传感器数据字典
            
        Returns:
            控制指令列表
        """
        return self._execute_control_logic('smart_greenhouse', sensor_data)
    
    def _execute_control_logic(self, mode: str, sensor_data: Dict) -> List[str]:
        """执行指定模式的控制逻辑
        
        Args:
            mode: 控制模式
            sensor_data: 传感器数据
            
        Returns:
            控制指令列表
        """
        if mode not in self.control_modes:
            logger.error(f"未知控制模式: {mode}")
            return []
        
        try:
            # 执行控制逻辑
            commands = self.control_modes[mode](sensor_data)
            
            # 记录命令
            self._record_commands(commands, mode)
            
            # 更新系统状态
            self._update_system_state(sensor_data)
            
            return commands
            
        except Exception as e:
            logger.error(f"控制逻辑执行错误: {e}")
            return self._get_safe_commands()
    
    def _vehicle_control_logic(self, sensor_data: Dict) -> List[str]:
        """自动避障小车控制逻辑
        
        基于超声波测距实现自动避障：
        1. 距离 > 安全距离：正常前进
        2. 距离 < 安全距离：停止并转向避障
        3. 距离 < 紧急距离：紧急停止
        
        Args:
            sensor_data: 传感器数据
            
        Returns:
            控制指令列表
        """
        commands = []
        
        # 获取距离数据
        distance = sensor_data.get('distance', 100.0)
        temperature = sensor_data.get('temperature', 25.0)
        
        # 计算温度补偿后的安全距离
        safe_distance = self.config.get('emergency_stop_distance', 20.0)
        critical_distance = safe_distance * 0.5  # 紧急距离为安全距离的一半
        
        # 应用温度补偿（声速随温度变化）
        # 声速公式: v = 331.4 + 0.6 * T (m/s)
        sound_speed_compensation = 1.0 + (temperature - 25.0) * 0.0018  # 简化补偿
        compensated_distance = distance * sound_speed_compensation
        
        logger.debug(f"车辆控制 - 原始距离: {distance:.1f}cm, 补偿后: {compensated_distance:.1f}cm")
        
        # 决策逻辑
        if compensated_distance >= safe_distance:
            # 正常前进：速度与距离成正比
            speed = int(min(80, compensated_distance))
            commands.append(f"MOTOR:0:{speed}")
            logger.info(f"安全距离 ({compensated_distance:.1f}cm ≥ {safe_distance}cm)，正常前进，速度{speed}%")
        
        elif compensated_distance >= critical_distance:
            # 接近障碍物：减速并准备转向
            speed = int(max(20, compensated_distance - critical_distance))
            commands.append(f"MOTOR:0:{speed}")
            
            # 轻微转向（舵机角度与距离成反比）
            steer_angle = int(45 + (safe_distance - compensated_distance) * 2)
            steer_angle = max(30, min(150, steer_angle))
            commands.append(f"SERVO:{steer_angle}")
            
            logger.warning(f"接近障碍物 ({compensated_distance:.1f}cm)，减速至{speed}%，转向角度{steer_angle}°")
        
        else:
            # 紧急情况：停止并全力转向
            commands.append("MOTOR:0:0")
            commands.append("SERVO:135")  # 大角度转向
            
            # 记录紧急状态
            self.system_state = 'emergency'
            logger.error(f"紧急停止！距离过近: {compensated_distance:.1f}cm < {critical_distance}cm")
        
        # 根据温度调整风扇（模拟散热）
        if temperature > 25.0:
            fan_speed = int(min(100, (temperature - 25.0) * 10))
            commands.append(f"MOTOR:1:{fan_speed}")
            logger.debug(f"温度 {temperature:.1f}℃，启动散热风扇，速度{fan_speed}%")
        
        return commands
    
    def _greenhouse_control_logic(self, sensor_data: Dict) -> List[str]:
        """智能温室控制逻辑
        
        基于温湿度数据实现环境控制：
        1. 温度控制：通风扇（降温）、加热器（升温）
        2. 湿度控制：加湿器（增湿）、除湿器（降湿）
        3. 光照控制：遮阳帘调节
        
        Args:
            sensor_data: 传感器数据
            
        Returns:
            控制指令列表
        """
        commands = []
        
        # 获取传感器数据
        temperature = sensor_data.get('temperature', 25.0)
        humidity = sensor_data.get('humidity', 60.0)
        light = sensor_data.get('light', 50.0)
        pressure = sensor_data.get('pressure', 1013.0)
        
        logger.debug(f"温室控制 - 温度: {temperature:.1f}℃，湿度: {humidity:.1f}%，光照: {light:.1f}%")
        
        # 温度控制逻辑
        temp_threshold_high = self.config.get('temperature_threshold_high', 28.0)
        temp_threshold_low = self.config.get('temperature_threshold_low', 18.0)
        
        if temperature > temp_threshold_high:
            # 温度过高：启动通风扇
            fan_speed = int(min(100, (temperature - temp_threshold_high) * 20))
            commands.append(f"MOTOR:0:{fan_speed}")
            logger.info(f"温度过高 ({temperature:.1f}℃ > {temp_threshold_high}℃)，启动通风扇，速度{fan_speed}%")
            
            # 同时打开遮阳帘（减小光照）
            shade_position = int(max(0, 100 - (temperature - 25) * 10))
            commands.append(f"SERVO:{shade_position}")
            logger.debug(f"调节遮阳帘至 {shade_position}% 开度")
        
        elif temperature < temp_threshold_low:
            # 温度过低：启动加热器（模拟）
            heater_power = int(min(100, (temp_threshold_low - temperature) * 15))
            commands.append(f"MOTOR:1:{heater_power}")
            logger.info(f"温度过低 ({temperature:.1f}℃ < {temp_threshold_low}℃)，启动加热器，功率{heater_power}%")
        
        else:
            # 温度适宜：维持最小通风
            commands.append("MOTOR:0:20")
            logger.debug(f"温度适宜 ({temperature:.1f}℃)，维持最小通风")
        
        # 湿度控制逻辑
        humidity_threshold_high = self.config.get('humidity_threshold_high', 80.0)
        humidity_threshold_low = self.config.get('humidity_threshold_low', 40.0)
        
        if humidity > humidity_threshold_high:
            # 湿度过高：启动除湿器（模拟）
            dehumidifier_power = int(min(100, (humidity - humidity_threshold_high) * 5))
            commands.append(f"MOTOR:2:{dehumidifier_power}")
            logger.info(f"湿度过高 ({humidity:.1f}% > {humidity_threshold_high}%)，启动除湿器，功率{dehumidifier_power}%")
        
        elif humidity < humidity_threshold_low:
            # 湿度过低：启动加湿器（舵机控制阀门）
            valve_position = int(min(180, (humidity_threshold_low - humidity) * 3))
            commands.append(f"SERVO:{valve_position}")
            logger.info(f"湿度过低 ({humidity:.1f}% < {humidity_threshold_low}%)，调节加湿器阀门至{valve_position}°")
        
        # 光照控制（简化）
        if light > 80 and temperature > 25:
            # 光照过强且温度偏高：关闭部分遮阳帘
            shade_close = int(30 + (light - 80) * 2)
            commands.append(f"SERVO:{shade_close}")
            logger.debug(f"光照过强 ({light:.1f}%)，调节遮阳帘至{shade_close}°")
        
        # 气压变化预警
        pressure_history = []  # 模拟历史数据
        if len(pressure_history) > 10:
            pressure_trend = pressure - sum(pressure_history[-10:]) / 10
            if abs(pressure_trend) > 5.0:  # 气压快速变化
                logger.warning(f"气压快速变化: {pressure_trend:.1f}hPa/10次采样，可能预示天气变化")
        
        return commands
    
    def _record_commands(self, commands: List[str], mode: str):
        """记录控制命令
        
        Args:
            commands: 控制指令列表
            mode: 控制模式
        """
        if commands:
            record = {
                'timestamp': datetime.now().isoformat(),
                'mode': mode,
                'commands': commands.copy(),
                'system_state': self.system_state
            }
            
            self.command_history.append(record)
            
            # 保持历史记录长度
            if len(self.command_history) > self.max_history:
                self.command_history.pop(0)
    
    def _update_system_state(self, sensor_data: Dict):
        """更新系统状态
        
        Args:
            sensor_data: 传感器数据
        """
        # 检查关键传感器状态
        critical_sensors = ['distance', 'temperature']
        warning_count = 0
        
        for sensor in critical_sensors:
            value = sensor_data.get(sensor)
            if value is None:
                warning_count += 1
                logger.warning(f"关键传感器 {sensor} 数据无效")
        
        # 根据异常数量更新状态
        if warning_count >= 2:
            self.system_state = 'emergency'
        elif warning_count >= 1:
            self.system_state = 'warning'
        else:
            self.system_state = 'normal'
    
    def _get_safe_commands(self) -> List[str]:
        """获取安全状态命令（故障安全模式）
        
        Returns:
            安全指令列表
        """
        safe_commands = [
            "MOTOR:0:0",      # 停止所有电机
            "SERVO:90",       # 舵机回到中立位
            "STEPPER:0:0"     # 停止步进电机
        ]
        
        logger.info("进入故障安全模式，发送安全停止指令")
        return safe_commands
    
    def get_control_history(self, count: int = 10) -> List[Dict]:
        """获取控制历史
        
        Args:
            count: 返回的记录数量
            
        Returns:
            控制历史记录列表
        """
        start_idx = max(0, len(self.command_history) - count)
        return self.command_history[start_idx:].copy()
    
    def get_system_status(self) -> Dict:
        """获取系统状态
        
        Returns:
            系统状态字典
        """
        return {
            'system_state': self.system_state,
            'last_command_count': len(self.last_commands),
            'history_length': len(self.command_history),
            'available_modes': list(self.control_modes.keys())
        }

# 高级控制算法
class PIDController:
    """PID控制器"""
    
    def __init__(self, kp: float, ki: float, kd: float):
        """初始化PID控制器
        
        Args:
            kp: 比例系数
            ki: 积分系数
            kd: 微分系数
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        
        # 状态变量
        self.last_error = 0.0
        self.integral = 0.0
        self.last_time = time.time()
        
        # 限制
        self.integral_limit = 100.0
        self.output_limit = 100.0
        
        logger.debug(f"PID控制器初始化: Kp={kp}, Ki={ki}, Kd={kd}")
    
    def compute(self, setpoint: float, measured: float) -> float:
        """计算控制输出
        
        Args:
            setpoint: 目标值
            measured: 测量值
            
        Returns:
            控制输出
        """
        current_time = time.time()
        dt = current_time - self.last_time
        
        if dt <= 0:
            dt = 0.01  # 最小时间间隔
        
        # 计算误差
        error = setpoint - measured
        
        # 比例项
        proportional = self.kp * error
        
        # 积分项（带抗饱和）
        self.integral += error * dt
        # 积分限幅
        if abs(self.integral) > self.integral_limit:
            self.integral = math.copysign(self.integral_limit, self.integral)
        integral = self.ki * self.integral
        
        # 微分项
        derivative = 0.0
        if dt > 0:
            derivative = self.kd * (error - self.last_error) / dt
        
        # 计算输出
        output = proportional + integral + derivative
        
        # 输出限幅
        if abs(output) > self.output_limit:
            output = math.copysign(self.output_limit, output)
        
        # 更新状态
        self.last_error = error
        self.last_time = current_time
        
        logger.debug(f"PID计算: 目标={setpoint}, 测量={measured}, 误差={error:.2f}, 输出={output:.2f}")
        
        return output
    
    def reset(self):
        """重置控制器状态"""
        self.last_error = 0.0
        self.integral = 0.0
        self.last_time = time.time()
        logger.debug("PID控制器已重置")

class FuzzyLogicController:
    """模糊逻辑控制器（简化实现）"""
    
    def __init__(self, rules: List[Dict]):
        """初始化模糊逻辑控制器
        
        Args:
            rules: 模糊规则列表
        """
        self.rules = rules
        
        # 隶属度函数定义（三角型）
        self.membership_functions = {
            'very_low': lambda x: max(0, min(1, (20 - x) / 10)),
            'low': lambda x: max(0, min((x - 10) / 10, (30 - x) / 10)),
            'medium': lambda x: max(0, min((x - 20) / 10, (40 - x) / 10)),
            'high': lambda x: max(0, min((x - 30) / 10, (50 - x) / 10)),
            'very_high': lambda x: max(0, min((x - 40) / 10, 1))
        }
        
        logger.debug(f"模糊逻辑控制器初始化: {len(rules)} 条规则")
    
    def infer(self, inputs: Dict[str, float]) -> Dict[str, float]:
        """执行模糊推理
        
        Args:
            inputs: 输入变量字典 {变量名: 值}
            
        Returns:
            输出变量字典 {变量名: 隶属度}
        """
        outputs = {}
        
        for rule in self.rules:
            # 计算规则前提的隶属度
            premise_strength = 1.0
            
            for var_name, fuzzy_set in rule.get('if', {}).items():
                if var_name in inputs:
                    value = inputs[var_name]
                    mf = self.membership_functions.get(fuzzy_set)
                    if mf:
                        premise_strength = min(premise_strength, mf(value))
            
            # 应用规则结论
            for var_name, fuzzy_set in rule.get('then', {}).items():
                if var_name not in outputs:
                    outputs[var_name] = {}
                
                outputs[var_name][fuzzy_set] = max(
                    outputs[var_name].get(fuzzy_set, 0),
                    premise_strength
                )
        
        # 去模糊化（重心法）
        crisp_outputs = {}
        
        for var_name, fuzzy_sets in outputs.items():
            numerator = 0.0
            denominator = 0.0
            
            for fuzzy_set, membership in fuzzy_sets.items():
                # 获取模糊集的代表值（中心）
                centroid = self._get_centroid(fuzzy_set)
                
                numerator += centroid * membership
                denominator += membership
            
            if denominator > 0:
                crisp_outputs[var_name] = numerator / denominator
            else:
                crisp_outputs[var_name] = 0.0
        
        logger.debug(f"模糊推理结果: 输入={inputs}, 输出={crisp_outputs}")
        
        return crisp_outputs
    
    def _get_centroid(self, fuzzy_set: str) -> float:
        """获取模糊集的重心（代表值）
        
        Args:
            fuzzy_set: 模糊集名称
            
        Returns:
            重心值
        """
        centroids = {
            'very_low': 10.0,
            'low': 20.0,
            'medium': 30.0,
            'high': 40.0,
            'very_high': 50.0
        }
        
        return centroids.get(fuzzy_set, 30.0)

# 测试函数
def test_control_engine():
    """测试控制引擎"""
    print("测试控制引擎...")
    
    # 创建配置
    control_config = {
        'decision_interval': 1.0,
        'emergency_stop_distance': 20.0,
        'temperature_threshold_high': 28.0,
        'temperature_threshold_low': 18.0,
        'humidity_threshold_high': 80.0,
        'humidity_threshold_low': 40.0
    }
    
    # 创建控制引擎
    engine = ControlEngine(control_config)
    
    # 测试车辆控制
    print("\n1. 测试自动避障小车控制:")
    test_sensor_data = {
        'distance': 15.0,  # 接近障碍物
        'temperature': 27.0,
        'humidity': 65.0
    }
    
    commands = engine.decide_vehicle_control(test_sensor_data)
    print(f"控制指令: {commands}")
    
    # 测试温室控制
    print("\n2. 测试智能温室控制:")
    test_sensor_data = {
        'temperature': 30.0,  # 温度过高
        'humidity': 35.0,     # 湿度过低
        'light': 85.0,
        'pressure': 1005.0
    }
    
    commands = engine.decide_greenhouse_control(test_sensor_data)
    print(f"控制指令: {commands}")
    
    # 测试PID控制器
    print("\n3. 测试PID控制器:")
    pid = PIDController(kp=2.0, ki=0.5, kd=1.0)
    
    setpoint = 25.0
    measured = 20.0
    
    for i in range(5):
        output = pid.compute(setpoint, measured)
        measured += output * 0.1  # 模拟系统响应
        print(f"迭代 {i+1}: 目标={setpoint}, 测量={measured:.2f}, 输出={output:.2f}")
    
    # 测试模糊逻辑控制器
    print("\n4. 测试模糊逻辑控制器:")
    rules = [
        {
            'if': {'temperature': 'very_high', 'humidity': 'low'},
            'then': {'fan_speed': 'very_high', 'humidifier': 'high'}
        },
        {
            'if': {'temperature': 'medium', 'humidity': 'medium'},
            'then': {'fan_speed': 'low', 'humidifier': 'very_low'}
        }
    ]
    
    fuzzy = FuzzyLogicController(rules)
    inputs = {'temperature': 35.0, 'humidity': 30.0}
    outputs = fuzzy.infer(inputs)
    print(f"模糊推理: 输入={inputs}, 输出={outputs}")
    
    print("\n测试完成")

if __name__ == "__main__":
    test_control_engine()