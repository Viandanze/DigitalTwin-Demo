# DigitalTwin-Demo

Industrial equipment digital twin system with real-time sensor data acquisition, MQTT communication, 3D visualization, and PID closed-loop control.

## Tech Stack

- **Frontend:** Three.js + JavaScript
- **Backend:** Python 3.8+ (FastAPI/Flask)
- **Protocol:** MQTT (Eclipse Mosquitto)
- **Hardware:** Arduino + sensor suite
- **Storage:** SQLite

Hardware: Raspberry Pi 5 + Arduino UNO R3 + sensor suite (temperature/pressure/position)

## System Architecture

```
Sensor → Arduino → Serial → Python Bridge → MQTT Broker → Control Engine
                                                      ↓
                                           Web (Three.js) ← Real-time rendering
```

Data flow:
1. Arduino reads sensor data
2. Python receives data via serial port
3. Data published to MQTT Broker
4. Control engine subscribes to sensor topics
5. PID controller computes control output
6. Control commands published to actuator topics
7. Arduino receives commands and adjusts motors
8. Three.js renders latest state

## Quick Start

### Prerequisites

- Python 3.8+
- Arduino IDE
- MQTT Broker (Eclipse Mosquitto)

### Installation

```bash
git clone https://github.com/Viandanze/DigitalTwin-Demo.git
cd DigitalTwin-Demo

pip install paho-mqtt pyserial flask fastapi

# Arduino libraries (via Arduino IDE Library Manager)
# - PubSubClient
# - ArduinoJson
```

### Startup Sequence

```bash
# Terminal 1: Start MQTT broker
mosquitto -v

# Terminal 2: Start serial bridge
python src/serial_comm/arduino_bridge.py

# Terminal 3: Run simulator (if no hardware)
python src/mqtt_simulator/mqtt_simulator.py

# Terminal 4: Start control engine
python src/actuator_integration/control_main.py

# Open browser to src/index.html
```

## Project Structure

```
DigitalTwin-Demo/
├── src/
│   ├── Arduino/                    # Arduino firmware
│   ├── sensor_acquisition/         # Sensor data collection
│   ├── serial_comm/                # Serial communication
│   ├── cloud_sync/                 # MQTT client
│   ├── actuator_integration/       # PID controller
│   ├── motor_control/              # Motor drivers
│   ├── closed_loop_test/           # Closed-loop testing
│   ├── system_integration/         # System integration
│   └── mqtt_simulator/            # MQTT simulator
└── web/                           # Frontend
    └── index.html                 # Three.js 3D visualization
```

## MQTT Topics

```
digital_twin/
├── sensors/
│   ├── temperature
│   ├── position
│   └── status
├── actuators/
│   ├── motor_speed
│   └── servo_angle
└── system/
    ├── state
    └── alerts
```

## Known Issues

- **Missing Three.js frontend**: The `src/` directory currently contains only backend Python code and Arduino firmware. The Three.js 3D visualization page (`index.html`) has not been uploaded yet. All backend components (MQTT communication, serial bridge, control engine, simulator) are fully functional.

## License

MIT
