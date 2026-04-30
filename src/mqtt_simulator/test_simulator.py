#!/usr/bin/env python3
"""
测试MQTT模拟器功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mqtt_simulator import load_device_models, init_database

print("🔧 测试MQTT模拟器...")

# 测试模型加载
try:
    load_device_models()
    print("✅ 模型加载测试通过")
except Exception as e:
    print(f"❌ 模型加载测试失败: {e}")
    sys.exit(1)

# 测试数据库初始化
try:
    init_database()
    print("✅ 数据库初始化测试通过")
except Exception as e:
    print(f"❌ 数据库初始化测试失败: {e}")
    sys.exit(1)

print("🎉 所有测试通过！")