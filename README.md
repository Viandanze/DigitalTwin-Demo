# DigitalTwin-Demo

Industrial equipment digital twin system with real-time sensor data acquisition, MQTT communication, 3D visualization, and PID closed-loop control.

## Tech Stack

- **Frontend:** Three.js + JavaScript
- **Backend:** Python 3.8+ (FastAPI/Flask)
- **Protocol:** MQTT (Eclipse Mosquitto)
- **Hardware:** Arduino + sensor suite
- **Storage:** SQLite

Hardware: Raspberry Pi 5 + Arduino UNO R3 + sensor suite (temperature/pressure/position)

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
