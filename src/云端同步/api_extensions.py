#!/usr/bin/env python3
"""
Flask API扩展 - 云端同步专用端点
扩展现有Flask应用，添加传感器数据接收和查询端点
以及远程控制指令下发端点
"""

import json
import sqlite3
import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, make_response

# 创建蓝图
cloud_sync_bp = Blueprint('cloud_sync', __name__)

# 数据库路径（默认）
DB_PATH = "data/sensor_data.db"

# 配置日志
logger = logging.getLogger(__name__)

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 使返回结果为字典形式
    return conn

def init_sensor_table():
    """确保传感器数据表存在（与现有表结构一致）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 创建传感器数据表（如果不存在）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            device_id TEXT NOT NULL,
            sensor_id TEXT NOT NULL,
            sensor_type TEXT NOT NULL,
            sensor_name TEXT,
            value REAL NOT NULL,
            unit TEXT,
            topic TEXT
        )
    ''')
    
    # 创建设备状态表（如果不存在）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            device_id TEXT NOT NULL,
            status TEXT NOT NULL,
            position_x REAL,
            position_y REAL,
            position_z REAL,
            battery INTEGER,
            speed REAL
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("传感器数据表初始化完成")

@cloud_sync_bp.route('/api/sensor/data', methods=['POST'])
def receive_sensor_data():
    """接收传感器数据并存储到数据库
    
    请求体格式（树莓派MQTT客户端发布的数据）:
    {
        "device_id": "raspberry_pi_001",
        "timestamp": "2026-04-04T05:37:00.123456",
        "sensor_data": {
            "temperature": {
                "value": 25.5,
                "unit": "℃",
                "description": "环境温度"
            },
            "humidity": {
                "value": 65.2,
                "unit": "%",
                "description": "环境湿度"
            },
            "distance": {
                "value": 32.1,
                "unit": "cm",
                "description": "超声波测距"
            },
            "light": {
                "value": 78.5,
                "unit": "%",
                "description": "光照强度"
            },
            "pressure": {
                "value": 1013.2,
                "unit": "hPa",
                "description": "大气压强"
            }
        },
        "location": "lab_001",
        "firmware_version": "1.2.0"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "请求体必须为JSON格式"
            }), 400
        
        # 验证必要字段
        required_fields = ['device_id', 'timestamp', 'sensor_data']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "success": False,
                    "error": f"缺少必要字段: {field}"
                }), 400
        
        device_id = data['device_id']
        timestamp = data['timestamp']
        sensor_data = data['sensor_data']
        
        # 验证传感器数据格式
        if not isinstance(sensor_data, dict):
            return jsonify({
                "success": False,
                "error": "sensor_data必须为对象格式"
            }), 400
        
        # 确保数据库表存在
        init_sensor_table()
        
        # 连接数据库
        conn = get_db_connection()
        cursor = conn.cursor()
        
        inserted_count = 0
        
        # 遍历每个传感器，插入数据库
        for sensor_name, sensor_info in sensor_data.items():
            if not isinstance(sensor_info, dict):
                continue
                
            value = sensor_info.get('value')
            unit = sensor_info.get('unit', '')
            description = sensor_info.get('description', '')
            
            if value is None:
                continue
            
            # 生成传感器ID和类型
            sensor_id = f"{device_id}_{sensor_name}"
            sensor_type = sensor_name
            
            # 插入数据
            cursor.execute('''
                INSERT INTO sensor_data 
                (timestamp, device_id, sensor_id, sensor_type, sensor_name, value, unit, topic)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                timestamp, 
                device_id, 
                sensor_id,
                sensor_type,
                description,
                float(value),
                unit,
                request.url  # 记录来源URL
            ))
            
            inserted_count += 1
        
        conn.commit()
        conn.close()
        
        logger.info(f"成功存储 {inserted_count} 条传感器数据，设备: {device_id}")
        
        return jsonify({
            "success": True,
            "message": f"成功接收并存储 {inserted_count} 条传感器数据",
            "device_id": device_id,
            "timestamp": timestamp,
            "sensor_count": inserted_count
        })
        
    except Exception as e:
        logger.error(f"接收传感器数据失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@cloud_sync_bp.route('/api/sensor/latest', methods=['GET'])
def get_latest_sensor_data():
    """查询最新传感器数据
    
    查询参数:
    - device_id: 设备ID (可选，默认返回所有设备的最新数据)
    - limit: 返回的传感器数量限制 (可选，默认10)
    """
    try:
        device_id = request.args.get('device_id')
        limit = int(request.args.get('limit', 10))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 构建查询条件
        if device_id:
            query = '''
                SELECT * FROM sensor_data 
                WHERE device_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            '''
            cursor.execute(query, (device_id, limit))
        else:
            query = '''
                SELECT * FROM sensor_data 
                ORDER BY timestamp DESC 
                LIMIT ?
            '''
            cursor.execute(query, (limit,))
        
        rows = cursor.fetchall()
        
        # 转换为字典列表
        data = []
        for row in rows:
            data.append({
                "id": row['id'],
                "timestamp": row['timestamp'],
                "device_id": row['device_id'],
                "sensor_id": row['sensor_id'],
                "sensor_type": row['sensor_type'],
                "sensor_name": row['sensor_name'],
                "value": row['value'],
                "unit": row['unit'],
                "topic": row['topic']
            })
        
        conn.close()
        
        # 按设备分组数据
        grouped_data = {}
        for item in data:
            dev_id = item['device_id']
            if dev_id not in grouped_data:
                grouped_data[dev_id] = []
            grouped_data[dev_id].append(item)
        
        return jsonify({
            "success": True,
            "count": len(data),
            "device_id_filter": device_id if device_id else "全部设备",
            "data": data,
            "grouped_by_device": grouped_data
        })
        
    except Exception as e:
        logger.error(f"查询最新传感器数据失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@cloud_sync_bp.route('/api/control/command', methods=['POST'])
def receive_control_command():
    """接收远程控制指令
    
    请求体格式:
    {
        "device": "agv",
        "command": "move",
        "params": {
            "speed": 50,
            "direction": "forward"
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "请求体必须为JSON格式"
            }), 400
        
        # 验证必要字段
        required_fields = ['device', 'command']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "success": False,
                    "error": f"缺少必要字段: {field}"
                }), 400
        
        device = data['device']
        command = data['command']
        params = data.get('params', {})
        timestamp = datetime.now().isoformat()
        
        # 模拟指令处理逻辑
        # 在实际系统中，这里会将指令转发到串口或MQTT
        logger.info(f"📡 收到控制指令 - 设备: {device}, 命令: {command}, 参数: {params}")
        
        # 模拟不同设备的响应
        response = {
            "success": True,
            "message": f"指令已接收并排队执行",
            "device": device,
            "command": command,
            "params": params,
            "timestamp": timestamp,
            "execution_id": f"cmd_{int(time.time())}_{random.randint(1000, 9999)}"
        }
        
        # 根据设备类型模拟不同的响应细节
        if device == "agv":
            response["details"] = {
                "action": "移动指令",
                "expected_duration": "5秒",
                "next_status": "moving"
            }
        elif device == "arm":
            response["details"] = {
                "action": "关节控制",
                "expected_duration": "3秒",
                "next_status": "busy"
            }
        elif device == "raspberry_pi":
            response["details"] = {
                "action": "传感器读取",
                "expected_duration": "1秒",
                "next_status": "sensing"
            }
        else:
            response["details"] = {
                "action": "未知设备类型",
                "expected_duration": "未知",
                "next_status": "unknown"
            }
        
        # 记录到控制日志表（如果存在）
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 检查控制日志表是否存在
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS control_command_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    device TEXT NOT NULL,
                    command TEXT NOT NULL,
                    params TEXT,
                    received INTEGER DEFAULT 1,
                    forwarded INTEGER DEFAULT 0,
                    forwarded_to TEXT,
                    response TEXT
                )
            ''')
            
            # 插入记录
            cursor.execute('''
                INSERT INTO control_command_log 
                (timestamp, device, command, params, response)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                timestamp,
                device,
                command,
                json.dumps(params),
                json.dumps(response)
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"控制指令已记录到数据库")
            
        except Exception as db_error:
            logger.warning(f"记录控制指令到数据库失败: {db_error}")
            # 继续执行，不影响主流程
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"处理控制指令失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# 辅助函数：模拟串口下发
def simulate_serial_command(device, command, params):
    """模拟通过串口下发指令到Arduino
    
    在实际硬件部署中，这里会通过pyserial发送指令
    """
    # 构建指令字符串
    if device == "agv" and command == "move":
        speed = params.get("speed", 0)
        direction = params.get("direction", "forward")
        
        if direction == "forward":
            dir_code = "0"
        else:
            dir_code = "1"
        
        cmd_str = f"MOTOR:{dir_code}:{speed}"
        logger.info(f"🔌 串口模拟: 发送指令 -> {cmd_str}")
        
    elif device == "arm" and command == "set_angles":
        joint1 = params.get("joint1", 0)
        joint2 = params.get("joint2", 45)
        joint3 = params.get("joint3", -30)
        
        cmd_str = f"SERVO:J1:{joint1}:J2:{joint2}:J3:{joint3}"
        logger.info(f"🔌 串口模拟: 发送指令 -> {cmd_str}")
    
    else:
        logger.info(f"🔌 串口模拟: 未识别的设备/命令组合 {device}/{command}")
    
    # 模拟指令执行延迟
    time.sleep(0.1)
    
    return True

# 导入必要的模块（在文件末尾）
import time
import random