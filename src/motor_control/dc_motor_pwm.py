"""
树莓派5通过L298N驱动直流电机PWM调速控制
支持正反转、速度控制（0-100%）
接线说明：
  - GPIO17 -> L298N IN1 (方向控制1)
  - GPIO18 -> L298N IN2 (方向控制2)
  - GPIO19 -> L298N ENA (PWM调速)
  - GND -> L298N GND (共地)
  - 外部12V电源 -> L298N +12V
  - 电机正负极 -> L298N OUT1/OUT2
"""

import RPi.GPIO as GPIO
import time
import sys

class DCMotorController:
    """直流电机控制器类"""
    
    def __init__(self, in1_pin=17, in2_pin=18, ena_pin=19, pwm_freq=1000):
        """
        初始化电机控制器
        
        参数:
            in1_pin: 方向控制引脚1 (BCM编号)
            in2_pin: 方向控制引脚2 (BCM编号)
            ena_pin: PWM使能引脚 (BCM编号)
            pwm_freq: PWM频率 (Hz)，默认1kHz
        """
        self.in1_pin = in1_pin
        self.in2_pin = in2_pin
        self.ena_pin = ena_pin
        self.pwm_freq = pwm_freq
        self.pwm = None
        self.current_speed = 0  # 0-100
        self.current_direction = "stopped"
        
        # 设置GPIO模式
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # 设置引脚模式
        GPIO.setup(self.in1_pin, GPIO.OUT)
        GPIO.setup(self.in2_pin, GPIO.OUT)
        GPIO.setup(self.ena_pin, GPIO.OUT)
        
        # 初始化输出
        GPIO.output(self.in1_pin, GPIO.LOW)
        GPIO.output(self.in2_pin, GPIO.LOW)
        
        # 创建PWM实例
        self.pwm = GPIO.PWM(self.ena_pin, self.pwm_freq)
        self.pwm.start(0)  # 初始占空比0%
        
        print(f"直流电机控制器初始化完成，PWM频率: {self.pwm_freq}Hz")
        print(f"引脚: IN1={self.in1_pin}, IN2={self.in2_pin}, ENA={self.ena_pin}")
    
    def forward(self, speed_percent=50):
        """
        正转
        
        参数:
            speed_percent: 速度百分比 (0-100)
        """
        if speed_percent < 0 or speed_percent > 100:
            raise ValueError("速度百分比必须在0-100之间")
        
        # 设置方向
        GPIO.output(self.in1_pin, GPIO.HIGH)
        GPIO.output(self.in2_pin, GPIO.LOW)
        
        # 设置速度
        self.pwm.ChangeDutyCycle(speed_percent)
        
        self.current_speed = speed_percent
        self.current_direction = "forward"
        
        print(f"正转，速度: {speed_percent}%")
    
    def backward(self, speed_percent=50):
        """
        反转
        
        参数:
            speed_percent: 速度百分比 (0-100)
        """
        if speed_percent < 0 or speed_percent > 100:
            raise ValueError("速度百分比必须在0-100之间")
        
        # 设置方向
        GPIO.output(self.in1_pin, GPIO.LOW)
        GPIO.output(self.in2_pin, GPIO.HIGH)
        
        # 设置速度
        self.pwm.ChangeDutyCycle(speed_percent)
        
        self.current_speed = speed_percent
        self.current_direction = "backward"
        
        print(f"反转，速度: {speed_percent}%")
    
    def stop(self):
        """停止电机"""
        GPIO.output(self.in1_pin, GPIO.LOW)
        GPIO.output(self.in2_pin, GPIO.LOW)
        self.pwm.ChangeDutyCycle(0)
        
        self.current_speed = 0
        self.current_direction = "stopped"
        
        print("电机已停止")
    
    def set_speed(self, speed_percent):
        """
        设置速度（保持当前方向）
        
        参数:
            speed_percent: 速度百分比 (0-100)
        """
        if speed_percent < 0 or speed_percent > 100:
            raise ValueError("速度百分比必须在0-100之间")
        
        # 如果当前已停止，需要先设置方向
        if self.current_direction == "stopped":
            print("警告: 当前方向为停止，请先调用forward()或backward()")
            return
        
        self.pwm.ChangeDutyCycle(speed_percent)
        self.current_speed = speed_percent
        
        print(f"速度设置为: {speed_percent}%")
    
    def emergency_stop(self):
        """紧急停止（立即停止所有输出）"""
        GPIO.output(self.in1_pin, GPIO.LOW)
        GPIO.output(self.in2_pin, GPIO.LOW)
        self.pwm.ChangeDutyCycle(0)
        
        print("紧急停止！")
    
    def get_status(self):
        """获取当前状态"""
        return {
            "direction": self.current_direction,
            "speed": self.current_speed,
            "pwm_freq": self.pwm_freq,
            "pins": {
                "in1": self.in1_pin,
                "in2": self.in2_pin,
                "ena": self.ena_pin
            }
        }
    
    def cleanup(self):
        """清理GPIO资源"""
        self.stop()
        if self.pwm:
            self.pwm.stop()
        GPIO.cleanup()
        print("GPIO资源已清理")


def demo():
    """演示函数"""
    print("=== 直流电机PWM调速演示 ===\n")
    
    try:
        # 创建电机控制器实例
        motor = DCMotorController()
        
        # 正转演示
        print("1. 正转演示")
        motor.forward(30)
        time.sleep(2)
        
        motor.set_speed(60)
        time.sleep(2)
        
        motor.set_speed(90)
        time.sleep(2)
        
        # 停止
        motor.stop()
        time.sleep(1)
        
        # 反转演示
        print("\n2. 反转演示")
        motor.backward(40)
        time.sleep(2)
        
        motor.set_speed(70)
        time.sleep(2)
        
        # 渐停
        print("\n3. 渐停演示")
        for speed in range(70, 0, -10):
            motor.set_speed(speed)
            time.sleep(0.5)
        
        motor.stop()
        
        # 显示状态
        print("\n4. 当前状态:")
        status = motor.get_status()
        for key, value in status.items():
            print(f"  {key}: {value}")
        
        print("\n演示完成！")
        
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        if 'motor' in locals():
            motor.cleanup()


def safety_check():
    """安全检查"""
    print("安全注意事项:")
    print("1. 确保所有GND共地")
    print("2. 树莓派GPIO为3.3V，L298N输入兼容3.3V")
    print("3. 外部12V电源正负极正确连接")
    print("4. 电机负载电流不超过L298N额定值（2A持续）")
    print("5. 首次测试时建议先低速运行")
    print("6. 紧急情况下可使用emergency_stop()立即停止")


if __name__ == "__main__":
    safety_check()
    print("\n开始演示吗？(y/n)")
    choice = input().strip().lower()
    
    if choice == 'y':
        demo()
    else:
        print("退出程序")