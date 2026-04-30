#!/usr/bin/env python3
"""
快速测试MQTT发布功能
"""

import time
import json
import paho.mqtt.client as mqtt

def on_connect(client, userdata, flags, rc):
    print(f"✅ 连接成功，返回码: {rc}")

def on_publish(client, userdata, mid):
    print(f"📤 消息已发布，消息ID: {mid}")

# 创建客户端
client = mqtt.Client()
client.on_connect = on_connect
client.on_publish = on_publish

try:
    client.connect("mqtt.eclipseprojects.io", 1883, 60)
    client.loop_start()
    
    # 等待连接建立
    time.sleep(1)
    
    # 发布测试消息
    test_msg = {
        "timestamp": "2026-03-26T16:30:00Z",
        "device_id": "test_001",
        "sensor_id": "test_sensor",
        "value": 42.5,
        "unit": "°C"
    }
    
    result = client.publish("test/topic", json.dumps(test_msg))
    print(f"📤 发布结果: {result}")
    
    # 等待消息发送
    time.sleep(2)
    
    client.loop_stop()
    client.disconnect()
    print("✅ 测试完成")
    
except Exception as e:
    print(f"❌ 测试失败: {e}")