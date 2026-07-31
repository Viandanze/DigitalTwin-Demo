"""
28BYJ-48步进电机控制程序（四相八拍时序）
通过ULN2003驱动模块控制

接线说明（树莓派GPIO -> ULN2003 IN引脚）：
  - GPIO17 -> IN1 (对应电机橙线)
  - GPIO18 -> IN2 (对应电机黄线)
  - GPIO19 -> IN3 (对应电机粉线)
  - GPIO20 -> IN4 (对应电机蓝线)
  - 电机红线 -> 5V/12V电源正极
  - 电源负极 -> ULN2003 GND
  - ULN2003 GND -> 树莓派GND（共地）

电机参数：
  - 减速比：1:64
  - 步距角：5.625°（全步）
  - 步数/圈：4096（四相八拍模式）
  - 工作电压：5V或12V
"""

import RPi.GPIO as GPIO
import time
import sys

class StepperMotor28BYJ48:
    """28BYJ-48步进电机控制器"""
    
    # 四相八拍时序表（1表示激活，0表示关闭）
    # 顺序: IN1, IN2, IN3, IN4
    STEP_SEQUENCE = [
        [1, 0, 0, 0],  # 步1
        [1, 1, 0, 0],  # 步2
        [0, 1, 0, 0],  # 步3
        [0, 1, 1, 0],  # 步4
        [0, 0, 1, 0],  # 步5
        [0, 0, 1, 1],  # 步6
        [0, 0, 0, 1],  # 步7
        [1, 0, 0, 1],  # 步8
    ]
    
    # 电机技术参数
    STEPS_PER_REVOLUTION = 4096  # 四相八拍模式下的步数/圈
    STEP_ANGLE = 5.625 / 64      # 输出轴步距角（度）
    
    def __init__(self, in_pins=[17, 18, 19, 20], step_delay=0.001):
        """
        初始化步进电机控制器
        
        参数:
            in_pins: ULN2003输入引脚列表 [IN1, IN2, IN3, IN4]
            step_delay: 每一步之间的延迟（秒），控制速度
        """
        self.in_pins = in_pins
        self.step_delay = step_delay
        self.current_step = 0
        self.total_steps = 0
        self.direction = 1  # 1: 正转, -1: 反转
        self.is_running = False
        
        # 验证引脚数量
        if len(self.in_pins) != 4:
            raise ValueError("必须提供4个控制引脚")
        
        # 设置GPIO模式
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # 设置引脚为输出模式
        for pin in self.in_pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
        
        print("28BYJ-48步进电机控制器初始化完成")
        print(f"控制引脚: IN1={self.in_pins[0]}, IN2={self.in_pins[1]}, "
              f"IN3={self.in_pins[2]}, IN4={self.in_pins[3]}")
        print(f"步进延迟: {self.step_delay*1000}ms")
        print(f"步数/圈: {self.STEPS_PER_REVOLUTION}")
        print(f"步距角: {self.STEP_ANGLE:.4f} 度")
    
    def _set_step(self, step_pattern):
        """设置当前步的引脚状态"""
        for i in range(4):
            GPIO.output(self.in_pins[i], step_pattern[i])
    
    def step(self, num_steps=1, direction=1):
        """
        移动指定步数
        
        参数:
            num_steps: 移动步数（正数）
            direction: 方向 (1: 正转, -1: 反转)
        
        返回:
            实际移动的步数
        """
        if num_steps <= 0:
            return 0
        
        self.is_running = True
        self.direction = direction
        
        steps_moved = 0
        
        try:
            for _ in range(num_steps):
                # 根据方向计算当前步索引
                if direction == 1:
                    self.current_step = (self.current_step + 1) % 8
                else:
                    self.current_step = (self.current_step - 1) % 8
                
                # 设置引脚状态
                self._set_step(self.STEP_SEQUENCE[self.current_step])
                
                # 等待
                time.sleep(self.step_delay)
                
                steps_moved += 1
                self.total_steps += direction
            
            # 移动完成后关闭所有引脚
            self._set_step([0, 0, 0, 0])
            
        except KeyboardInterrupt:
            print("步进移动被中断")
        finally:
            self.is_running = False
        
        return steps_moved
    
    def step_forward(self, num_steps=1):
        """正转指定步数"""
        return self.step(num_steps, direction=1)
    
    def step_backward(self, num_steps=1):
        """反转指定步数"""
        return self.step(num_steps, direction=-1)
    
    def rotate(self, angle_degrees, direction=1):
        """
        旋转指定角度
        
        参数:
            angle_degrees: 角度（度）
            direction: 方向 (1: 正转, -1: 反转)
        
        返回:
            移动的步数
        """
        # 计算所需步数
        steps_needed = int(abs(angle_degrees) / self.STEP_ANGLE)
        
        if steps_needed == 0:
            return 0
        
        print(f"旋转 {angle_degrees} 度，需要 {steps_needed} 步")
        return self.step(steps_needed, direction)
    
    def rotate_degrees(self, angle_degrees):
        """旋转指定角度（正转）"""
        if angle_degrees >= 0:
            return self.rotate(angle_degrees, 1)
        else:
            return self.rotate(abs(angle_degrees), -1)
    
    def move_to_position(self, target_steps):
        """
        移动到绝对位置（以步数计）
        
        参数:
            target_steps: 目标步数位置
        """
        delta = target_steps - self.total_steps
        
        if delta == 0:
            return 0
        
        direction = 1 if delta > 0 else -1
        return self.step(abs(delta), direction)
    
    def set_speed(self, step_delay):
        """
        设置步进速度
        
        参数:
            step_delay: 每一步之间的延迟（秒）
        """
        if step_delay <= 0:
            raise ValueError("步进延迟必须大于0")
        
        self.step_delay = step_delay
        print(f"速度设置为 {step_delay*1000}ms/步")
    
    def emergency_stop(self):
        """紧急停止"""
        self.is_running = False
        self._set_step([0, 0, 0, 0])
        print("紧急停止 - 所有输出已关闭")
    
    def get_status(self):
        """获取当前状态"""
        # 计算当前位置（角度）
        current_angle = (self.total_steps % self.STEPS_PER_REVOLUTION) * self.STEP_ANGLE
        
        return {
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "current_angle": current_angle,
            "direction": self.direction,
            "is_running": self.is_running,
            "step_delay": self.step_delay,
            "pins": self.in_pins
        }
    
    def cleanup(self):
        """清理GPIO资源"""
        self.emergency_stop()
        GPIO.cleanup()
        print("GPIO资源已清理")


def demo():
    """演示函数"""
    print("\n=== 28BYJ-48步进电机演示 ===\n")
    
    try:
        # 创建电机控制器实例
        motor = StepperMotor28BYJ48(step_delay=0.001)
        
        print("1. 正转演示 (90度)")
        motor.rotate(90, 1)
        time.sleep(1)
        
        print("\n2. 反转演示 (45度)")
        motor.rotate(45, -1)
        time.sleep(1)
        
        print("\n3. 精确位置控制演示")
        print("   a) 移动到0度位置")
        motor.move_to_position(0)
        time.sleep(1)
        
        print("   b) 移动到180度位置")
        motor.rotate(180, 1)
        time.sleep(1)
        
        print("   c) 回到初始位置")
        motor.move_to_position(0)
        time.sleep(1)
        
        print("\n4. 变速演示")
        print("   a) 慢速 (5ms/步)")
        motor.set_speed(0.005)
        motor.step_forward(200)
        
        print("   b) 快速 (1ms/步)")
        motor.set_speed(0.001)
        motor.step_backward(200)
        
        print("   c) 中速 (2ms/步)")
        motor.set_speed(0.002)
        motor.step_forward(100)
        
        # 回到初始位置
        motor.move_to_position(0)
        
        print("\n5. 当前状态:")
        status = motor.get_status()
        for key, value in status.items():
            if key != 'pins':
                print(f"   {key}: {value}")
        
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
    print("2. ULN2003最大负载电流500mA/路，勿超限")
    print("3. 电机工作电压选择正确（5V或12V）")
    print("4. 步进电机堵转会产生高热，及时停止")
    print("5. 首次测试时建议先低速运行")
    print("6. 紧急情况下使用emergency_stop()")


def manual_test():
    """手动测试模式"""
    motor = StepperMotor28BYJ48()
    
    print("手动测试模式 (输入命令)")
    print("  f 步数 - 正转")
    print("  b 步数 - 反转")
    print("  a 角度 - 旋转角度")
    print("  s 延迟 - 设置速度 (ms)")
    print("  i - 显示信息")
    print("  e - 紧急停止")
    print("  q - 退出")
    
    try:
        while True:
            cmd = input("> ").strip().lower().split()
            
            if not cmd:
                continue
            
            if cmd[0] == 'q':
                break
            elif cmd[0] == 'f' and len(cmd) > 1:
                steps = int(cmd[1])
                motor.step_forward(steps)
            elif cmd[0] == 'b' and len(cmd) > 1:
                steps = int(cmd[1])
                motor.step_backward(steps)
            elif cmd[0] == 'a' and len(cmd) > 1:
                angle = float(cmd[1])
                motor.rotate_degrees(angle)
            elif cmd[0] == 's' and len(cmd) > 1:
                delay_ms = float(cmd[1])
                motor.set_speed(delay_ms / 1000.0)
            elif cmd[0] == 'i':
                status = motor.get_status()
                for key, value in status.items():
                    print(f"{key}: {value}")
            elif cmd[0] == 'e':
                motor.emergency_stop()
            else:
                print("未知命令")
    
    finally:
        motor.cleanup()


if __name__ == "__main__":
    safety_check()
    
    print("\n选择模式:")
    print("  1 - 自动演示")
    print("  2 - 手动测试")
    print("  3 - 退出")
    
    try:
        choice = input("请输入选择 (1-3): ").strip()
        
        if choice == '1':
            demo()
        elif choice == '2':
            manual_test()
        else:
            print("退出程序")
    
    except KeyboardInterrupt:
        print("\n程序被用户中断")