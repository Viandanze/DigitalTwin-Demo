#!/usr/bin/env python3
"""
树莓派MQTT传感器数据发布客户端
模拟树莓派采集温湿度、距离、光照、气压传感器数据，按1秒间隔发布到MQTT主题
为云端同步与数字孪生数据同步提供数据源
"""

import json
import random
import time
import datetime
import logging
import sys
import signal
import paho.mqtt.client as mqtt

# 配置
MQTT_BROKER = "mqtt.eclipseprojects.io"  # 公共测试代理
MQTT_PORT = 1883
MQTT_TOPIC = "dt/sensor/data"
DEVICE_ID = "raspberry_pi_001"
SENSOR_INTERVAL = 1.0  # 秒

# 传感器配置
SENSOR_CONFIGS = {
    "temperature": {
        "range": [15.0, 35.0],
        "unit": "℃",
        "description": "环境温度"
    },
    "humidity": {
        "range": [30.0, 90.0],
        "unit": "%",
        "description": "环境湿度"
    },
    "distance": {
        "range": [5.0, 45.0],
        "unit": "cm",
        "description": "超声波测距"
    },
    "light": {
        "range": [0.0, 100.0],
        "unit": "%",
        "description": "光照强度"
    },
    "pressure": {
        "range": [950.0, 1050.0],
        "unit": "hPa",
        "description": "大气压强"
    }
}

# 全局变量
mqtt_client = None
running = False
logger = None

def setup_logging():
    """配置日志"""
    global logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger("raspberry_mqtt_client")

def generate_sensor_value(sensor_name):
    """生成传感器模拟值"""
    config = SENSOR_CONFIGS.get(sensor_name)
    if not config or "range" not in config:
        return None
    
    min_val, max_val = config["range"]
    # 生成在范围内的随机值，添加缓慢变化趋势
    base = (min_val + max_val) / 2
    # 添加一些正弦波动模拟昼夜/周期性变化
    time_factor = time.time() / 3600  # 每小时周期
    sine_wave = random.uniform(-0.2, 0.2) * (max_val - min_val) * 0.5
    
    # 主要随机波动
    fluctuation = random.uniform(-0.1, 0.1) * (max_val - min_val)
    value = base + sine_wave + fluctuation
    
    # 确保在合理范围内
    value = max(min_val * 0.9, min(max_val * 1.1, value))
    
    # 添加偶尔的异常值（5%概率）
    if random.random() < 0.05:
        value = random.uniform(min_val - 10, max_val + 10)
    
    return round(value, 2)

def create_sensor_message():
    """创建传感器数据消息"""
    timestamp = datetime.datetime.now().isoformat()
    
    # 生成所有传感器数据
    sensor_readings = {}
    for sensor_name, config in SENSOR_CONFIGS.items():
        value = generate_sensor_value(sensor_name)
        if value is not None:
            sensor_readings[sensor_name] = {
                "value": value,
                "unit": config["unit"],
                "description": config["description"]
            }
    
    # 完整消息
    message = {
        "device_id": DEVICE_ID,
        "timestamp": timestamp,
        "sensor_data": sensor_readings,
        "location": "lab_001",
        "firmware_version": "1.2.0"
    }
    
    return message

def on_mqtt_connect(client, userdata, flags, rc):
    """MQTT连接回调"""
    if rc == 0:
        logger.info(f"✅ 已连接到MQTT代理 {MQTT_BROKER}:{MQTT_PORT}")
    else:
        logger.error(f"❌ MQTT连接失败，返回码: {rc}")

def on_mqtt_disconnect(client, userdata, rc):
    """MQTT断开连接回调"""
    logger.warning(f"⚠️  MQTT连接断开，返回码: {rc}")
    if running:
        logger.info("尝试重新连接...")
        time.sleep(5)
        try:
            client.reconnect()
        except Exception as e:
            logger.error(f"重连失败: {e}")

def publish_sensor_data():
    """发布传感器数据"""
    global mqtt_client, running
    
    while running:
        try:
            # 创建传感器消息
            message = create_sensor_message()
            payload = json.dumps(message, ensure_ascii=False)
            
            # 发布到MQTT
            result = mqtt_client.publish(MQTT_TOPIC, payload, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"📤 已发布传感器数据到 {MQTT_TOPIC}")
                logger.debug(f"数据内容: {payload}")
            else:
                logger.warning(f"发布失败，返回码: {result.rc}")
            
            # 等待下一个发布周期
            time.sleep(SENSOR_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("接收到中断信号")
            running = False
            break
        except Exception as e:
            logger.error(f"发布传感器数据时出错: {e}")
            time.sleep(SENSOR_INTERVAL)

def signal_handler(signum, frame):
    """信号处理函数"""
    global running
    logger.info("接收到停止信号，正在关闭...")
    running = False

def main():
    """主函数"""
    global mqtt_client, running
    
    setup_logging()
    
    print("=" * 60)
    print("树莓派MQTT传感器数据发布客户端 v1.0")
    print(f"设备ID: {DEVICE_ID}")
    print(f"MQTT代理: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"发布主题: {MQTT_TOPIC}")
    print(f"发布间隔: {SENSOR_INTERVAL}秒")
    print("=" * 60)
    
    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 创建MQTT客户端
    mqtt_client = mqtt.Client(client_id=DEVICE_ID)
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_disconnect = on_mqtt_disconnect
    
    # 连接MQTT代理
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
    except Exception as e:
        logger.error(f"无法连接到MQTT代理: {e}")
        return 1
    
    # 等待连接建立
    time.sleep(2)
    
    running = True
    
    # 开始发布数据
    try:
        publish_sensor_data()
    except Exception as e:
        logger.error(f"主循环异常: {e}")
    
    # 清理资源
    logger.info("正在停止客户端...")
    running = False
    
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    
    logger.info("客户端已停止")
    return 0

if __name__ == "__main__":
    sys.exit(main())