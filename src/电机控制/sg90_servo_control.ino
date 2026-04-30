/*
 * SG90舵机角度定位控制
 * 
 * 接线说明：
 *   - SG90信号线（黄） -> Arduino D9
 *   - SG90 VCC（红）   -> Arduino 5V
 *   - SG90 GND（棕/黑）-> Arduino GND
 * 
 * 注意事项：
 *   1. SG90工作电压4.8-6V，Arduino 5V可驱动但扭矩稍低
 *   2. 如需更大扭矩或驱动多个舵机，建议使用外部电源
 *   3. 确保所有GND共地
 *   4. 舵机堵转会消耗大电流，可能导致Arduino重启
 */

#include <Servo.h>

// 定义舵机引脚
const int SERVO_PIN = 9;

// 创建舵机对象
Servo sg90;

// 舵机参数
const int MIN_ANGLE = 0;      // 最小角度
const int MAX_ANGLE = 180;    // 最大角度
const int INIT_ANGLE = 90;    // 初始角度（中立位）

// 当前角度
int currentAngle = INIT_ANGLE;

void setup() {
  // 初始化串口通信
  Serial.begin(9600);
  while (!Serial) {
    ; // 等待串口连接
  }
  
  Serial.println("=== SG90舵机控制程序 ===");
  Serial.println("命令格式:");
  Serial.println("  s角度 - 设置角度 (0-180)");
  Serial.println("  a+/-角度 - 相对角度调整");
  Serial.println("  c - 校准 (0->90->180->90->0)");
  Serial.println("  h - 回到初始位置 (90度)");
  Serial.println("  i - 显示信息");
  Serial.println("  q - 退出演示模式");
  Serial.println();
  
  // 舵机初始化
  sg90.attach(SERVO_PIN);
  sg90.write(INIT_ANGLE);
  
  Serial.print("舵机已初始化，初始角度: ");
  Serial.print(INIT_ANGLE);
  Serial.println(" 度");
  
  delay(1000); // 等待舵机稳定
}

void loop() {
  // 主循环保持舵机当前位置
  // 通过串口接收命令
  
  if (Serial.available() > 0) {
    processCommand();
  }
}

void processCommand() {
  char command = Serial.read();
  
  switch (command) {
    case 's': // 设置绝对角度
      setAngle();
      break;
      
    case 'a': // 相对角度调整
      adjustAngle();
      break;
      
    case 'c': // 校准演示
      calibrationDemo();
      break;
      
    case 'h': // 回到初始位置
      homePosition();
      break;
      
    case 'i': // 显示信息
      showInfo();
      break;
      
    case 'q': // 退出演示模式
      Serial.println("退出演示模式");
      break;
      
    default:
      Serial.println("未知命令，输入 'i' 查看帮助");
      break;
  }
}

void setAngle() {
  // 读取角度值
  int angle = Serial.parseInt();
  
  // 角度范围检查
  if (angle < MIN_ANGLE || angle > MAX_ANGLE) {
    Serial.print("角度超出范围 (");
    Serial.print(MIN_ANGLE);
    Serial.print("-");
    Serial.print(MAX_ANGLE);
    Serial.println(")");
    return;
  }
  
  // 设置舵机角度
  sg90.write(angle);
  currentAngle = angle;
  
  Serial.print("角度设置为: ");
  Serial.print(angle);
  Serial.println(" 度");
  
  // 等待舵机到位
  delay(500);
}

void adjustAngle() {
  // 读取相对角度值（带符号）
  char sign = Serial.read();
  int delta = Serial.parseInt();
  
  // 根据符号确定方向
  if (sign == '-') {
    delta = -delta;
  }
  
  // 计算新角度
  int newAngle = currentAngle + delta;
  
  // 角度范围检查
  if (newAngle < MIN_ANGLE || newAngle > MAX_ANGLE) {
    Serial.print("角度超出范围 (");
    Serial.print(MIN_ANGLE);
    Serial.print("-");
    Serial.print(MAX_ANGLE);
    Serial.println(")");
    return;
  }
  
  // 设置舵机角度
  sg90.write(newAngle);
  currentAngle = newAngle;
  
  Serial.print("角度调整 ");
  Serial.print(delta);
  Serial.print(" 度，当前角度: ");
  Serial.print(currentAngle);
  Serial.println(" 度");
  
  // 等待舵机到位
  delay(500);
}

void calibrationDemo() {
  Serial.println("开始校准演示...");
  
  // 0度
  Serial.println("移动到 0 度");
  sg90.write(0);
  delay(1000);
  
  // 90度（中立位）
  Serial.println("移动到 90 度");
  sg90.write(90);
  delay(1000);
  
  // 180度
  Serial.println("移动到 180 度");
  sg90.write(180);
  delay(1000);
  
  // 回到90度
  Serial.println("回到 90 度");
  sg90.write(90);
  currentAngle = 90;
  delay(1000);
  
  // 回到0度
  Serial.println("回到 0 度");
  sg90.write(0);
  currentAngle = 0;
  delay(1000);
  
  // 最终回到中立位
  sg90.write(INIT_ANGLE);
  currentAngle = INIT_ANGLE;
  
  Serial.println("校准演示完成，回到初始位置");
}

void homePosition() {
  Serial.print("回到初始位置: ");
  Serial.print(INIT_ANGLE);
  Serial.println(" 度");
  
  sg90.write(INIT_ANGLE);
  currentAngle = INIT_ANGLE;
  
  delay(500);
}

void showInfo() {
  Serial.println("=== 舵机信息 ===");
  Serial.print("当前角度: ");
  Serial.println(currentAngle);
  
  Serial.print("工作范围: ");
  Serial.print(MIN_ANGLE);
  Serial.print(" - ");
  Serial.println(MAX_ANGLE);
  
  Serial.print("控制引脚: D");
  Serial.println(SERVO_PIN);
  
  Serial.println();
  Serial.println("SG90技术参数:");
  Serial.println("  • 工作电压: 4.8-6V");
  Serial.println("  • 扭矩: 1.8kg·cm @4.8V");
  Serial.println("  • 响应速度: 0.12s/60°");
  Serial.println("  • PWM信号: 50Hz, 0.5-2.5ms脉冲");
  Serial.println("  • 重量: 约9g");
  
  Serial.println();
}

// 安全函数
void emergencyStop() {
  // 立即停止舵机（保持当前位置）
  // 注意：SG90舵机没有紧急停止功能，只能保持当前位置
  Serial.println("紧急停止 - 舵机保持当前位置");
}

// 角度平滑移动函数
void smoothMove(int targetAngle, int durationMs = 1000) {
  // 平滑移动舵机到目标角度
  // 参数：
  //   targetAngle: 目标角度
  //   durationMs: 移动持续时间（毫秒）
  
  int startAngle = currentAngle;
  int steps = 20; // 移动步数
  int stepDelay = durationMs / steps;
  
  for (int i = 0; i <= steps; i++) {
    float t = (float)i / steps;
    int angle = startAngle + (targetAngle - startAngle) * t;
    
    sg90.write(angle);
    delay(stepDelay);
  }
  
  currentAngle = targetAngle;
}

// 示例演示函数
void demonstration() {
  Serial.println("开始自动演示...");
  
  // 平滑移动到0度
  smoothMove(0, 1500);
  Serial.println("到达0度");
  delay(500);
  
  // 平滑移动到90度
  smoothMove(90, 1500);
  Serial.println("到达90度");
  delay(500);
  
  // 平滑移动到180度
  smoothMove(180, 1500);
  Serial.println("到达180度");
  delay(500);
  
  // 回到初始位置
  smoothMove(INIT_ANGLE, 1500);
  Serial.println("回到初始位置");
  
  Serial.println("演示完成");
}