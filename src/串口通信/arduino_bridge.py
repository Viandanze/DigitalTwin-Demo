#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arduino数字孪生通信模块
文件名: arduino_bridge.py
版本: v1.0
创建时间: 2026-04-11
描述: 树莓派与Arduino之间的串口通信封装
      支持传感器数据接收、执行器控制指令发送
"""

import serial
import serial.tools.list_ports
import json
import time
import threading
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class SensorData:
    """传感器数据结构"""
    humidity: float = -1.0
    temp_dht: float = -1.0
    temp_bmp: float = -1.0
    pressure: float = -1.0
    distance: int = -1
    light: int = -1
    timestamp: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "humidity": self.humidity,
            "temp_dht": self.temp_dht,
            "temp_bmp": self.temp_bmp,
            "pressure": self.pressure,
            "distance": self.distance,
            "light": self.light,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SensorData':
        return cls(
            humidity=data.get("humidity", -1.0),
            temp_dht=data.get("temp_dht", -1.0),
            temp_bmp=data.get("temp_bmp", -1.0),
            pressure=data.get("pressure", -1.0),
            distance=data.get("distance", -1),
            light=data.get("light", -1),
            timestamp=data.get("timestamp", 0)
        )


@dataclass
class ActuatorState:
    """执行器状态"""
    motor_speed: int = 0
    motor_direction: int = 0  # 0=停止, 1=正转, 2=反转
    servo_angle: int = 90
    uptime_ms: int = 0


class ArduinoBridge:
    """
    Arduino数字孪生桥接器
    
    功能：
    1. 自动检测并连接Arduino串口
    2. 接收并解析传感器数据
    3. 发送执行器控制指令
    4. 心跳检测与自动重连
    5. 异步数据处理（后台线程）
    """
    
    # 串口配置
    DEFAULT_BAUD_RATE = 115200
    DEFAULT_TIMEOUT = 1.0
    RECONNECT_DELAY = 3.0  # 重连延迟(秒)
    PING_INTERVAL = 5.0    # 心跳间隔(秒)
    
    def __init__(self, 
                 port: Optional[str] = None,
                 baud_rate: int = DEFAULT_BAUD_RATE,
                 timeout: float = DEFAULT_TIMEOUT,
                 auto_detect: bool = True):
        """
        初始化桥接器
        
        参数：
            port: 串口路径（如 /dev/ttyUSB0），None则自动检测
            baud_rate: 波特率
            timeout: 读取超时
            auto_detect: 是否自动检测Arduino端口
        """
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.auto_detect = auto_detect
        
        self.serial: Optional[serial.Serial] = None
        self.state = ConnectionState.DISCONNECTED
        
        # 数据回调
        self.sensor_callback: Optional[Callable[[SensorData], None]] = None
        self.status_callback: Optional[Callable[[Dict], None]] = None
        self.error_callback: Optional[Callable[[str], None]] = None
        
        # 异步处理
        self._running = False
        self._read_thread: Optional[threading.Thread] = None
        self._data_queue: Queue = Queue()
        
        # 执行器状态
        self.actuator_state = ActuatorState()
        
        # 统计信息
        self.stats = {
            "bytes_sent": 0,
            "bytes_received": 0,
            "sensor_readings": 0,
            "errors": 0,
            "last_ping": 0,
            "last_pong": 0,
            "connection_attempts": 0
        }
    
    # =========================================================================
    # 连接管理
    # =========================================================================
    
    def find_arduino_port(self) -> Optional[str]:
        """自动检测Arduino串口"""
        ports = list(serial.tools.list_ports.comports())
        
        for port in ports:
            # Arduino通常使用这些VID/PID
            if port.vid is not None:
                vid = port.vid
                pid = port.pid if port.pid else 0
                
                # 常见Arduino VID
                known_arduino_vids = [
                    0x2341,  # Arduino (official)
                    0x2A03,  # Arduino (alternate VID)
                    0x1A86,  # CH340 (clone)
                    0x0403,  # FTDI
                    0x10C4,  # CP2102
                ]
                
                if vid in known_arduino_vids:
                    logger.info(f"找到Arduino设备: {port.device} ({port.description})")
                    return port.device
        
        # 如果没有VID信息，尝试通过描述匹配
        for port in ports:
            desc = port.description.lower() if port.description else ""
            if any(keyword in desc for keyword in ["arduino", "ch340", "ch341", "usb serial"]):
                logger.info(f"通过描述找到设备: {port.device} ({port.description})")
                return port.device
        
        return None
    
    def connect(self, port: Optional[str] = None) -> bool:
        """
        连接到Arduino
        
        参数：
            port: 串口路径，None则使用初始化时的值或自动检测
            
        返回：
            是否连接成功
        """
        if self.state == ConnectionState.CONNECTED:
            logger.warning("已连接到Arduino")
            return True
        
        # 确定端口
        target_port = port or self.port
        if target_port is None:
            if self.auto_detect:
                target_port = self.find_arduino_port()
                if target_port is None:
                    logger.error("未找到Arduino设备")
                    self.state = ConnectionState.ERROR
                    return False
            else:
                logger.error("未指定串口且未启用自动检测")
                return False
        
        self.state = ConnectionState.CONNECTING
        self.stats["connection_attempts"] += 1
        
        try:
            self.serial = serial.Serial(
                port=target_port,
                baudrate=self.baud_rate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            # 等待Arduino初始化
            time.sleep(2)
            self.serial.reset_input_buffer()
            
            # 发送初始化命令
            self._send_command("GET_STATUS")
            time.sleep(0.5)
            
            self.port = target_port
            self.state = ConnectionState.CONNECTED
            logger.info(f"成功连接到 {target_port}")
            
            # 启动读取线程
            self._start_reading()
            
            return True
            
        except serial.SerialException as e:
            logger.error(f"串口连接失败: {e}")
            self.state = ConnectionState.ERROR
            return False
        except Exception as e:
            logger.error(f"连接异常: {e}")
            self.state = ConnectionState.ERROR
            return False
    
    def disconnect(self):
        """断开连接"""
        self._running = False
        
        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join(timeout=2.0)
        
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info("已断开Arduino连接")
        
        self.state = ConnectionState.DISCONNECTED
    
    def reconnect(self) -> bool:
        """重新连接"""
        logger.info("尝试重新连接...")
        self.disconnect()
        time.sleep(self.RECONNECT_DELAY)
        return self.connect()
    
    # =========================================================================
    # 数据读取（后台线程）
    # =========================================================================
    
    def _start_reading(self):
        """启动后台读取线程"""
        self._running = True
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()
        logger.info("启动数据读取线程")
    
    def _read_loop(self):
        """后台读取循环"""
        last_ping_time = time.time()
        
        while self._running and self.serial and self.serial.is_open:
            try:
                # 定期发送心跳
                current_time = time.time()
                if current_time - last_ping_time >= self.PING_INTERVAL:
                    self._send_command("PING")
                    self.stats["last_ping"] = int(current_time * 1000)
                    last_ping_time = current_time
                
                # 读取数据
                if self.serial.in_waiting > 0:
                    line = self.serial.readline().decode('utf-8').strip()
                    self.stats["bytes_received"] += len(line)
                    
                    if line:
                        self._parse_and_handle(line)
                
                time.sleep(0.01)  # 避免CPU占用过高
                
            except serial.SerialException as e:
                logger.error(f"串口读取错误: {e}")
                self.stats["errors"] += 1
                break
            except UnicodeDecodeError as e:
                logger.warning(f"数据解码错误: {e}")
                continue
            except Exception as e:
                logger.error(f"读取异常: {e}")
                self.stats["errors"] += 1
                continue
        
        # 连接断开处理
        if self._running:
            logger.warning("读取线程退出，尝试重连...")
            self.state = ConnectionState.DISCONNECTED
            # 自动重连
            threading.Thread(target=self._auto_reconnect, daemon=True).start()
    
    def _auto_reconnect(self):
        """自动重连（后台线程）"""
        while self._running and self.state != ConnectionState.CONNECTED:
            if self.reconnect():
                break
            time.sleep(self.RECONNECT_DELAY)
    
    def _parse_and_handle(self, line: str):
        """解析并处理接收到的数据"""
        if not line.startswith('{'):
            logger.debug(f"收到非JSON数据: {line}")
            return
        
        try:
            data = json.loads(line)
            msg_type = data.get("type", "")
            
            if msg_type == "sensor":
                # 传感器数据
                sensor_data = SensorData.from_dict(data.get("data", {}))
                self.stats["sensor_readings"] += 1
                
                if self.sensor_callback:
                    self.sensor_callback(sensor_data)
                    
            elif msg_type == "pong":
                # 心跳响应
                self.stats["last_pong"] = data.get("timestamp", 0)
                logger.debug(f"收到PONG: {data.get('timestamp')}")
                
            elif msg_type == "status":
                # 设备状态
                self._update_actuator_state(data)
                
                if self.status_callback:
                    self.status_callback(data)
                    
            elif msg_type == "motor" or msg_type == "servo":
                # 执行器确认
                logger.debug(f"执行器响应: {data}")
                
            elif msg_type == "error":
                # 错误信息
                logger.error(f"Arduino错误: {data.get('msg', 'Unknown')}")
                if self.error_callback:
                    self.error_callback(data.get("msg", "Unknown"))
                    
            elif msg_type == "system":
                # 系统消息
                logger.info(f"Arduino系统: {data.get('msg', '')}")
                
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}, 原始数据: {line}")
    
    def _update_actuator_state(self, data: Dict):
        """更新执行器状态"""
        if "motor" in data:
            self.actuator_state.motor_speed = data["motor"].get("speed", 0)
            self.actuator_state.motor_direction = data["motor"].get("direction", 0)
        if "servo" in data:
            self.actuator_state.servo_angle = data["servo"].get("angle", 90)
        if "uptime" in data:
            self.actuator_state.uptime_ms = data["uptime"]
    
    # =========================================================================
    # 指令发送
    # =========================================================================
    
    def _send_command(self, cmd: str) -> bool:
        """发送指令到Arduino"""
        if not self.serial or not self.serial.is_open:
            logger.warning("串口未打开，无法发送指令")
            return False
        
        try:
            cmd_bytes = (cmd + '\n').encode('utf-8')
            self.serial.write(cmd_bytes)
            self.stats["bytes_sent"] += len(cmd_bytes)
            logger.debug(f"发送指令: {cmd}")
            return True
        except serial.SerialException as e:
            logger.error(f"发送失败: {e}")
            self.stats["errors"] += 1
            return False
    
    def ping(self) -> bool:
        """发送心跳检测"""
        return self._send_command("PING")
    
    def get_status(self) -> bool:
        """获取设备状态"""
        return self._send_command("GET_STATUS")
    
    def set_motor(self, speed: int, direction: int) -> bool:
        """
        设置电机速度
        
        参数：
            speed: 速度 0-255
            direction: 方向 0=停止, 1=正转, 2=反转
        """
        cmd = f"SET_MOTOR {speed} {direction}"
        return self._send_command(cmd)
    
    def set_servo(self, angle: int) -> bool:
        """
        设置舵机角度
        
        参数：
            angle: 角度 0-180
        """
        cmd = f"SET_SERVO {angle}"
        return self._send_command(cmd)
    
    # =========================================================================
    # 回调设置
    # =========================================================================
    
    def on_sensor_data(self, callback: Callable[[SensorData], None]):
        """设置传感器数据回调"""
        self.sensor_callback = callback
    
    def on_status_update(self, callback: Callable[[Dict], None]):
        """设置状态更新回调"""
        self.status_callback = callback
    
    def on_error(self, callback: Callable[[str], None]):
        """设置错误回调"""
        self.error_callback = callback
    
    # =========================================================================
    # 上下文管理
    # =========================================================================
    
    def __enter__(self):
        """上下文入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文退出"""
        self.disconnect()
        return False
    
    # =========================================================================
    # 状态与统计
    # =========================================================================
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self.state == ConnectionState.CONNECTED
    
    def get_stats(self) -> Dict[str, Any]:
        """获取通信统计"""
        return self.stats.copy()
    
    def get_actuator_state(self) -> ActuatorState:
        """获取执行器状态"""
        return self.actuator_state
    
    def __repr__(self) -> str:
        return f"ArduinoBridge(port={self.port}, state={self.state.value})"


# ============================================================================
# 使用示例
# ============================================================================

def example_basic_usage():
    """基础使用示例"""
    with ArduinoBridge() as bridge:
        if not bridge.is_connected:
            print("连接失败!")
            return
        
        # 设置传感器回调
        def on_sensor(data: SensorData):
            print(f"传感器数据: 温度={data.temp_dht}°C, 湿度={data.humidity}%, 距离={data.distance}cm")
        
        bridge.on_sensor_data(on_sensor)
        
        # 控制电机
        bridge.set_motor(128, 1)  # 半速正转
        time.sleep(2)
        bridge.set_motor(0, 0)    # 停止
        
        # 控制舵机
        bridge.set_servo(90)     # 居中
        time.sleep(1)
        bridge.set_servo(0)       # 左转
        time.sleep(1)
        bridge.set_servo(180)     # 右转
        
        # 运行一段时间
        time.sleep(10)


def example_cli():
    """命令行交互示例"""
    bridge = ArduinoBridge(auto_detect=True)
    
    if not bridge.connect():
        print("无法连接到Arduino")
        return
    
    print("Arduino桥接器已启动，输入命令（help查看帮助）:")
    
    while True:
        try:
            cmd = input("\n> ").strip()
            
            if cmd == "help":
                print("可用命令:")
                print("  ping    - 心跳检测")
                print("  status  - 获取状态")
                print("  motor <speed> <dir> - 设置电机 (speed:0-255, dir:0-2)")
                print("  servo <angle>       - 设置舵机 (angle:0-180)")
                print("  stats  - 查看统计")
                print("  quit   - 退出")
                
            elif cmd == "ping":
                bridge.ping()
                
            elif cmd == "status":
                bridge.get_status()
                time.sleep(0.5)
                print(f"执行器状态: {bridge.get_actuator_state()}")
                
            elif cmd.startswith("motor"):
                parts = cmd.split()
                if len(parts) >= 3:
                    speed = int(parts[1])
                    direction = int(parts[2])
                    bridge.set_motor(speed, direction)
                else:
                    print("用法: motor <speed> <direction>")
                    
            elif cmd.startswith("servo"):
                parts = cmd.split()
                if len(parts) >= 2:
                    angle = int(parts[1])
                    bridge.set_servo(angle)
                else:
                    print("用法: servo <angle>")
                    
            elif cmd == "stats":
                print(f"统计: {bridge.get_stats()}")
                
            elif cmd == "quit":
                break
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"错误: {e}")
    
    bridge.disconnect()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        example_cli()
    else:
        print("运行示例代码...")
        example_basic_usage()
