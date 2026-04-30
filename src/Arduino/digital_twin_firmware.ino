/**
 * Arduino数字孪生传感器采集固件
 * 版本: v1.0
 * 创建时间: 2026-04-11
 * 描述: 整合DHT11、HC-SR04、BMP280、光敏传感器的数据采集
 *       支持上位机指令控制执行器（电机、舵机）
 */

#include <DHT.h>
#include <Wire.h>
#include <Adafruit_BMP280.h>
#include <NewPing.h>
#include <Servo.h>

// ============================================================================
// 引脚定义
// ============================================================================

// DHT11 温湿度传感器
#define DHT_PIN 2
#define DHT_TYPE DHT11
DHT dht(DHT_PIN, DHT_TYPE);

// HC-SR04 超声波测距
#define TRIG_PIN 3
#define ECHO_PIN 4
#define MAX_DISTANCE 200  // cm
NewPing sonar(TRIG_PIN, ECHO_PIN, MAX_DISTANCE);

// 光敏传感器（模拟输入）
#define LIGHT_PIN A0

// L298N 电机驱动
#define ENA 5   // PWM调速
#define IN1 6   // 方向控制
#define IN2 7   // 方向控制

// SG90 舵机
#define SERVO_PIN 9
Servo myservo;

// ============================================================================
// 全局变量
// ============================================================================
unsigned long lastSensorRead = 0;
const unsigned long SENSOR_INTERVAL = 1000;  // 读取间隔 ms

// 电机状态
int currentMotorSpeed = 0;
int currentMotorDir = 0;  // 0=停止, 1=正转, 2=反转

// 舵机状态
int currentServoAngle = 90;

// ============================================================================
// 初始化
// ============================================================================
void setup() {
    Serial.begin(115200);  // 高速串口通信
    
    // 等待串口稳定
    while (!Serial && millis() < 3000);
    
    // 初始化传感器
    dht.begin();
    Serial.println("{\"status\":\"DHT11_INIT_OK\"}");
    
    // BMP280 I2C初始化
    if (!bmp280.begin(0x76)) {
        Serial.println("{\"status\":\"BMP280_INIT_FAILED\"}");
    } else {
        Serial.println("{\"status\":\"BMP280_INIT_OK\"}");
    }
    
    // 执行器引脚模式
    pinMode(ENA, OUTPUT);
    pinMode(IN1, OUTPUT);
    pinMode(IN2, OUTPUT);
    motorStop();  // 初始化为停止状态
    
    // 舵机初始化
    myservo.attach(SERVO_PIN);
    myservo.write(currentServoAngle);
    
    // 固件就绪通知
    Serial.println("{\"type\":\"system\",\"msg\":\"Arduino Digital Twin Firmware Ready\",\"version\":\"1.0\"}");
}

Adafruit_BMP280 bmp280;  // BMP280对象声明

// ============================================================================
// 主循环
// ============================================================================
void loop() {
    // 按间隔读取传感器
    if (millis() - lastSensorRead >= SENSOR_INTERVAL) {
        lastSensorRead = millis();
        readAllSensors();
    }
    
    // 处理上位机指令
    if (Serial.available()) {
        processCommand();
    }
}

// ============================================================================
// 传感器读取
// ============================================================================
void readAllSensors() {
    // 读取DHT11
    float humidity = dht.readHumidity();
    float tempDHT = dht.readTemperature();
    
    // 处理DHT11读取失败
    if (isnan(humidity) || isnan(tempDHT)) {
        Serial.println("{\"type\":\"error\",\"sensor\":\"DHT11\",\"msg\":\"Read failed\"}");
        humidity = -1;
        tempDHT = -1;
    }
    
    // 读取超声波（多次采样取中位数）
    int distance = sonar.ping_median(5);
    distance = sonar.convert_cm(distance);
    
    // 读取光敏（模拟值0-1023）
    int light = analogRead(LIGHT_PIN);
    
    // 读取BMP280
    float pressure = bmp280.readPressure() / 100.0F;  // Pa → hPa
    float tempBMP = bmp280.readTemperature();
    
    // 构建JSON输出
    Serial.print("{\"type\":\"sensor\",\"data\":{");
    Serial.print("\"humidity\":"); Serial.print(humidity, 1);
    Serial.print(",\"temp_dht\":"); Serial.print(tempDHT, 1);
    Serial.print(",\"temp_bmp\":"); Serial.print(tempBMP, 1);
    Serial.print(",\"pressure\":"); Serial.print(pressure, 1);
    Serial.print(",\"distance\":"); Serial.print(distance);
    Serial.print(",\"light\":"); Serial.print(light);
    Serial.print(",\"timestamp\":"); Serial.print(millis());
    Serial.println("}}");
}

// ============================================================================
// 指令处理
// ============================================================================
void processCommand() {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    
    if (cmd.length() == 0) return;
    
    // PING指令 - 心跳检测
    if (cmd == "PING") {
        Serial.print("{\"type\":\"pong\",\"timestamp\":");
        Serial.print(millis());
        Serial.println("}");
        return;
    }
    
    // GET_STATUS - 获取设备状态
    if (cmd == "GET_STATUS") {
        Serial.print("{\"type\":\"status\",\"motor\":{\"speed\":");
        Serial.print(currentMotorSpeed);
        Serial.print(",\"direction\":");
        Serial.print(currentMotorDir);
        Serial.print("},\"servo\":{\"angle\":");
        Serial.print(currentServoAngle);
        Serial.print("},\"uptime\":");
        Serial.print(millis());
        Serial.println("}}");
        return;
    }
    
    // SET_MOTOR speed direction - 电机控制
    // speed: 0-255, direction: 0=停止, 1=正转, 2=反转
    if (cmd.startsWith("SET_MOTOR")) {
        int spaceIdx = cmd.indexOf(' ');
        if (spaceIdx > 0) {
            int speed = cmd.substring(spaceIdx + 1).toInt();
            int dirIdx = cmd.indexOf(' ', spaceIdx + 1);
            int direction = 0;
            if (dirIdx > 0) {
                direction = cmd.substring(dirIdx + 1).toInt();
            }
            setMotor(speed, direction);
        }
        return;
    }
    
    // SET_SERVO angle - 舵机控制
    // angle: 0-180
    if (cmd.startsWith("SET_SERVO")) {
        int angle = cmd.substring(10).toInt();
        setServo(angle);
        return;
    }
    
    // UNKNOWN指令
    Serial.print("{\"type\":\"error\",\"cmd\":\"UNKNOWN\",\"msg\":\"");
    Serial.print(cmd);
    Serial.println("\"}");
}

// ============================================================================
// 电机控制函数
// ============================================================================
void setMotor(int speed, int direction) {
    speed = constrain(speed, 0, 255);
    direction = constrain(direction, 0, 2);
    
    currentMotorSpeed = speed;
    currentMotorDir = direction;
    
    switch (direction) {
        case 0:  // 停止
            digitalWrite(IN1, LOW);
            digitalWrite(IN2, LOW);
            analogWrite(ENA, 0);
            break;
        case 1:  // 正转
            digitalWrite(IN1, HIGH);
            digitalWrite(IN2, LOW);
            analogWrite(ENA, speed);
            break;
        case 2:  // 反转
            digitalWrite(IN1, LOW);
            digitalWrite(IN2, HIGH);
            analogWrite(ENA, speed);
            break;
    }
    
    // 确认消息
    Serial.print("{\"type\":\"motor\",\"speed\":");
    Serial.print(speed);
    Serial.print(",\"direction\":");
    Serial.print(direction);
    Serial.println("}");
}

void motorStop() {
    setMotor(0, 0);
}

// ============================================================================
// 舵机控制函数
// ============================================================================
void setServo(int angle) {
    angle = constrain(angle, 0, 180);
    currentServoAngle = angle;
    myservo.write(angle);
    
    // 确认消息
    Serial.print("{\"type\":\"servo\",\"angle\":");
    Serial.print(angle);
    Serial.println("}");
}
