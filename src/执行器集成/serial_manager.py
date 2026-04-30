#!/usr/bin/env python3
"""
串口通信管理器模块
功能：管理与Arduino的串口通信，包括指令发送、反馈接收、错误处理
作者：数字孪生学习项目
日期：2026年4月3日
"""

import time
import threading
import queue
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging

# 尝试导入pyserial，如果失败则使用模拟模式
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("警告: pyserial模块未安装，将使用模拟串口模式")

logger = logging.getLogger(__name__)

class SerialManager:
    """串口通信管理器"""
    
    def __init__(self, serial_config: Dict):
        """初始化串口管理器
        
        Args:
            serial_config: 串口配置字典
        """
        self.config = serial_config
        self.serial_port = None
        self.running = False
        self.connected = False
        
        # 通信队列
        self.command_queue = queue.Queue(maxsize=100)
        self.response_queue = queue.Queue(maxsize=100)
        
        # 统计信息
        self.stats = {
            'commands_sent': 0,
            'commands_failed': 0,
            'responses_received': 0,
            'bytes_sent': 0,
            'bytes_received': 0,
            'connection_attempts': 0,
            'last_connect_time': None,
            'last_error': None
        }
        
        # 线程
        self.send_thread = None
        self.receive_thread = None
        
        # 指令解析器
        self.parser = CommandParser()
        
        # 连接状态回调
        self.connection_callbacks = []
        
        logger.info("串口管理器初始化完成")
    
    def add_connection_callback(self, callback):
        """添加连接状态回调函数
        
        Args:
            callback: 回调函数，参数为(bool)连接状态
        """
        self.connection_callbacks.append(callback)
    
    def _notify_connection_change(self, connected: bool):
        """通知连接状态变化
        
        Args:
            connected: 是否连接
        """
        for callback in self.connection_callbacks:
            try:
                callback(connected)
            except Exception as e:
                logger.error(f"连接状态回调错误: {e}")
    
    def start(self):
        """启动串口管理器"""
        if self.running:
            return
        
        logger.info("启动串口管理器...")
        self.running = True
        
        # 尝试连接
        self._connect()
        
        # 启动发送线程
        self.send_thread = threading.Thread(target=self._send_loop, daemon=True)
        self.send_thread.start()
        
        # 启动接收线程
        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()
        
        logger.info("串口管理器启动完成")
    
    def stop(self):
        """停止串口管理器"""
        logger.info("停止串口管理器...")
        self.running = False
        
        # 停止线程
        if self.send_thread:
            self.send_thread.join(timeout=2.0)
        
        if self.receive_thread:
            self.receive_thread.join(timeout=2.0)
        
        # 关闭串口
        self._disconnect()
        
        logger.info("串口管理器已停止")
    
    def _connect(self):
        """连接到串口设备"""
        self.stats['connection_attempts'] += 1
        
        port = self.config.get('port', '/dev/ttyAMA0')
        baudrate = self.config.get('baudrate', 115200)
        timeout = self.config.get('timeout', 1.0)
        
        try:
            if SERIAL_AVAILABLE:
                # 真实串口连接
                self.serial_port = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    timeout=timeout
                )
                
                # 等待串口稳定
                time.sleep(0.5)
                
                self.connected = True
                self.stats['last_connect_time'] = datetime.now().isoformat()
                logger.info(f"串口连接成功: {port} @ {baudrate}bps")
                
            else:
                # 模拟模式
                self.serial_port = MockSerialPort(port, baudrate, timeout)
                self.connected = True
                self.stats['last_connect_time'] = datetime.now().isoformat()
                logger.info(f"模拟串口连接成功: {port} @ {baudrate}bps")
            
            # 通知连接状态变化
            self._notify_connection_change(True)
            
        except Exception as e:
            self.connected = False
            self.stats['last_error'] = str(e)
            logger.error(f"串口连接失败: {e}")
            
            # 通知连接状态变化
            self._notify_connection_change(False)
    
    def _disconnect(self):
        """断开串口连接"""
        if self.serial_port:
            try:
                self.serial_port.close()
                logger.info("串口已关闭")
            except Exception as e:
                logger.error(f"串口关闭错误: {e}")
            finally:
                self.serial_port = None
        
        if self.connected:
            self.connected = False
            # 通知连接状态变化
            self._notify_connection_change(False)
    
    def reconnect(self):
        """重新连接串口"""
        logger.info("尝试重新连接串口...")
        self._disconnect()
        time.sleep(1.0)  # 等待后重连
        self._connect()
    
    def is_connected(self) -> bool:
        """检查是否连接
        
        Returns:
            连接状态
        """
        return self.connected
    
    def _send_loop(self):
        """发送循环线程"""
        logger.info("串口发送线程启动")
        
        while self.running:
            try:
                # 从队列获取指令（非阻塞）
                try:
                    command = self.command_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # 发送指令
                success = self._send_command_impl(command)
                
                if success:
                    self.stats['commands_sent'] += 1
                    logger.debug(f"指令发送成功: {command}")
                else:
                    self.stats['commands_failed'] += 1
                    logger.warning(f"指令发送失败: {command}")
                    
                    # 失败后重试
                    if self.config.get('retry_count', 3) > 0:
                        self._retry_command(command)
                
                # 标记任务完成
                self.command_queue.task_done()
                
            except Exception as e:
                logger.error(f"发送循环错误: {e}")
                time.sleep(0.5)
        
        logger.info("串口发送线程结束")
    
    def _send_command_impl(self, command: str) -> bool:
        """发送指令实现
        
        Args:
            command: 指令字符串
            
        Returns:
            发送是否成功
        """
        if not self.connected or not self.serial_port:
            logger.warning("串口未连接，无法发送指令")
            return False
        
        try:
            # 添加换行符作为指令结束符
            full_command = command.strip() + '\n'
            bytes_sent = self.serial_port.write(full_command.encode('utf-8'))
            
            self.stats['bytes_sent'] += bytes_sent
            
            # 刷新缓冲区确保数据发送
            self.serial_port.flush()
            
            return True
            
        except Exception as e:
            self.stats['last_error'] = str(e)
            logger.error(f"指令发送错误: {e}")
            return False
    
    def _retry_command(self, command: str):
        """重试发送指令
        
        Args:
            command: 指令字符串
        """
        retry_count = self.config.get('retry_count', 3)
        retry_delay = self.config.get('retry_delay', 0.5)
        
        for attempt in range(retry_count):
            time.sleep(retry_delay)
            
            logger.info(f"重试指令 ({attempt+1}/{retry_count}): {command}")
            
            if self._send_command_impl(command):
                logger.info(f"指令重试成功: {command}")
                return
            
        logger.error(f"指令重试失败: {command}")
    
    def _receive_loop(self):
        """接收循环线程"""
        logger.info("串口接收线程启动")
        
        while self.running:
            try:
                if not self.connected or not self.serial_port:
                    time.sleep(1.0)
                    continue
                
                # 读取一行数据
                line = self._read_line()
                
                if line:
                    self.stats['responses_received'] += 1
                    self.stats['bytes_received'] += len(line.encode('utf-8'))
                    
                    # 解析响应
                    parsed = self.parser.parse_response(line)
                    
                    if parsed:
                        # 放入响应队列
                        try:
                            self.response_queue.put(parsed, timeout=0.1)
                            logger.debug(f"响应接收: {parsed}")
                        except queue.Full:
                            logger.warning("响应队列已满，丢弃响应")
                    
                    # 记录原始响应
                    logger.debug(f"原始响应: {line.strip()}")
                
                # 短暂休眠
                time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"接收循环错误: {e}")
                time.sleep(0.5)
        
        logger.info("串口接收线程结束")
    
    def _read_line(self) -> Optional[str]:
        """读取一行数据
        
        Returns:
            读取到的字符串，失败返回None
        """
        try:
            if hasattr(self.serial_port, 'readline'):
                line = self.serial_port.readline()
                
                if line:
                    return line.decode('utf-8', errors='ignore').strip()
            
            return None
            
        except Exception as e:
            logger.error(f"读取数据错误: {e}")
            return None
    
    def send_command(self, command: str) -> bool:
        """发送指令（外部调用接口）
        
        Args:
            command: 指令字符串
            
        Returns:
            是否成功加入发送队列
        """
        if not self.running:
            logger.warning("串口管理器未运行，无法发送指令")
            return False
        
        # 验证指令格式
        if not self.parser.validate_command(command):
            logger.error(f"指令格式无效: {command}")
            return False
        
        try:
            # 放入发送队列
            self.command_queue.put(command, timeout=0.5)
            return True
            
        except queue.Full:
            logger.error("指令队列已满，无法发送")
            return False
    
    def receive_feedback(self, timeout: float = 0.5) -> Optional[str]:
        """接收反馈（外部调用接口）
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            反馈字符串，超时返回None
        """
        try:
            feedback = self.response_queue.get(timeout=timeout)
            
            # 标记任务完成
            self.response_queue.task_done()
            
            return feedback
            
        except queue.Empty:
            return None
    
    def send_and_wait(self, command: str, timeout: float = 2.0) -> Optional[Dict]:
        """发送指令并等待响应
        
        Args:
            command: 指令字符串
            timeout: 超时时间（秒）
            
        Returns:
            解析后的响应字典，超时返回None
        """
        if not self.send_command(command):
            return None
        
        # 等待响应
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self.receive_feedback(timeout=0.1)
            
            if response:
                return response
            
            time.sleep(0.01)
        
        logger.warning(f"指令 {command} 响应超时")
        return None
    
    def get_stats(self) -> Dict:
        """获取通信统计
        
        Returns:
            统计信息字典
        """
        stats_copy = self.stats.copy()
        stats_copy.update({
            'queue_size': self.command_queue.qsize(),
            'response_queue_size': self.response_queue.qsize(),
            'running': self.running,
            'connected': self.connected
        })
        
        return stats_copy
    
    def clear_queues(self):
        """清空队列"""
        # 清空命令队列
        while not self.command_queue.empty():
            try:
                self.command_queue.get_nowait()
                self.command_queue.task_done()
            except queue.Empty:
                break
        
        # 清空响应队列
        while not self.response_queue.empty():
            try:
                self.response_queue.get_nowait()
                self.response_queue.task_done()
            except queue.Empty:
                break
        
        logger.info("通信队列已清空")

class CommandParser:
    """指令解析器"""
    
    def __init__(self):
        """初始化指令解析器"""
        # 指令格式定义
        self.command_patterns = {
            'MOTOR': r'^MOTOR:([01]):(\d{1,3})$',  # MOTOR:DIR:SPEED
            'SERVO': r'^SERVO:(\d{1,3})$',         # SERVO:ANGLE
            'STEPPER': r'^STEPPER:([01]):(\d+)$',  # STEPPER:DIR:STEPS
            'STATUS': r'^STATUS:(ALL|[A-Z0-9_]+)$' # STATUS:ALL or STATUS:DEVICE
        }
        
        # 响应格式定义
        self.response_patterns = {
            'MOTOR': r'^MOTOR:(SPEED|DIR):(.+)$',
            'SERVO': r'^SERVO:(ANGLE|SPEED):(.+)$',
            'STEPPER': r'^STEPPER:(POS|SPEED|DIR):(.+)$',
            'ACK': r'^ACK:(.+)$',
            'ERROR': r'^ERROR:(.+)$'
        }
    
    def validate_command(self, command: str) -> bool:
        """验证指令格式
        
        Args:
            command: 指令字符串
            
        Returns:
            格式是否有效
        """
        if not command or ':' not in command:
            return False
        
        # 提取指令类型
        cmd_type = command.split(':')[0]
        
        if cmd_type not in self.command_patterns:
            return False
        
        # 正则匹配验证
        pattern = self.command_patterns[cmd_type]
        match = re.match(pattern, command)
        
        return match is not None
    
    def parse_command(self, command: str) -> Optional[Dict]:
        """解析指令
        
        Args:
            command: 指令字符串
            
        Returns:
            解析后的指令字典，格式无效返回None
        """
        if not self.validate_command(command):
            return None
        
        parts = command.split(':')
        cmd_type = parts[0]
        
        result = {
            'type': cmd_type,
            'raw': command,
            'timestamp': datetime.now().isoformat()
        }
        
        # 根据指令类型解析参数
        if cmd_type == 'MOTOR' and len(parts) == 3:
            result.update({
                'direction': int(parts[1]),  # 0=正转, 1=反转
                'speed': int(parts[2])       # 0-100%
            })
        
        elif cmd_type == 'SERVO' and len(parts) == 2:
            result.update({
                'angle': int(parts[1])  # 0-180度
            })
        
        elif cmd_type == 'STEPPER' and len(parts) == 3:
            result.update({
                'direction': int(parts[1]),  # 0=正向, 1=反向
                'steps': int(parts[2])       # 步数
            })
        
        elif cmd_type == 'STATUS':
            result.update({
                'target': parts[1]  # ALL or 设备名
            })
        
        return result
    
    def parse_response(self, response: str) -> Optional[Dict]:
        """解析响应
        
        Args:
            response: 响应字符串
            
        Returns:
            解析后的响应字典，格式无效返回None
        """
        if not response or ':' not in response:
            return None
        
        parts = response.split(':', 2)  # 最多分割成3部分
        
        if len(parts) < 2:
            return None
        
        cmd_type = parts[0]
        
        # 检查是否为已知响应类型
        result = {
            'type': cmd_type,
            'raw': response,
            'timestamp': datetime.now().isoformat()
        }
        
        # 根据响应类型解析
        if cmd_type == 'MOTOR' and len(parts) >= 3:
            result.update({
                'device': 'MOTOR',
                'status_type': parts[1],
                'value': parts[2]
            })
        
        elif cmd_type == 'SERVO' and len(parts) >= 3:
            result.update({
                'device': 'SERVO',
                'status_type': parts[1],
                'value': parts[2]
            })
        
        elif cmd_type == 'STEPPER' and len(parts) >= 3:
            result.update({
                'device': 'STEPPER',
                'status_type': parts[1],
                'value': parts[2]
            })
        
        elif cmd_type == 'ACK':
            result.update({
                'ack_type': parts[1],
                'message': parts[2] if len(parts) > 2 else ''
            })
        
        elif cmd_type == 'ERROR':
            result.update({
                'error_type': parts[1],
                'message': parts[2] if len(parts) > 2 else ''
            })
        
        else:
            # 未知格式，记录原始响应
            result.update({
                'type': 'UNKNOWN',
                'raw': response
            })
        
        return result
    
    def build_command(self, cmd_type: str, **kwargs) -> Optional[str]:
        """构建指令字符串
        
        Args:
            cmd_type: 指令类型
            **kwargs: 指令参数
            
        Returns:
            指令字符串，失败返回None
        """
        if cmd_type == 'MOTOR':
            direction = kwargs.get('direction', 0)
            speed = kwargs.get('speed', 0)
            
            if direction not in [0, 1] or speed < 0 or speed > 100:
                return None
            
            return f"MOTOR:{direction}:{speed}"
        
        elif cmd_type == 'SERVO':
            angle = kwargs.get('angle', 90)
            
            if angle < 0 or angle > 180:
                return None
            
            return f"SERVO:{angle}"
        
        elif cmd_type == 'STEPPER':
            direction = kwargs.get('direction', 0)
            steps = kwargs.get('steps', 0)
            
            if direction not in [0, 1] or steps < 0:
                return None
            
            return f"STEPPER:{direction}:{steps}"
        
        elif cmd_type == 'STATUS':
            target = kwargs.get('target', 'ALL')
            return f"STATUS:{target}"
        
        return None

class MockSerialPort:
    """模拟串口类"""
    
    def __init__(self, port: str, baudrate: int, timeout: float):
        """初始化模拟串口
        
        Args:
            port: 端口名
            baudrate: 波特率
            timeout: 超时时间
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = True
        
        # 模拟缓冲区
        self.input_buffer = b''
        self.output_buffer = b''
        
        # 模拟响应
        self.mock_responses = {
            'MOTOR:0:50': 'ACK:MOTOR_SET:OK\n',
            'MOTOR:1:30': 'ACK:MOTOR_SET:OK\n',
            'SERVO:90': 'ACK:SERVO_SET:OK\n',
            'STEPPER:0:200': 'ACK:STEPPER_SET:OK\n',
            'STATUS:ALL': 'MOTOR:SPEED:50\nSERVO:ANGLE:90\nSTEPPER:POS:1024\n'
        }
    
    def write(self, data: bytes) -> int:
        """模拟写入数据
        
        Args:
            data: 要写入的数据
            
        Returns:
            写入的字节数
        """
        if not self.is_open:
            raise IOError("Port is closed")
        
        # 记录发送的数据
        self.output_buffer += data
        
        # 模拟响应（异步）
        threading.Thread(target=self._simulate_response, args=(data,), daemon=True).start()
        
        return len(data)
    
    def _simulate_response(self, sent_data: bytes):
        """模拟响应生成
        
        Args:
            sent_data: 发送的数据
        """
        time.sleep(0.01)  # 模拟通信延迟
        
        try:
            command = sent_data.decode('utf-8', errors='ignore').strip()
            
            # 查找对应的模拟响应
            for cmd_pattern, response in self.mock_responses.items():
                if command.startswith(cmd_pattern.split(':')[0]):
                    # 将响应加入输入缓冲区
                    self.input_buffer += response.encode('utf-8')
                    break
            
        except Exception:
            pass
    
    def readline(self) -> bytes:
        """模拟读取一行数据
        
        Returns:
            读取到的数据
        """
        if not self.is_open:
            return b''
        
        # 检查是否有数据
        if not self.input_buffer:
            time.sleep(0.01)
            return b''
        
        # 查找换行符
        if b'\n' in self.input_buffer:
            idx = self.input_buffer.index(b'\n') + 1
            data = self.input_buffer[:idx]
            self.input_buffer = self.input_buffer[idx:]
            return data
        
        # 没有换行符，返回所有数据
        data = self.input_buffer
        self.input_buffer = b''
        return data
    
    def flush(self):
        """模拟刷新缓冲区"""
        pass
    
    def close(self):
        """模拟关闭串口"""
        self.is_open = False
        self.input_buffer = b''
        self.output_buffer = b''

# 测试函数
def test_serial_manager():
    """测试串口管理器"""
    print("测试串口管理器...")
    
    # 创建配置
    serial_config = {
        'port': '/dev/ttyAMA0',
        'baudrate': 115200,
        'timeout': 1.0,
        'retry_count': 3,
        'retry_delay': 0.5
    }
    
    # 创建串口管理器
    manager = SerialManager(serial_config)
    
    # 添加连接状态回调
    def connection_callback(connected):
        print(f"连接状态变化: {'已连接' if connected else '已断开'}")
    
    manager.add_connection_callback(connection_callback)
    
    # 启动管理器
    manager.start()
    
    try:
        # 等待连接建立
        time.sleep(1.0)
        
        # 测试发送指令
        test_commands = [
            "MOTOR:0:75",
            "SERVO:45",
            "STEPPER:1:200",
            "STATUS:ALL"
        ]
        
        for cmd in test_commands:
            print(f"\n发送指令: {cmd}")
            
            # 发送并等待响应
            response = manager.send_and_wait(cmd, timeout=2.0)
            
            if response:
                print(f"收到响应: {response}")
            else:
                print("未收到响应")
            
            time.sleep(0.5)
        
        # 显示统计信息
        print("\n通信统计:")
        stats = manager.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
    finally:
        # 停止管理器
        manager.stop()
    
    print("\n测试完成")

if __name__ == "__main__":
    test_serial_manager()