# DigitalTwin_Demo 🏭

> Industrial Equipment Digital Twin with Three.js + MQTT + Arduino

A real-time digital twin system for industrial equipment monitoring and control, featuring 3D visualization with Three.js, real-time MQTT communication, Arduino sensor integration, and closed-loop control capabilities.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Three.js](https://img.shields.io/badge/Three.js-r158-green.svg)](https://threejs.org/)
[![MQTT](https://img.shields.io/badge/MQTT-5.0-orange.svg)](https://mqtt.org/)
[![Arduino](https://img.shields.io/badge/Arduino-1.8+-green.svg)](https://www.arduino.cc/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 Project Overview

This project implements a complete digital twin solution for industrial equipment, enabling real-time monitoring, simulation, and control through an integrated system of sensors, microcontrollers, and 3D visualization.

**Core Capabilities**:
- Real-time 3D visualization of industrial equipment
- MQTT-based IoT communication
- Arduino sensor data acquisition
- Closed-loop control system
- State database synchronization

## 🛠️ Tech Stack

- **Frontend**: Three.js, JavaScript
- **Backend**: Python 3.8+, Flask/FastAPI
- **IoT Protocol**: MQTT (Eclipse Mosquitto)
- **Hardware**: Arduino, various sensors (temperature, pressure, position)
- **Database**: SQLite (state management)
- **Communication**: Serial (USB), WiFi, WebSocket

## ✨ Key Features

- **3D Visualization**: Real-time Three.js rendering with PBR materials
- **MQTT Integration**: Pub/Sub architecture for real-time data flow
- **Sensor Fusion**: Multi-sensor data collection and processing
- **Actuator Control**: DC motors, servo motors, stepper motors
- **Closed-Loop Control**: PID control with sensor feedback
- **System Debugging**: Built-in debug panel for development
- **Cloud Sync**: Optional cloud extension for remote monitoring

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Arduino IDE
- MQTT Broker (Eclipse Mosquitto)
- Node.js (optional, for web server)

### Installation

```bash
# Clone the repository
git clone https://github.com/Viandanze/DigitalTwin_Demo.git
cd DigitalTwin_Demo

# Install Python dependencies
pip install paho-mqtt pyserial flask

# Install Arduino libraries (via Arduino IDE Library Manager)
# - PubSubClient
# - ArduinoJson
```

### Hardware Setup

1. Connect Arduino to your PC via USB
2. Upload firmware from `src/Arduino/digital_twin_firmware.ino`
3. Wire sensors according to pin definitions in the firmware

### Run the System

```bash
# Terminal 1: Start MQTT broker
mosquitto -v

# Terminal 2: Start serial bridge
python src/串口通信/arduino_bridge.py

# Terminal 3: Start MQTT simulator (for testing without hardware)
python src/mqtt_simulator/mqtt_simulator.py

# Terminal 4: Start control engine
python src/执行器集成/control_main.py

# Open web browser: src/index.html
```

## 📁 Project Structure

```
DigitalTwin_Demo/
├── src/
│   ├── Arduino/                    # Arduino firmware
│   │   ├── digital_twin_firmware.ino
│   │   └── digital_twin_firmware_v2.ino
│   ├── 传感器采集/                 # Sensor data collection
│   │   └── sensor_collector.py
│   ├── 串口通信/                   # Serial communication
│   │   ├── arduino_bridge.py       # Main bridge
│   │   ├── sensor_data_pipeline.py # Data pipeline
│   │   └── serial_communication_test.py
│   ├── 云端同步/                   # Cloud synchronization
│   │   ├── mqtt_client.py
│   │   ├── api_extensions.py
│   │   └── threejs_cloud_extension.js
│   ├── 执行器集成/                 # Actuator integration
│   │   ├── control_engine.py       # PID controller
│   │   ├── control_main.py
│   │   ├── serial_manager.py
│   │   ├── sensor_simulator.py
│   │   └── threejs_actuator_extension.js
│   ├── 电机控制/                   # Motor control
│   │   ├── dc_motor_pwm.py
│   │   └── stepper_motor_control.py
│   ├── 闭环测试/                   # Closed-loop testing
│   │   └── closed_loop_system.py
│   ├── 系统联调/                   # System integration
│   │   ├── test_integration.py
│   │   ├── update_state_db.py
│   │   └── threejs_debug_panel.js
│   └── mqtt_simulator/             # MQTT testing tools
│       ├── mqtt_simulator.py
│       └── test_simulator.py
├── web/                            # Web frontend
│   ├── index.html                  # Main HTML
│   └── assets/                     # 3D models, textures
├── docs/                           # Documentation
├── README.md
├── .gitignore
└── LICENSE
```

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Digital Twin System                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐      │
│  │   3D View    │◄───►│  MQTT Broker │◄───►│   Control     │      │
│  │  (Three.js)  │     │  (Mosquitto) │     │   Engine      │      │
│  └──────────────┘     └──────┬───────┘     └──────────────┘      │
│         │                    │                    ▲               │
│         │            ┌───────┴───────┐            │               │
│         │            │  Serial Bridge │────────────┘               │
│         │            └───────┬───────┘                              │
│         │                    │                                      │
│  ┌──────▼──────┐     ┌──────▼──────┐     ┌──────────────┐          │
│  │  Database   │◄────│   Arduino   │◄───►│   Sensors    │          │
│  │  (State)    │     │   (UNO/R3)  │     │  Temp/Posi   │          │
│  └─────────────┘     └─────────────┘     └──────────────┘          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Sensors** → Arduino reads sensor data (temperature, position, etc.)
2. **Serial Bridge** → Python reads from Arduino via USB
3. **MQTT Pub** → Python publishes sensor data to MQTT broker
4. **MQTT Sub** → Control engine subscribes to sensor topics
5. **Control** → PID controller computes actuator commands
6. **MQTT Pub** → Commands published to actuator topics
7. **Arduino** → Receives commands, adjusts motor speeds
8. **3D View** → Three.js renders real-time equipment state

## 📊 Technical Highlights

### Interview Value Points

- **Full-Stack IoT**: Complete hardware-to-cloud integration
- **Real-Time Systems**: Sub-second latency data processing
- **Protocol Design**: MQTT topic structure, payload design
- **PID Control**: Classic control theory implementation
- **3D Web Graphics**: Three.js scene management, materials, lighting
- **Multi-Threading**: Python async/await, serial communication
- **System Integration**: Debugging complex multi-component systems

## 🔧 Configuration

MQTT topic structure:
```
digital_twin/
├── sensors/
│   ├── temperature     # Temperature readings
│   ├── position        # Motor position
│   └── status          # System status
├── actuators/
│   ├── motor_speed     # Motor PWM control
│   └── servo_angle     # Servo angle control
└── system/
    ├── state          # Overall system state
    └── alerts         # Alert messages
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👤 Author

**曾炜峻 (Viandanze)**
- GitHub: [https://github.com/Viandanze](https://github.com/Viandanze)
- Focus: Digital Twin, IoT, Industrial Automation

---

*"Bridging the physical and digital worlds"*
