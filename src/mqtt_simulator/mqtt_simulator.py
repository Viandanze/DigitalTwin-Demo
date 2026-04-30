#!/usr/bin/env python3
"""
MQTT数据流模拟器 - 工业设备数字孪生演示
基于Day 1定义的设备模型JSON规范，模拟传感器数据并通过MQTT发布
同时将数据存储到SQLite数据库以供历史查询
"""

import json
import random
import time
import sqlite3
from datetime import datetime
import paho.mqtt.client as mqtt
import threading
import os
import sys

# 设备模型文件路径
AGV_MODEL_FILE = "outputs/冲刺项目/Day1-规划文档/agv_model.json"
ARM_MODEL_FILE = "outputs/冲刺项目/Day1-规划文档/robotic_arm_model.json"

# MQTT代理配置（使用公共测试代理）
MQTT_BROKER = "mqtt.eclipseprojects.io"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60

# SQLite数据库路径
DB_PATH = "data/sensor_data.db"

# 全局变量
agv_model = None
arm_model = None
mqtt_client = None
db_conn = None

def load_device_models():
    """加载设备模型JSON文件"""
    global agv_model, arm_model
    
    try:
        with open(AGV_MODEL_FILE, 'r', encoding='utf-8') as f:
            agv_model = json.load(f)
        print(f"✅ AGV模型加载成功: {agv_model['device_id']}")
    except Exception as e:
        print(f"❌ AGV模型加载失败: {e}")
        agv_model = None
    
    try:
        with open(ARM_MODEL_FILE, 'r', encoding='utf-8') as f:
            arm_model = json.load(f)
        print(f"✅ 机械臂模型加载成功: {arm_model['device_id']}")
    except Exception as e:
        print(f"❌ 机械臂模型加载失败: {e}")
        arm_model = None

def init_database():
    """初始化SQLite数据库，创建数据表"""
    global db_conn
    
    try:
        db_conn = sqlite3.connect(DB_PATH)
        cursor = db_conn.cursor()
        
        # 创建传感器数据表
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
        
        # 创建设备状态表
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
        
        # 创建关节角度表（针对机械臂）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS joint_angles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                device_id TEXT NOT NULL,
                joint_id TEXT NOT NULL,
                angle REAL NOT NULL,
                unit TEXT
            )
        ''')
        
        db_conn.commit()
        print(f"✅ 数据库初始化完成: {DB_PATH}")
        
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        db_conn = None

def save_sensor_data_to_db(timestamp, device_id, sensor_id, sensor_type, sensor_name, value, unit, topic):
    """保存传感器数据到数据库"""
    if db_conn is None:
        return
    
    try:
        cursor = db_conn.cursor()
        cursor.execute('''
            INSERT INTO sensor_data (timestamp, device_id, sensor_id, sensor_type, sensor_name, value, unit, topic)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, device_id, sensor_id, sensor_type, sensor_name, value, unit, topic))
        db_conn.commit()
    except Exception as e:
        print(f"❌ 传感器数据保存失败: {e}")

def save_device_status_to_db(timestamp, device_id, status, position_x, position_y, position_z, battery, speed):
    """保存设备状态到数据库"""
    if db_conn is None:
        return
    
    try:
        cursor = db_conn.cursor()
        cursor.execute('''
            INSERT INTO device_status (timestamp, device_id, status, position_x, position_y, position_z, battery, speed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, device_id, status, position_x, position_y, position_z, battery, speed))
        db_conn.commit()
    except Exception as e:
        print(f"❌ 设备状态保存失败: {e}")

def save_joint_angles_to_db(timestamp, device_id, joint_id, angle, unit):
    """保存关节角度到数据库"""
    if db_conn is None:
        return
    
    try:
        cursor = db_conn.cursor()
        cursor.execute('''
            INSERT INTO joint_angles (timestamp, device_id, joint_id, angle, unit)
            VALUES (?, ?, ?, ?, ?)
        ''', (timestamp, device_id, joint_id, angle, unit))
        db_conn.commit()
    except Exception as e:
        print(f"❌ 关节角度保存失败: {e}")

def generate_sensor_value(sensor_def):
    """根据传感器定义生成模拟值"""
    if 'range' in sensor_def and len(sensor_def['range']) == 2:
        min_val, max_val = sensor_def['range']
        # 在范围内生成随机值，但围绕某个基准值波动
        base = sensor_def.get('value', (min_val + max_val) / 2)
        # 产生小范围波动
        fluctuation = random.uniform(-0.1, 0.1) * (max_val - min_val)
        value = base + fluctuation
        # 确保在范围内
        value = max(min_val, min(max_val, value))
        return round(value, 2)
    else:
        # 没有范围定义，返回固定值加小随机
        base = sensor_def.get('value', 0)
        return round(base + random.uniform(-0.5, 0.5), 2)

def simulate_agv_data():
    """模拟AGV数据生成和发布"""
    if agv_model is None:
        return
    
    device_id = agv_model['device_id']
    data_topic = agv_model['metadata']['communication']['data_topic']
    
    # 生成传感器数据
    for sensor in agv_model['sensors']:
        timestamp = datetime.now().isoformat()
        value = generate_sensor_value(sensor)
        
        # 构建MQTT消息
        message = {
            "timestamp": timestamp,
            "device_id": device_id,
            "sensor_id": sensor['sensor_id'],
            "sensor_type": sensor['type'],
            "sensor_name": sensor['name'],
            "value": value,
            "unit": sensor['unit'],
            "topic": data_topic
        }
        
        # 发布到MQTT
        if mqtt_client:
            mqtt_client.publish(data_topic, json.dumps(message))
            print(f"📤 AGV数据发布: {sensor['sensor_id']} = {value} {sensor['unit']}")
        
        # 保存到数据库
        save_sensor_data_to_db(
            timestamp, device_id, sensor['sensor_id'], sensor['type'],
            sensor['name'], value, sensor['unit'], data_topic
        )
    
    # 模拟AGV位置变化（缓慢移动）
    if 'position' in agv_model:
        # 在-2到2范围内随机移动
        new_x = agv_model['position']['x'] + random.uniform(-0.05, 0.05)
        new_y = agv_model['position']['y']
        new_z = agv_model['position']['z'] + random.uniform(-0.05, 0.05)
        
        # 限制范围
        new_x = max(-2, min(2, new_x))
        new_z = max(-2, min(2, new_z))
        
        agv_model['position']['x'] = new_x
        agv_model['position']['z'] = new_z
    
    # 模拟电量缓慢下降
    if 'battery' in agv_model:
        agv_model['battery'] = max(10, agv_model['battery'] - random.uniform(0, 0.1))
    
    # 保存设备状态到数据库
    timestamp = datetime.now().isoformat()
    save_device_status_to_db(
        timestamp, device_id, agv_model['status'],
        agv_model['position']['x'], agv_model['position']['y'], agv_model['position']['z'],
        int(agv_model['battery']), agv_model.get('speed', 0.0)
    )

def simulate_arm_data():
    """模拟机械臂数据生成和发布"""
    if arm_model is None:
        return
    
    device_id = arm_model['device_id']
    data_topic = arm_model['metadata']['communication']['data_topic']
    
    # 生成传感器数据
    for sensor in arm_model['sensors']:
        timestamp = datetime.now().isoformat()
        value = generate_sensor_value(sensor)
        
        # 构建MQTT消息
        message = {
            "timestamp": timestamp,
            "device_id": device_id,
            "sensor_id": sensor['sensor_id'],
            "sensor_type": sensor['type'],
            "sensor_name": sensor['name'],
            "value": value,
            "unit": sensor['unit'],
            "topic": data_topic
        }
        
        # 发布到MQTT
        if mqtt_client:
            mqtt_client.publish(data_topic, json.dumps(message))
            print(f"📤 机械臂数据发布: {sensor['sensor_id']} = {value} {sensor['unit']}")
        
        # 保存到数据库
        save_sensor_data_to_db(
            timestamp, device_id, sensor['sensor_id'], sensor['type'],
            sensor['name'], value, sensor['unit'], data_topic
        )
    
    # 模拟关节角度变化
    if 'joints' in arm_model:
        for joint in arm_model['joints']:
            # 在范围内随机变化
            if 'min' in joint and 'max' in joint:
                new_angle = joint.get('angle', 0) + random.uniform(-5, 5)
                new_angle = max(joint['min'], min(joint['max'], new_angle))
                joint['angle'] = new_angle
                
                # 保存关节角度到数据库
                timestamp = datetime.now().isoformat()
                save_joint_angles_to_db(
                    timestamp, device_id, joint['joint_id'],
                    new_angle, joint.get('unit', '°')
                )
    
    # 保存设备状态到数据库
    timestamp = datetime.now().isoformat()
    save_device_status_to_db(
        timestamp, device_id, arm_model['status'],
        arm_model['position']['x'], arm_model['position']['y'], arm_model['position']['z'],
        None, None  # 机械臂无电量、速度
    )

def on_mqtt_connect(client, userdata, flags, rc):
    """MQTT连接回调"""
    if rc == 0:
        print("✅ MQTT代理连接成功")
    else:
        print(f"❌ MQTT连接失败，返回码: {rc}")

def init_mqtt():
    """初始化MQTT客户端并连接"""
    global mqtt_client
    
    client = mqtt.Client()
    client.on_connect = on_mqtt_connect
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
        client.loop_start()
        mqtt_client = client
        print(f"✅ MQTT客户端初始化完成，代理: {MQTT_BROKER}:{MQTT_PORT}")
        return True
    except Exception as e:
        print(f"❌ MQTT连接失败: {e}")
        return False

def simulation_loop():
    """主模拟循环"""
    print("🚀 开始数据流模拟...")
    
    # 初始化
    load_device_models()
    if not init_mqtt():
        print("⚠️  使用模拟模式（无实际MQTT连接）")
    
    init_database()
    
    # 模拟计数器
    iteration = 0
    
    try:
        while True:
            iteration += 1
            print(f"\n🔄 第 {iteration} 轮数据生成")
            
            # 模拟AGV数据
            simulate_agv_data()
            
            # 模拟机械臂数据
            simulate_arm_data()
            
            # 等待下一个周期（使用最短的传感器更新间隔）
            # 从模型中获取最短更新间隔
            min_interval = 1000  # 默认1秒
            if agv_model:
                for sensor in agv_model['sensors']:
                    interval = sensor.get('update_interval', 1000)
                    min_interval = min(min_interval, interval)
            if arm_model:
                for sensor in arm_model['sensors']:
                    interval = sensor.get('update_interval', 1000)
                    min_interval = min(min_interval, interval)
            
            # 转换为秒（毫秒转秒）
            sleep_time = min_interval / 1000.0
            time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        print("\n🛑 模拟停止")
    finally:
        # 清理资源
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        if db_conn:
            db_conn.close()
        print("✅ 资源清理完成")

if __name__ == "__main__":
    print("=" * 60)
    print("工业设备数字孪生 - MQTT数据流模拟器")
    print("=" * 60)
    
    # 检查模型文件是否存在
    if not os.path.exists(AGV_MODEL_FILE):
        print(f"❌ AGV模型文件不存在: {AGV_MODEL_FILE}")
        sys.exit(1)
    if not os.path.exists(ARM_MODEL_FILE):
        print(f"❌ 机械臂模型文件不存在: {ARM_MODEL_FILE}")
        sys.exit(1)
    
    # 启动模拟循环
    simulation_loop()