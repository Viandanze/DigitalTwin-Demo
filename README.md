# DigitalTwin-Demo

Industrial equipment digital twin system with real-time sensor data acquisition, MQTT communication, 3D visualization, PID closed-loop control, and LLM Agent integration.

## Tech Stack

- **Frontend:** Three.js + JavaScript (713-line interactive 3D viewer)
- **Backend:** Python 3.8+ (FastAPI/Flask)
- **Protocol:** MQTT (Eclipse Mosquitto)
- **LLM:** Function Calling + ReAct multi-step reasoning
- **RAG:** ChromaDB for equipment manual retrieval
- **Hardware:** Raspberry Pi 5 + Arduino UNO R3 + sensor suite
- **Storage:** SQLite

## Key Features

1. **Real-time Sensor Pipeline**: Arduino → Serial → MQTT → SQLite, temperature/pressure/position at configurable sampling rate
2. **3D Visualization**: Three.js viewer with real-time WebSocket sync — device state changes reflect in 3D scene instantly
3. **PID Closed-loop Control**: Actuator integration with motor driver and servo control, auto-tuning PID parameters
4. **LLM Agent (In Progress)**: Natural language interface for device control — "set fan speed to 1200" → Agent parses intent → MQTT command → device executes
5. **RAG-assisted Decisions**: Equipment technical manuals indexed in ChromaDB, Agent retrieves relevant docs before making control decisions
6. **Anomaly Detection**: Threshold-based alerting with Agent-generated diagnostic suggestions

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
│   ├── mqtt_simulator/             # MQTT simulator (no hardware needed)
│   ├── frontend/
│   │   └── simple_viewer.html      # Three.js 3D visualization
│   ├── 系统联调/                    # System integration modules
│   ├── 执行器集成/                  # Actuator Three.js extensions
│   └── 云端同步/                    # Cloud sync extensions
└── README.md
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

## Quick Start

### MQTT Simulator (No Hardware)

```bash
# Start MQTT broker
mosquitto -d

# Run simulator
python src/mqtt_simulator/simulator.py

# Open 3D viewer
open src/frontend/simple_viewer.html
```

### With Real Hardware

```bash
# Flash Arduino firmware
# Connect sensors and actuators
# Start serial bridge
python src/serial_comm/serial_bridge.py

# Start MQTT client
python src/cloud_sync/mqtt_client.py

# Open 3D viewer
open src/frontend/simple_viewer.html
```

## License

MIT
