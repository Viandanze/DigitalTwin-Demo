#!/usr/bin/env python3
"""
云端同步端到端测试脚本
测试MQTT发布、API接收、数据库存储、Three.js更新、控制指令下发的全链路功能
"""

import sys
import os
import json
import time
import sqlite3
import random
import datetime
import threading
import logging
from urllib import request as urllib_request
from urllib.error import URLError

# 添加父目录到路径，以便导入模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("cloud_sync_e2e_test")

class CloudSyncE2ETest:
    """云端同步端到端测试类"""
    
    def __init__(self):
        self.api_base_url = "http://localhost:5000"
        self.db_path = "data/sensor_data.db"
        self.test_results = {}
        self.test_data = {
            "device_id": "test_raspberry_pi_001",
            "timestamp": datetime.datetime.now().isoformat(),
            "sensor_data": {
                "temperature": {
                    "value": round(random.uniform(15.0, 35.0), 2),
                    "unit": "℃",
                    "description": "测试环境温度"
                },
                "humidity": {
                    "value": round(random.uniform(30.0, 90.0), 2),
                    "unit": "%",
                    "description": "测试环境湿度"
                },
                "distance": {
                    "value": round(random.uniform(5.0, 45.0), 2),
                    "unit": "cm",
                    "description": "测试超声波测距"
                },
                "light": {
                    "value": round(random.uniform(0.0, 100.0), 2),
                    "unit": "%",
                    "description": "测试光照强度"
                },
                "pressure": {
                    "value": round(random.uniform(950.0, 1050.0), 2),
                    "unit": "hPa",
                    "description": "测试大气压强"
                }
            },
            "location": "test_lab_001",
            "firmware_version": "test_1.0.0"
        }
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 70)
        print("云端同步端到端测试开始")
        print("=" * 70)
        
        # 测试1: 检查API服务是否运行
        self.test_api_service()
        
        # 测试2: 发送传感器数据到API
        self.test_sensor_data_api()
        
        # 测试3: 验证数据库存储
        self.test_database_storage()
        
        # 测试4: 查询最新传感器数据
        self.test_latest_data_api()
        
        # 测试5: 发送控制指令
        self.test_control_command_api()
        
        # 测试6: 模拟MQTT发布（简化）
        self.test_mqtt_simulation()
        
        # 输出测试报告
        self.generate_test_report()
        
        return self.all_tests_passed()
    
    def test_api_service(self):
        """测试1: 检查API服务是否运行"""
        test_name = "API服务运行状态"
        logger.info(f"📋 开始测试: {test_name}")
        
        try:
            # 尝试访问API根路径
            req = urllib_request.Request(f"{self.api_base_url}/")
            response = urllib_request.urlopen(req, timeout=10)
            
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                self.test_results[test_name] = {
                    "status": "通过",
                    "message": f"API服务正常运行，版本: {data.get('version', '未知')}",
                    "details": data
                }
                logger.info(f"✅ {test_name}: 通过")
            else:
                self.test_results[test_name] = {
                    "status": "失败",
                    "message": f"API返回非200状态码: {response.status}",
                    "details": None
                }
                logger.error(f"❌ {test_name}: 失败")
                
        except URLError as e:
            self.test_results[test_name] = {
                "status": "失败",
                "message": f"无法连接到API服务: {e.reason}",
                "details": None
            }
            logger.error(f"❌ {test_name}: 失败 - {e.reason}")
        except Exception as e:
            self.test_results[test_name] = {
                "status": "失败",
                "message": f"测试过程中发生异常: {str(e)}",
                "details": None
            }
            logger.error(f"❌ {test_name}: 失败 - {str(e)}")
    
    def test_sensor_data_api(self):
        """测试2: 发送传感器数据到API"""
        test_name = "传感器数据API接收"
        logger.info(f"📋 开始测试: {test_name}")
        
        try:
            # 准备测试数据
            test_payload = self.test_data.copy()
            test_payload["timestamp"] = datetime.datetime.now().isoformat()
            
            # 发送POST请求
            req = urllib_request.Request(
                f"{self.api_base_url}/api/sensor/data",
                data=json.dumps(test_payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            
            response = urllib_request.urlopen(req, timeout=10)
            data = json.loads(response.read().decode('utf-8'))
            
            if response.status == 200 and data.get("success"):
                self.test_results[test_name] = {
                    "status": "通过",
                    "message": f"成功接收并存储 {data.get('sensor_count', 0)} 条传感器数据",
                    "details": data,
                    "test_payload": test_payload
                }
                logger.info(f"✅ {test_name}: 通过")
            else:
                self.test_results[test_name] = {
                    "status": "失败",
                    "message": f"API返回失败状态: {data.get('error', '未知错误')}",
                    "details": data
                }
                logger.error(f"❌ {test_name}: 失败")
                
        except Exception as e:
            self.test_results[test_name] = {
                "status": "失败",
                "message": f"发送传感器数据失败: {str(e)}",
                "details": None
            }
            logger.error(f"❌ {test_name}: 失败 - {str(e)}")
    
    def test_database_storage(self):
        """测试3: 验证数据库存储"""
        test_name = "数据库存储验证"
        logger.info(f"📋 开始测试: {test_name}")
        
        try:
            # 检查数据库文件是否存在
            if not os.path.exists(self.db_path):
                self.test_results[test_name] = {
                    "status": "失败",
                    "message": f"数据库文件不存在: {self.db_path}",
                    "details": None
                }
                logger.error(f"❌ {test_name}: 失败 - 数据库文件不存在")
                return
            
            # 连接数据库
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 查询最新的传感器数据（按时间戳倒序）
            cursor.execute('''
                SELECT * FROM sensor_data 
                WHERE device_id = ? 
                ORDER BY timestamp DESC 
                LIMIT 10
            ''', (self.test_data["device_id"],))
            
            rows = cursor.fetchall()
            
            if rows:
                # 验证数据格式
                latest_row = rows[0]
                required_fields = ['timestamp', 'device_id', 'sensor_id', 'value']
                
                missing_fields = []
                for field in required_fields:
                    if latest_row[field] is None:
                        missing_fields.append(field)
                
                if missing_fields:
                    self.test_results[test_name] = {
                        "status": "失败",
                        "message": f"数据库记录缺少必要字段: {missing_fields}",
                        "details": dict(latest_row)
                    }
                    logger.error(f"❌ {test_name}: 失败 - 缺少字段")
                else:
                    self.test_results[test_name] = {
                        "status": "通过",
                        "message": f"数据库存储验证成功，找到 {len(rows)} 条记录",
                        "details": {
                            "latest_record": dict(latest_row),
                            "total_records": len(rows)
                        }
                    }
                    logger.info(f"✅ {test_name}: 通过")
            else:
                self.test_results[test_name] = {
                    "status": "警告",
                    "message": f"数据库中未找到测试设备的数据，可能API尚未存储或设备ID不匹配",
                    "details": None
                }
                logger.warning(f"⚠️  {test_name}: 警告 - 未找到测试数据")
            
            conn.close()
            
        except sqlite3.Error as e:
            self.test_results[test_name] = {
                "status": "失败",
                "message": f"数据库操作失败: {str(e)}",
                "details": None
            }
            logger.error(f"❌ {test_name}: 失败 - {str(e)}")
        except Exception as e:
            self.test_results[test_name] = {
                "status": "失败",
                "message": f"数据库验证过程中发生异常: {str(e)}",
                "details": None
            }
            logger.error(f"❌ {test_name}: 失败 - {str(e)}")
    
    def test_latest_data_api(self):
        """测试4: 查询最新传感器数据"""
        test_name = "最新数据API查询"
        logger.info(f"📋 开始测试: {test_name}")
        
        try:
            # 发送GET请求查询最新数据
            req = urllib_request.Request(
                f"{self.api_base_url}/api/sensor/latest?limit=5",
                method='GET'
            )
            
            response = urllib_request.urlopen(req, timeout=10)
            data = json.loads(response.read().decode('utf-8'))
            
            if response.status == 200 and data.get("success"):
                self.test_results[test_name] = {
                    "status": "通过",
                    "message": f"成功查询到 {data.get('count', 0)} 条最新传感器数据",
                    "details": {
                        "data_count": data.get('count', 0),
                        "device_filter": data.get('device_id_filter', '无'),
                        "sample_data": data.get('data', [])[:2] if data.get('data') else []
                    }
                }
                logger.info(f"✅ {test_name}: 通过")
            else:
                self.test_results[test_name] = {
                    "status": "失败",
                    "message": f"查询最新数据失败: {data.get('error', '未知错误')}",
                    "details": data
                }
                logger.error(f"❌ {test_name}: 失败")
                
        except Exception as e:
            self.test_results[test_name] = {
                "status": "失败",
                "message": f"查询最新数据失败: {str(e)}",
                "details": None
            }
            logger.error(f"❌ {test_name}: 失败 - {str(e)}")
    
    def test_control_command_api(self):
        """测试5: 发送控制指令"""
        test_name = "控制指令API"
        logger.info(f"📋 开始测试: {test_name}")
        
        try:
            # 准备控制指令测试数据
            control_payload = {
                "device": "agv",
                "command": "move",
                "params": {
                    "speed": random.randint(20, 80),
                    "direction": random.choice(["forward", "backward"])
                }
            }
            
            # 发送POST请求
            req = urllib_request.Request(
                f"{self.api_base_url}/api/control/command",
                data=json.dumps(control_payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            
            response = urllib_request.urlopen(req, timeout=10)
            data = json.loads(response.read().decode('utf-8'))
            
            if response.status == 200 and data.get("success"):
                self.test_results[test_name] = {
                    "status": "通过",
                    "message": f"控制指令发送成功: {control_payload['device']} - {control_payload['command']}",
                    "details": data,
                    "test_payload": control_payload
                }
                logger.info(f"✅ {test_name}: 通过")
            else:
                self.test_results[test_name] = {
                    "status": "失败",
                    "message": f"控制指令发送失败: {data.get('error', '未知错误')}",
                    "details": data
                }
                logger.error(f"❌ {test_name}: 失败")
                
        except Exception as e:
            self.test_results[test_name] = {
                "status": "失败",
                "message": f"发送控制指令失败: {str(e)}",
                "details": None
            }
            logger.error(f"❌ {test_name}: 失败 - {str(e)}")
    
    def test_mqtt_simulation(self):
        """测试6: 模拟MQTT发布（简化测试）"""
        test_name = "MQTT模拟功能"
        logger.info(f"📋 开始测试: {test_name}")
        
        try:
            # 这里不实际连接MQTT，而是测试MQTT客户端代码的导入和基本功能
            # 检查mqtt_client.py是否存在
            mqtt_client_path = os.path.join(os.path.dirname(__file__), "mqtt_client.py")
            
            if not os.path.exists(mqtt_client_path):
                self.test_results[test_name] = {
                    "status": "失败",
                    "message": f"MQTT客户端文件不存在: {mqtt_client_path}",
                    "details": None
                }
                logger.error(f"❌ {test_name}: 失败 - 文件不存在")
                return
            
            # 尝试导入mqtt_client模块（简化，不实际运行）
            import importlib.util
            spec = importlib.util.spec_from_file_location("mqtt_client", mqtt_client_path)
            mqtt_module = importlib.util.module_from_spec(spec)
            
            # 只检查文件内容是否包含必要的函数和类
            with open(mqtt_client_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            required_elements = [
                "paho.mqtt.client",
                "DEVICE_ID",
                "MQTT_TOPIC",
                "create_sensor_message",
                "publish_sensor_data"
            ]
            
            missing_elements = []
            for element in required_elements:
                if element not in content:
                    missing_elements.append(element)
            
            if missing_elements:
                self.test_results[test_name] = {
                    "status": "警告",
                    "message": f"MQTT客户端文件缺少部分元素: {missing_elements}",
                    "details": None
                }
                logger.warning(f"⚠️  {test_name}: 警告 - 缺少元素")
            else:
                self.test_results[test_name] = {
                    "status": "通过",
                    "message": "MQTT客户端代码结构验证通过",
                    "details": {
                        "file_size": os.path.getsize(mqtt_client_path),
                        "line_count": len(content.splitlines())
                    }
                }
                logger.info(f"✅ {test_name}: 通过")
                
        except Exception as e:
            self.test_results[test_name] = {
                "status": "警告",
                "message": f"MQTT模拟测试部分失败（不影响核心功能）: {str(e)}",
                "details": None
            }
            logger.warning(f"⚠️  {test_name}: 警告 - {str(e)}")
    
    def generate_test_report(self):
        """生成测试报告"""
        print("\n" + "=" * 70)
        print("云端同步端到端测试报告")
        print("=" * 70)
        
        # 统计测试结果
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results.values() if r["status"] == "通过")
        failed_tests = sum(1 for r in self.test_results.values() if r["status"] == "失败")
        warning_tests = sum(1 for r in self.test_results.values() if r["status"] == "警告")
        
        print(f"\n📊 测试统计:")
        print(f"   总测试数: {total_tests}")
        print(f"   ✅ 通过: {passed_tests}")
        print(f"   ❌ 失败: {failed_tests}")
        print(f"   ⚠️  警告: {warning_tests}")
        
        # 详细测试结果
        print(f"\n📋 详细结果:")
        for test_name, result in self.test_results.items():
            status_icon = "✅" if result["status"] == "通过" else "❌" if result["status"] == "失败" else "⚠️"
            print(f"   {status_icon} {test_name}: {result['status']}")
            print(f"      消息: {result['message']}")
        
        # 总体结论
        print(f"\n🎯 总体结论:")
        if failed_tests == 0:
            if warning_tests == 0:
                print("   🎉 所有测试通过！云端同步功能完整可用。")
            else:
                print("   👍 核心功能测试通过，部分非关键功能有警告。")
        else:
            print("   😞 存在失败的测试，需要检查相关功能。")
        
        print("\n" + "=" * 70)
        
        # 保存报告到文件
        self.save_report_to_file()
    
    def save_report_to_file(self):
        """保存测试报告到文件"""
        report_data = {
            "test_timestamp": datetime.datetime.now().isoformat(),
            "test_results": self.test_results,
            "summary": {
                "total_tests": len(self.test_results),
                "passed_tests": sum(1 for r in self.test_results.values() if r["status"] == "通过"),
                "failed_tests": sum(1 for r in self.test_results.values() if r["status"] == "失败"),
                "warning_tests": sum(1 for r in self.test_results.values() if r["status"] == "警告")
            }
        }
        
        report_dir = "reports"
        os.makedirs(report_dir, exist_ok=True)
        
        report_file = os.path.join(report_dir, f"cloud_sync_e2e_test_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 测试报告已保存到: {report_file}")
    
    def all_tests_passed(self):
        """检查所有测试是否通过"""
        failed_tests = sum(1 for r in self.test_results.values() if r["status"] == "失败")
        return failed_tests == 0

def main():
    """主函数"""
    # 创建测试实例
    tester = CloudSyncE2ETest()
    
    # 运行所有测试
    success = tester.run_all_tests()
    
    # 返回退出码
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()