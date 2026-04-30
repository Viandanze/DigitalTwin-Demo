/**
 * Arduino数字孪生传感器采集固件 - 增强版
 * 版本: v2.0
 * 创建时间: 2026-04-12
 * 更新: 添加安全保护、移动平均滤波、校准功能
 * 
 * 功能：
 * 1. 多传感器采集（DHT11、HC-SR04、BMP280、光敏）
 * 2. 执行器控制（电机、舵机）
 * 3. 移动平均滤波
 * 4. 安全保护（温度/电流监控）
 * 5. 校准功能
 * 6. 指令式通信协议
 */

#include <DHT.h>
#include <Wire.h>
#include <Adafruit_BMP280.h>
#include <NewPing.h>
#include <Servo.h>

// ============================================================================
// 版本信息
// ============================================================================
#define FIRMWARE_VERSION "v2.0"
#define BUILD_DATE "2026-04-12"

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

// 电流检测（可选）
#define CURRENT_SENSOR_PIN A1

// SG90 舵机
#define SERVO_PIN 9
Servo myservo;

// ============================================================================
// 配置参数
// ============================================================================

// 传感器采样间隔 (ms)
#define SENSOR_INTERVAL 1000

// 移动平均滤波器窗口大小
#define FILTER_WINDOW 5

// 安全阈值
#define TEMP_MAX 60.0        // 最高温度 (°C)
#define TEMP_MIN -10.0       // 最低温度 (°C)
#define CURRENT_MAX 2000     // 最大电流 (mA)

// 串口配置
#define BAUD_RATE 115200

// ============================================================================
// 全局变量
// ============================================================================

// 状态变量
unsigned long lastSensorRead = 0;
unsigned long systemStartTime = 0;
uint16_t systemRestartCount = 0;

// 电机状态
int currentMotorSpeed = 0;
int currentMotorDir = 0;  // 0=停止, 1=正转, 2=反转

// 舵机状态
int currentServoAngle = 90;

// 安全标志
bool safetyEnabled = true;
bool emergencyStop = false;

// 校准偏移
float calibTemp = 0.0;
float calibHumidity = 0.0;
float calibPressure = 0.0;
float calibDistance = 0.0;
float calibLight = 0.0;

// ============================================================================
// 移动平均滤波器
// ============================================================================

template<typename T, size_t N>
class MovingAverage {
private:
    T buffer[N];
    size_t index = 0;
    size_t count = 0;
    T sum = 0;

public:
    void add(T value) {
        if (count < N) {
            count++;
            sum += value;
        } else {
            sum -= buffer[index];
            sum += value;
        }
        buffer[index] = value;
        index = (index + 1) % N;
    }

    T getAverage() {
        if (count == 0) return 0;
        return sum / count;
    }

    T getMedian() {
        if (count == 0) return 0;
        // 简单实现：返回平均值
        return sum / count;
    }

    void reset() {
        index = 0;
        count = 0;
        sum = 0;
    }
};

// 滤波器实例
MovingAverage<float, FILTER_WINDOW> avgTempDHT;
MovingAverage<float, FILTER_WINDOW> avgTempBMP;
MovingAverage<float, FILTER_WINDOW> avgHumidity;
MovingAverage<float, FILTER_WINDOW> avgDistance;
MovingAverage<int, FILTER_WINDOW> avgLight;
MovingAverage<float, FILTER_WINDOW> avgPressure;

// ============================================================================
// BMP280对象
// ============================================================================
Adafruit_BMP280 bmp280;

// ============================================================================
// 初始化
// ============================================================================
void setup() {
    Serial.begin(BAUD_RATE);
    
    // 等待串口稳定
    unsigned long start = millis();
    while (!Serial && (millis() - start < 3000));
    
    systemStartTime = millis();
    
    // 初始化传感器
    initSensors();
    
    // 初始化执行器
    initActuators();
    
    // 发送启动信息
    sendSystemInfo();
}

// ============================================================================
// 主循环
// ============================================================================
void loop() {
    // 按间隔读取传感器
    if (millis() - lastSensorRead >= SENSOR_INTERVAL) {
        lastSensorRead = millis();
        readAndFilterSensors();
        outputSensorData();
    }
    
    // 检查安全状态
    if (safetyEnabled) {
        checkSafetyConditions();
    }
    
    // 处理上位机指令
    if (Serial.available()) {
        processCommand();
    }
}

// ============================================================================
// 传感器初始化
// ============================================================================
void initSensors() {
    // DHT11
    dht.begin();
    Serial.print("{\"type\":\"status\",\"msg\":\"DHT11_INIT_OK\"}");
    
    // BMP280 I2C
    if (!bmp280.begin(0x76)) {
        Serial.print(",\"bmp280\":\"FAILED\"}");
    } else {
        Serial.print(",\"bmp280\":\"OK\"}");
    }
    
    // 设置BMP280配置
    bmp280.setSampling(Adafruit_BMP280::MODE_NORMAL,
                      Adafruit_BMP280::SAMPLING_X2,
                      Adafruit_BMP280::SAMPLING_X16,
                      Adafruit_BMP280::FILTER_X16,
                      Adafruit_BMP280::STANDBY_MS_500);
    
    // 光敏引脚
    pinMode(LIGHT_PIN, INPUT);
    
    Serial.println("}");
}

// ============================================================================
// 执行器初始化
// ============================================================================
void initActuators() {
    // 电机引脚
    pinMode(ENA, OUTPUT);
    pinMode(IN1, OUTPUT);
    pinMode(IN2, OUTPUT);
    motorStop();
    
    // 电流检测引脚
    pinMode(CURRENT_SENSOR_PIN, INPUT);
    
    // 舵机
    myservo.attach(SERVO_PIN);
    myservo.write(currentServoAngle);
}

// ============================================================================
// 系统信息
// ============================================================================
void sendSystemInfo() {
    Serial.print("{\"type\":\"system\"");
    Serial.print(",\"version\":\"");
    Serial.print(FIRMWARE_VERSION);
    Serial.print("\"");
    Serial.print(",\"build\":\"");
    Serial.print(BUILD_DATE);
    Serial.print("\"");
    Serial.print(",\"uptime\":");
    Serial.print(millis());
    Serial.print(",\"filter_window\":");
    Serial.print(FILTER_WINDOW);
    Serial.println("}");
}

// ============================================================================
// 读取并滤波传感器数据
// ============================================================================
void readAndFilterSensors() {
    // 读取DHT11
    float humidity = dht.readHumidity();
    float tempDHT = dht.readTemperature();
    
    // 处理DHT11异常值
    if (isnan(humidity) || isnan(tempDHT)) {
        humidity = -1;
        tempDHT = -1;
    } else {
        humidity += calibHumidity;
        tempDHT += calibTemp;
        avgHumidity.add(humidity);
        avgTempDHT.add(tempDHT);
    }
    
    // 读取超声波（多次采样取中位数）
    int distanceRaw = sonar.ping_median(5);
    float distance = sonar.convert_cm(distanceRaw) + calibDistance;
    if (distance > 0) {
        avgDistance.add(distance);
    }
    
    // 读取光敏（模拟值0-1023）
    int light = analogRead(LIGHT_PIN) + (int)calibLight;
    light = constrain(light, 0, 1023);
    avgLight.add(light);
    
    // 读取BMP280
    float pressure = bmp280.readPressure() / 100.0F + calibPressure;
    float tempBMP = bmp280.readTemperature() + calibTemp;
    if (tempBMP > -50 && tempBMP < 100) {
        avgTempBMP.add(tempBMP);
        avgPressure.add(pressure);
    }
}

// ============================================================================
// 输出滤波后的传感器数据
// ============================================================================
void outputSensorData() {
    Serial.print("{\"type\":\"sensor\"");
    Serial.print(",\"humidity\":"); Serial.print(avgHumidity.getAverage(), 1);
    Serial.print(",\"temp_dht\":"); Serial.print(avgTempDHT.getAverage(), 1);
    Serial.print(",\"temp_bmp\":"); Serial.print(avgTempBMP.getAverage(), 1);
    Serial.print(",\"pressure\":"); Serial.print(avgPressure.getAverage(), 1);
    Serial.print(",\"distance\":"); Serial.print((int)avgDistance.getAverage());
    Serial.print(",\"light\":"); Serial.print(avgLight.getAverage());
    Serial.print(",\"current\":"); Serial.print(readCurrent());
    Serial.print(",\"uptime\":"); Serial.print(millis());
    Serial.println("}");
}

// ============================================================================
// 读取电流值
// ============================================================================
int readCurrent() {
    // ACS712电流传感器（需根据实际型号调整）
    int rawValue = analogRead(CURRENT_SENSOR_PIN);
    // 简单转换：0-1023 -> 0-5000mA（示例）
    int current = map(rawValue, 0, 1023, 0, 5000);
    return current;
}

// ============================================================================
// 安全检查
// ============================================================================
void checkSafetyConditions() {
    float temp = avgTempDHT.getAverage();
    
    // 温度超限检查
    if (temp > TEMP_MAX || temp < TEMP_MIN) {
        Serial.print("{\"type\":\"safety\",\"level\":\"WARNING\"");
        Serial.print(",\"reason\":\"TEMP_OUT_OF_RANGE\"");
        Serial.print(",\"temp\":"); Serial.print(temp);
        Serial.println("}");
    }
    
    // 电流超限检查
    int current = readCurrent();
    if (current > CURRENT_MAX) {
        Serial.print("{\"type\":\"safety\",\"level\":\"CRITICAL\"");
        Serial.print(",\"reason\":\"CURRENT_OVERLOAD\"");
        Serial.print(",\"current\":"); Serial.print(current);
        Serial.println("}");
        // 紧急停止电机
        motorStop();
        Serial.println("{\"type\":\"safety\",\"action\":\"MOTOR_EMERGENCY_STOP\"}");
    }
    
    // 紧急停止检查
    if (emergencyStop) {
        motorStop();
        myservo.write(90);
        Serial.println("{\"type\":\"safety\",\"action\":\"EMERGENCY_STOP_ACTIVE\"}");
    }
}

// ============================================================================
// 指令处理
// ============================================================================
void processCommand() {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toUpperCase();
    
    if (cmd.length() == 0) return;
    
    // ========== 系统指令 ==========
    
    // PING - 心跳检测
    if (cmd == "PING") {
        Serial.print("{\"type\":\"pong\",\"timestamp\":");
        Serial.print(millis());
        Serial.println("}");
        return;
    }
    
    // GET_INFO - 获取系统信息
    if (cmd == "GET_INFO") {
        sendSystemInfo();
        return;
    }
    
    // GET_STATUS - 获取设备状态
    if (cmd == "GET_STATUS") {
        Serial.print("{\"type\":\"status\"");
        Serial.print(",\"motor\":{\"speed\":");
        Serial.print(currentMotorSpeed);
        Serial.print(",\"direction\":");
        Serial.print(currentMotorDir);
        Serial.print("}");
        Serial.print(",\"servo\":{\"angle\":");
        Serial.print(currentServoAngle);
        Serial.print("}");
        Serial.print(",\"safety\":{\"enabled\":");
        Serial.print(safetyEnabled ? "true" : "false");
        Serial.print(",\"emergency\":");
        Serial.print(emergencyStop ? "true" : "false");
        Serial.print("}");
        Serial.print(",\"calib\":{\"temp\":");
        Serial.print(calibTemp);
        Serial.print(",\"humidity\":");
        Serial.print(calibHumidity);
        Serial.print(",\"pressure\":");
        Serial.print(calibPressure);
        Serial.print(",\"distance\":");
        Serial.print(calibDistance);
        Serial.print(",\"light\":");
        Serial.print(calibLight);
        Serial.print("}");
        Serial.print(",\"uptime\":");
        Serial.print(millis());
        Serial.println("}}");
        return;
    }
    
    // RESET - 软件复位
    if (cmd == "RESET") {
        Serial.println("{\"type\":\"system\",\"action\":\"RESET\"}");
        delay(100);
        // 使用看门狗复位或软件复位
        asm volatile ("  jmp 0");
        return;
    }
    
    // STOP_ALL - 停止所有执行器
    if (cmd == "STOP_ALL") {
        emergencyStop = true;
        motorStop();
        myservo.write(90);
        Serial.println("{\"type\":\"action\",\"result\":\"STOP_ALL_OK\"}");
        return;
    }
    
    // RESUME - 恢复执行器
    if (cmd == "RESUME") {
        emergencyStop = false;
        Serial.println("{\"type\":\"action\",\"result\":\"RESUME_OK\"}");
        return;
    }
    
    // ========== 执行器控制 ==========
    
    // SET_MOTOR speed direction - 电机控制
    if (cmd.startsWith("SET_MOTOR")) {
        if (emergencyStop) {
            Serial.println("{\"type\":\"error\",\"reason\":\"EMERGENCY_STOP_ACTIVE\"}");
            return;
        }
        
        int spaceIdx = cmd.indexOf(' ');
        if (spaceIdx > 0) {
            int speed = cmd.substring(spaceIdx + 1).toInt();
            int dirIdx = cmd.indexOf(' ', spaceIdx + 1);
            int direction = 0;
            if (dirIdx > 0) {
                direction = cmd.substring(dirIdx + 1).toInt();
            }
            setMotor(speed, direction);
        } else {
            Serial.println("{\"type\":\"error\",\"cmd\":\"INVALID_MOTOR_PARAMS\"}");
        }
        return;
    }
    
    // STOP_MOTOR - 停止电机
    if (cmd == "STOP_MOTOR") {
        motorStop();
        Serial.println("{\"type\":\"action\",\"result\":\"MOTOR_STOPPED\"}");
        return;
    }
    
    // SET_SERVO angle - 舵机控制
    if (cmd.startsWith("SET_SERVO")) {
        if (emergencyStop) {
            Serial.println("{\"type\":\"error\",\"reason\":\"EMERGENCY_STOP_ACTIVE\"}");
            return;
        }
        
        int angle = cmd.substring(10).toInt();
        setServo(angle);
        return;
    }
    
    // ========== 校准指令 ==========
    
    // CALIB_READ - 读取当前值作为校准基准
    if (cmd == "CALIB_READ") {
        calibTemp = 0;
        calibHumidity = 0;
        calibPressure = 0;
        calibDistance = 0;
        calibLight = 0;
        
        // 获取当前滤波后的值
        float baseTemp = avgTempDHT.getAverage();
        float baseHumidity = avgHumidity.getAverage();
        float basePressure = avgPressure.getAverage();
        float baseDistance = avgDistance.getAverage();
        float baseLight = avgLight.getAverage();
        
        Serial.print("{\"type\":\"calib\",\"基准\":\"当前值已记录\"");
        Serial.print(",\"base_temp\":"); Serial.print(baseTemp);
        Serial.print(",\"base_humidity\":"); Serial.print(baseHumidity);
        Serial.print(",\"base_pressure\":"); Serial.print(basePressure);
        Serial.print(",\"base_distance\":"); Serial.print(baseDistance);
        Serial.print(",\"base_light\":"); Serial.print(baseLight);
        Serial.println("}");
        return;
    }
    
    // CALIB_SET sensor value - 设置校准偏移
    if (cmd.startsWith("CALIB_SET")) {
        int space1 = cmd.indexOf(' ');
        int space2 = cmd.indexOf(' ', space1 + 1);
        if (space1 > 0 && space2 > 0) {
            String sensor = cmd.substring(space1 + 1, space2);
            float value = cmd.substring(space2 + 1).toFloat();
            
            if (sensor == "TEMP") calibTemp = value;
            else if (sensor == "HUMIDITY") calibHumidity = value;
            else if (sensor == "PRESSURE") calibPressure = value;
            else if (sensor == "DISTANCE") calibDistance = value;
            else if (sensor == "LIGHT") calibLight = value;
            else {
                Serial.println("{\"type\":\"error\",\"sensor\":\"UNKNOWN\"}");
                return;
            }
            
            Serial.print("{\"type\":\"calib\",\"sensor\":\"");
            Serial.print(sensor);
            Serial.print("\",\"offset\":");
            Serial.print(value);
            Serial.println("}");
        }
        return;
    }
    
    // CALIB_RESET - 重置校准
    if (cmd == "CALIB_RESET") {
        calibTemp = 0;
        calibHumidity = 0;
        calibPressure = 0;
        calibDistance = 0;
        calibLight = 0;
        Serial.println("{\"type\":\"calib\",\"action\":\"RESET\"}");
        return;
    }
    
    // ========== 滤波器控制 ==========
    
    // FILTER_RESET - 重置滤波器
    if (cmd == "FILTER_RESET") {
        avgTempDHT.reset();
        avgTempBMP.reset();
        avgHumidity.reset();
        avgDistance.reset();
        avgLight.reset();
        avgPressure.reset();
        Serial.println("{\"type\":\"filter\",\"action\":\"RESET\"}");
        return;
    }
    
    // ========== 安全控制 ==========
    
    // SAFETY_ON / SAFETY_OFF - 安全开关
    if (cmd == "SAFETY_ON") {
        safetyEnabled = true;
        Serial.println("{\"type\":\"safety\",\"enabled\":true}");
        return;
    }
    if (cmd == "SAFETY_OFF") {
        safetyEnabled = false;
        Serial.println("{\"type\":\"safety\",\"enabled\":false}");
        return;
    }
    
    // UNKNOWN指令
    Serial.print("{\"type\":\"error\",\"cmd\":\"UNKNOWN\",\"received\":\"");
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
