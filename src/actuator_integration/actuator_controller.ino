/**
 * Arduino执行器控制器
 * 功能：接收树莓派控制指令，控制直流电机、舵机、步进电机，反馈执行器状态
 * 硬件连接：
 *  直流电机 (L298N):
 *    IN1 -> D2
 *    IN2 -> D3
 *    ENA -> D11 (PWM)
 *  舵机 (SG90):
 *    信号线 -> D9 (PWM)
 *  步进电机 (28BYJ-48 + ULN2003):
 *    IN1 -> D8
 *    IN2 -> D7
 *    IN3 -> D6
 *    IN4 -> D5
 * 串口通信：与树莓派通信，波特率115200
 */

#include <Servo.h>

// ==================== 引脚定义 ====================

// L298N直流电机控制引脚
const int MOTOR_IN1 = 2;      // 方向控制1
const int MOTOR_IN2 = 3;      // 方向控制2
const int MOTOR_ENA = 11;     // PWM调速 (必须支持PWM)

// SG90舵机控制引脚
const int SERVO_PIN = 9;      // 舵机PWM控制 (必须支持PWM)

// ULN2003步进电机控制引脚
const int STEPPER_IN1 = 8;    // 相位A
const int STEPPER_IN2 = 7;    // 相位B
const int STEPPER_IN3 = 6;    // 相位C
const int STEPPER_IN4 = 5;    // 相位D

// ==================== 全局对象 ====================

// 舵机对象
Servo sg90;

// 步进电机步序表 (四相八拍)
const int STEP_SEQUENCE[8][4] = {
  {1, 0, 0, 0},
  {1, 1, 0, 0},
  {0, 1, 0, 0},
  {0, 1, 1, 0},
  {0, 0, 1, 0},
  {0, 0, 1, 1},
  {0, 0, 0, 1},
  {1, 0, 0, 1}
};

// ==================== 全局变量 ====================

// 执行器状态
struct ActuatorStatus {
  // 直流电机状态
  int motorSpeed;      // 当前速度 (0-100%)
  int motorDirection;  // 当前方向 (0=正转, 1=反转)
  
  // 舵机状态
  int servoAngle;      // 当前角度 (0-180°)
  
  // 步进电机状态
  long stepperPosition; // 当前位置 (步)
  int stepperDirection; // 当前方向 (0=正向, 1=反向)
  
  // 更新时间戳
  unsigned long lastUpdateTime;
};

ActuatorStatus status = {
  .motorSpeed = 0,
  .motorDirection = 0,
  .servoAngle = 90,
  .stepperPosition = 0,
  .stepperDirection = 0,
  .lastUpdateTime = 0
};

// 步进电机控制变量
int stepperStepIndex = 0;       // 当前步序索引
unsigned long stepperLastStepTime = 0;
unsigned long stepperStepDelay = 2000; // 初始延迟 (微秒)，约500步/秒

// 串口缓冲区
const int BUFFER_SIZE = 64;
char inputBuffer[BUFFER_SIZE];
int bufferIndex = 0;

// ==================== 初始化函数 ====================

void setup() {
  // 初始化串口通信
  Serial.begin(115200);
  while (!Serial) {
    ; // 等待串口连接
  }
  
  // 打印启动信息
  Serial.println("=== Arduino执行器控制器 v1.0 ===");
  Serial.println("指令格式:");
  Serial.println("  MOTOR:DIR:SPEED    # 直流电机控制");
  Serial.println("  SERVO:ANGLE        # 舵机角度控制");
  Serial.println("  STEPPER:DIR:STEPS  # 步进电机控制");
  Serial.println("  STATUS:ALL         # 查询所有状态");
  Serial.println("  RESET              # 重置所有执行器");
  Serial.println();
  
  // 初始化GPIO引脚
  initializePins();
  
  // 初始化舵机
  sg90.attach(SERVO_PIN);
  sg90.write(status.servoAngle);
  delay(500); // 等待舵机稳定
  
  // 发送初始状态
  sendStatusUpdate();
  
  Serial.println("系统初始化完成，等待指令...");
}

// 初始化所有引脚
void initializePins() {
  // 直流电机引脚
  pinMode(MOTOR_IN1, OUTPUT);
  pinMode(MOTOR_IN2, OUTPUT);
  pinMode(MOTOR_ENA, OUTPUT);
  
  // 步进电机引脚
  pinMode(STEPPER_IN1, OUTPUT);
  pinMode(STEPPER_IN2, OUTPUT);
  pinMode(STEPPER_IN3, OUTPUT);
  pinMode(STEPPER_IN4, OUTPUT);
  
  // 初始状态
  digitalWrite(MOTOR_IN1, LOW);
  digitalWrite(MOTOR_IN2, LOW);
  analogWrite(MOTOR_ENA, 0);
  
  digitalWrite(STEPPER_IN1, LOW);
  digitalWrite(STEPPER_IN2, LOW);
  digitalWrite(STEPPER_IN3, LOW);
  digitalWrite(STEPPER_IN4, LOW);
}

// ==================== 主循环 ====================

void loop() {
  // 检查串口输入
  checkSerialInput();
  
  // 更新步进电机位置
  updateStepper();
  
  // 定期发送状态更新
  static unsigned long lastStatusUpdate = 0;
  if (millis() - lastStatusUpdate > 1000) {
    sendStatusUpdate();
    lastStatusUpdate = millis();
  }
  
  // 短暂延迟，避免过于频繁的循环
  delay(10);
}

// ==================== 串口通信函数 ====================

// 检查串口输入
void checkSerialInput() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    
    // 处理换行符（指令结束）
    if (c == '\n') {
      inputBuffer[bufferIndex] = '\0'; // 添加字符串结束符
      processCommand(inputBuffer);
      bufferIndex = 0; // 重置缓冲区
      memset(inputBuffer, 0, BUFFER_SIZE); // 清空缓冲区
    }
    // 处理回车符
    else if (c == '\r') {
      // 忽略，等待换行符
    }
    // 存储字符到缓冲区
    else if (bufferIndex < BUFFER_SIZE - 1) {
      inputBuffer[bufferIndex] = c;
      bufferIndex++;
    }
    // 缓冲区溢出
    else {
      Serial.println("ERROR:BUFFER_OVERFLOW");
      bufferIndex = 0;
      memset(inputBuffer, 0, BUFFER_SIZE);
    }
  }
}

// 处理接收到的指令
void processCommand(const char* command) {
  Serial.print("接收指令: ");
  Serial.println(command);
  
  // 解析指令
  char cmdType[16];
  char param1[16];
  char param2[16];
  
  // 解析字符串 (格式: TYPE:PARAM1:PARAM2)
  int parseCount = sscanf(command, "%15[^:]:%15[^:]:%15s", cmdType, param1, param2);
  
  if (parseCount < 1) {
    Serial.println("ERROR:INVALID_FORMAT");
    return;
  }
  
  // 根据指令类型处理
  if (strcmp(cmdType, "MOTOR") == 0) {
    // 格式: MOTOR:DIR:SPEED
    if (parseCount >= 3) {
      int dir = atoi(param1);
      int speed = atoi(param2);
      controlDCMotor(dir, speed);
    } else {
      Serial.println("ERROR:MOTOR_INVALID_PARAMS");
    }
  }
  else if (strcmp(cmdType, "SERVO") == 0) {
    // 格式: SERVO:ANGLE
    if (parseCount >= 2) {
      int angle = atoi(param1);
      controlServo(angle);
    } else {
      Serial.println("ERROR:SERVO_INVALID_PARAMS");
    }
  }
  else if (strcmp(cmdType, "STEPPER") == 0) {
    // 格式: STEPPER:DIR:STEPS
    if (parseCount >= 3) {
      int dir = atoi(param1);
      int steps = atoi(param2);
      controlStepper(dir, steps);
    } else {
      Serial.println("ERROR:STEPPER_INVALID_PARAMS");
    }
  }
  else if (strcmp(cmdType, "STATUS") == 0) {
    // 格式: STATUS:ALL
    sendStatusUpdate();
  }
  else if (strcmp(cmdType, "RESET") == 0) {
    // 重置所有执行器
    resetAllActuators();
  }
  else {
    Serial.print("ERROR:UNKNOWN_COMMAND:");
    Serial.println(cmdType);
  }
}

// ==================== 直流电机控制函数 ====================

// 控制直流电机
void controlDCMotor(int direction, int speed) {
  // 验证参数
  if (direction < 0 || direction > 1) {
    Serial.println("ERROR:MOTOR_INVALID_DIRECTION");
    return;
  }
  
  if (speed < 0) speed = 0;
  if (speed > 100) speed = 100;
  
  // 更新状态
  status.motorDirection = direction;
  status.motorSpeed = speed;
  
  // 计算PWM值 (0-255)
  int pwmValue = map(speed, 0, 100, 0, 255);
  
  // 控制电机
  if (direction == 0) {
    // 正转
    digitalWrite(MOTOR_IN1, HIGH);
    digitalWrite(MOTOR_IN2, LOW);
  } else {
    // 反转
    digitalWrite(MOTOR_IN1, LOW);
    digitalWrite(MOTOR_IN2, HIGH);
  }
  
  // 设置PWM速度
  analogWrite(MOTOR_ENA, pwmValue);
  
  // 发送确认
  Serial.print("ACK:MOTOR_SET:");
  Serial.print(direction);
  Serial.print(":");
  Serial.println(speed);
  
  // 更新状态时间戳
  status.lastUpdateTime = millis();
}

// ==================== 舵机控制函数 ====================

// 控制舵机角度
void controlServo(int angle) {
  // 验证参数
  if (angle < 0) angle = 0;
  if (angle > 180) angle = 180;
  
  // 更新状态
  status.servoAngle = angle;
  
  // 控制舵机
  sg90.write(angle);
  
  // 发送确认
  Serial.print("ACK:SERVO_SET:");
  Serial.println(angle);
  
  // 更新状态时间戳
  status.lastUpdateTime = millis();
}

// ==================== 步进电机控制函数 ====================

// 控制步进电机
void controlStepper(int direction, int steps) {
  // 验证参数
  if (direction < 0 || direction > 1) {
    Serial.println("ERROR:STEPPER_INVALID_DIRECTION");
    return;
  }
  
  if (steps < 0) steps = 0;
  
  // 更新状态
  status.stepperDirection = direction;
  
  // 计算总步数（考虑方向）
  long targetSteps = steps;
  if (direction == 1) {
    targetSteps = -targetSteps; // 反向
  }
  
  // 计算目标位置
  long targetPosition = status.stepperPosition + targetSteps;
  
  // 移动到目标位置
  moveStepperTo(targetPosition, steps);
  
  // 发送确认
  Serial.print("ACK:STEPPER_SET:");
  Serial.print(direction);
  Serial.print(":");
  Serial.println(steps);
  
  // 更新状态时间戳
  status.lastUpdateTime = millis();
}

// 移动到指定位置
void moveStepperTo(long targetPosition, int totalSteps) {
  // 计算移动方向
  int stepDirection = (targetPosition > status.stepperPosition) ? 1 : -1;
  
  // 计算剩余步数
  int remainingSteps = abs(targetPosition - status.stepperPosition);
  
  // 限制最大步数，避免长时间阻塞
  if (remainingSteps > 1000) {
    remainingSteps = 1000;
    Serial.println("WARNING:STEPPER_LIMITED_TO_1000_STEPS");
  }
  
  // 执行步进
  for (int i = 0; i < remainingSteps; i++) {
    // 更新步序索引
    if (stepDirection > 0) {
      stepperStepIndex = (stepperStepIndex + 1) % 8;
    } else {
      stepperStepIndex = (stepperStepIndex + 7) % 8; // 反向
    }
    
    // 设置步进电机引脚
    digitalWrite(STEPPER_IN1, STEP_SEQUENCE[stepperStepIndex][0]);
    digitalWrite(STEPPER_IN2, STEP_SEQUENCE[stepperStepIndex][1]);
    digitalWrite(STEPPER_IN3, STEP_SEQUENCE[stepperStepIndex][2]);
    digitalWrite(STEPPER_IN4, STEP_SEQUENCE[stepperStepIndex][3]);
    
    // 更新位置
    status.stepperPosition += stepDirection;
    
    // 延迟控制速度
    delayMicroseconds(stepperStepDelay);
    
    // 检查是否接收到新指令（避免长时间阻塞）
    if (Serial.available() > 0) {
      Serial.println("WARNING:STEPPER_INTERRUPTED");
      break;
    }
  }
}

// 更新步进电机位置（非阻塞方式）
void updateStepper() {
  // 这里可以添加非阻塞方式的步进电机控制
  // 目前已在controlStepper函数中实现
}

// ==================== 状态管理函数 ====================

// 发送状态更新
void sendStatusUpdate() {
  Serial.print("MOTOR:SPEED:");
  Serial.println(status.motorSpeed);
  
  Serial.print("MOTOR:DIR:");
  Serial.println(status.motorDirection);
  
  Serial.print("SERVO:ANGLE:");
  Serial.println(status.servoAngle);
  
  Serial.print("STEPPER:POS:");
  Serial.println(status.stepperPosition);
  
  Serial.print("STEPPER:DIR:");
  Serial.println(status.stepperDirection);
  
  // 添加更新时间戳
  Serial.print("TIMESTAMP:");
  Serial.println(millis());
}

// 重置所有执行器
void resetAllActuators() {
  Serial.println("正在重置所有执行器...");
  
  // 重置直流电机
  controlDCMotor(0, 0);
  
  // 重置舵机
  controlServo(90);
  
  // 重置步进电机
  stepperStepIndex = 0;
  status.stepperPosition = 0;
  status.stepperDirection = 0;
  
  // 更新状态
  status.lastUpdateTime = millis();
  
  Serial.println("ACK:RESET_COMPLETE");
}

// ==================== 辅助函数 ====================

// 限制数值范围
int constrainValue(int value, int minVal, int maxVal) {
  if (value < minVal) return minVal;
  if (value > maxVal) return maxVal;
  return value;
}

// 计算步进电机延迟（基于速度百分比）
unsigned long calculateStepDelay(int speedPercent) {
  if (speedPercent <= 0) return 0;
  
  // 将速度百分比转换为延迟（微秒）
  // 0% -> 无限延迟（停止），100% -> 最小延迟（最大速度）
  unsigned long maxDelay = 10000;  // 最慢：10000μs = 10ms，100步/秒
  unsigned long minDelay = 500;    // 最快：500μs = 0.5ms，2000步/秒
  
  // 线性映射
  return map(speedPercent, 0, 100, maxDelay, minDelay);
}

// 获取系统信息
void printSystemInfo() {
  Serial.println("=== 系统信息 ===");
  Serial.print("运行时间: ");
  Serial.print(millis() / 1000);
  Serial.println(" 秒");
  
  Serial.print("直流电机状态: ");
  Serial.print(status.motorDirection == 0 ? "正转" : "反转");
  Serial.print("，速度 ");
  Serial.print(status.motorSpeed);
  Serial.println("%");
  
  Serial.print("舵机状态: 角度 ");
  Serial.print(status.servoAngle);
  Serial.println("°");
  
  Serial.print("步进电机状态: 位置 ");
  Serial.print(status.stepperPosition);
  Serial.print(" 步，方向 ");
  Serial.print(status.stepperDirection == 0 ? "正向" : "反向");
  Serial.println();
}