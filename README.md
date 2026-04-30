# DigitalTwin_Demo

工业设备数字孪生系统。

软硬件结合的项目：Three.js 做 3D 可视化，MQTT 通信，Arduino 采集传感器数据，最终实现闭环控制。

## 这项目是干嘛的

简单说就是给工业设备建一个实时同步的数字副本。物理世界的传感器数据采集上来，通过 MQTT 传送到数字世界，Three.js 渲染出设备的实时状态，控制引擎根据数据计算控制指令，再下发执行。

目前能跑起来的核心功能：
- 传感器数据采集（温度、压力、位置）
- MQTT 实时通信
- 3D 可视化渲染（PBR 材质）
- PID 闭环控制
- 执行器控制（直流电机、舵机、步进电机）

## 技术栈

- 前端：Three.js + JavaScript
- 后端：Python 3.8+（FastAPI/Flask）
- 通信协议：MQTT（Eclipse Mosquitto）
- 硬件：Arduino + 传感器套件
- 状态存储：SQLite

硬件环境：树莓派 5 + Arduino UNO R3 + 传感器套件（温度/压力/位置传感器）

## 系统架构

```
传感器 → Arduino → 串口 → Python 桥接程序 → MQTT Broker → 控制引擎
                                                      ↓
                                           Web (Three.js) ← 实时渲染设备状态
```

数据流向：
1. Arduino 读取传感器数据
2. Python 通过串口接收数据
3. 数据发布到 MQTT Broker
4. 控制引擎订阅传感器 topic
5. PID 控制器计算控制量
6. 控制指令发布到执行器 topic
7. Arduino 接收指令调整电机
8. Three.js 渲染最新状态

## 怎么跑起来

### 环境要求

- Python 3.8+
- Arduino IDE
- MQTT Broker（Eclipse Mosquitto）

### 安装

```bash
git clone https://github.com/Viandanze/DigitalTwin_Demo.git
cd DigitalTwin_Demo

pip install paho-mqtt pyserial flask fastapi

# Arduino 库（通过 Arduino IDE Library Manager 安装）
# - PubSubClient
# - ArduinoJson
```

### 启动顺序

```bash
# 终端 1: 启动 MQTT broker
mosquitto -v

# 终端 2: 启动串口桥接程序
python src/串口通信/arduino_bridge.py

# 终端 3: 如果没有硬件，先跑模拟器测试
python src/mqtt_simulator/mqtt_simulator.py

# 终端 4: 启动控制引擎
python src/执行器集成/control_main.py

# 打开浏览器访问 src/index.html
```

## 项目结构

```
DigitalTwin_Demo/
├── src/
│   ├── Arduino/                    # Arduino 固件
│   ├── 传感器采集/                 # 传感器数据采集
│   ├── 串口通信/                   # 串口通信模块
│   ├── 云端同步/                   # MQTT 客户端
│   ├── 执行器集成/                 # PID 控制器
│   ├── 电机控制/                   # 电机驱动
│   ├── 闭环测试/                   # 闭环测试代码
│   ├── 系统联调/                   # 系统集成
│   └── mqtt_simulator/            # MQTT 模拟器
└── web/                           # 前端
    └── index.html                 # Three.js 3D 可视化
```

## MQTT Topic 结构

```
digital_twin/
├── sensors/
│   ├── temperature     # 温度
│   ├── position        # 位置
│   └── status          # 系统状态
├── actuators/
│   ├── motor_speed     # 电机 PWM 控制
│   └── servo_angle     # 舵机角度
└── system/
    ├── state           # 整体状态
    └── alerts          # 告警消息
```

## 面试能聊的点

- 完整软硬件系统集成能力
- 实时系统：亚秒级延迟数据处理
- MQTT 协议设计：topic 结构、payload 设计
- PID 控制理论实践
- Three.js 场景管理、材质、灯光
- Python 异步编程、串口通信
- 多组件系统调试经验

## 当前状态

核心功能已完成，在持续迭代。后续计划：
- 加入 LLM Agent 能力（自然语言控制）
- 预测性维护模块
- 云端部署

## License

MIT
