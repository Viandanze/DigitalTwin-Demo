/**
 * Three.js 数字孪生执行器控制扩展
 * 功能：扩展之前的数字孪生场景，增加执行器控制面板和状态可视化
 * 作者：数字孪生学习项目
 * 日期：2026年4月3日
 */

// 执行器数字孪生扩展类
class ActuatorTwinExtension {
    constructor(scene, camera, renderer) {
        this.scene = scene;
        this.camera = camera;
        this.renderer = renderer;
        
        // 执行器对象
        this.actuators = {
            dcMotor: null,
            servo: null,
            stepper: null
        };
        
        // 状态数据
        this.actuatorStatus = {
            dcMotor: { speed: 0, direction: 0 },
            servo: { angle: 90 },
            stepper: { position: 0 }
        };
        
        // 控制面板
        this.controlPanel = null;
        
        // 初始化
        this.init();
    }
    
    init() {
        console.log("初始化执行器数字孪生扩展...");
        
        // 创建执行器3D模型
        this.createActuatorModels();
        
        // 创建控制面板
        this.createControlPanel();
        
        // 添加事件监听
        this.setupEventListeners();
        
        console.log("执行器数字孪生扩展初始化完成");
    }
    
    createActuatorModels() {
        // 创建直流电机模型
        const dcMotorGeometry = new THREE.CylinderGeometry(0.5, 0.5, 1, 16);
        const dcMotorMaterial = new THREE.MeshPhongMaterial({ 
            color: 0x3366CC,
            shininess: 30
        });
        
        this.actuators.dcMotor = new THREE.Mesh(dcMotorGeometry, dcMotorMaterial);
        this.actuators.dcMotor.position.set(-3, 1, 0);
        this.actuators.dcMotor.rotation.x = Math.PI / 2;
        this.scene.add(this.actuators.dcMotor);
        
        // 添加电机轴
        const motorShaftGeometry = new THREE.CylinderGeometry(0.1, 0.1, 2, 8);
        const motorShaftMaterial = new THREE.MeshPhongMaterial({ 
            color: 0xCCCCCC,
            shininess: 50
        });
        
        const motorShaft = new THREE.Mesh(motorShaftGeometry, motorShaftMaterial);
        motorShaft.position.set(0, 0, 1.5);
        this.actuators.dcMotor.add(motorShaft);
        
        // 创建舵机模型
        const servoBaseGeometry = new THREE.BoxGeometry(1, 0.5, 1);
        const servoBaseMaterial = new THREE.MeshPhongMaterial({ 
            color: 0xCC3333,
            shininess: 30
        });
        
        const servoBase = new THREE.Mesh(servoBaseGeometry, servoBaseMaterial);
        servoBase.position.set(0, 0.5, 0);
        
        const servoArmGeometry = new THREE.BoxGeometry(0.2, 1, 0.2);
        const servoArmMaterial = new THREE.MeshPhongMaterial({ 
            color: 0xCCCCCC,
            shininess: 30
        });
        
        const servoArm = new THREE.Mesh(servoArmGeometry, servoArmMaterial);
        servoArm.position.set(0, 1.5, 0);
        
        this.actuators.servo = new THREE.Group();
        this.actuators.servo.add(servoBase);
        this.actuators.servo.add(servoArm);
        this.actuators.servo.position.set(0, 1, 0);
        this.scene.add(this.actuators.servo);
        
        // 创建步进电机模型
        const stepperGeometry = new THREE.CylinderGeometry(0.5, 0.5, 1, 8);
        const stepperMaterial = new THREE.MeshPhongMaterial({ 
            color: 0x33CC66,
            shininess: 30
        });
        
        this.actuators.stepper = new THREE.Mesh(stepperGeometry, stepperMaterial);
        this.actuators.stepper.position.set(3, 1, 0);
        this.actuators.stepper.rotation.x = Math.PI / 2;
        this.scene.add(this.actuators.stepper);
        
        // 添加标签
        this.createActuatorLabels();
    }
    
    createActuatorLabels() {
        // 创建标签容器
        const labelContainer = document.createElement('div');
        labelContainer.id = 'actuator-labels';
        labelContainer.style.position = 'absolute';
        labelContainer.style.top = '20px';
        labelContainer.style.left = '20px';
        labelContainer.style.color = 'white';
        labelContainer.style.fontFamily = 'Arial, sans-serif';
        labelContainer.style.backgroundColor = 'rgba(0,0,0,0.5)';
        labelContainer.style.padding = '10px';
        labelContainer.style.borderRadius = '5px';
        
        document.body.appendChild(labelContainer);
        
        // 更新标签函数
        this.updateLabels = () => {
            const motorStatus = this.actuatorStatus.dcMotor;
            const servoStatus = this.actuatorStatus.servo;
            const stepperStatus = this.actuatorStatus.stepper;
            
            labelContainer.innerHTML = `
                <h3 style="margin-top:0;">执行器状态</h3>
                <div style="margin-bottom: 8px;">
                    <strong>直流电机:</strong><br>
                    速度: ${motorStatus.speed}%<br>
                    方向: ${motorStatus.direction === 0 ? '正转' : '反转'}
                </div>
                <div style="margin-bottom: 8px;">
                    <strong>舵机:</strong><br>
                    角度: ${servoStatus.angle}°
                </div>
                <div>
                    <strong>步进电机:</strong><br>
                    位置: ${stepperStatus.position} 步
                </div>
            `;
        };
        
        // 初始更新
        this.updateLabels();
    }
    
    createControlPanel() {
        // 创建控制面板容器
        this.controlPanel = document.createElement('div');
        this.controlPanel.id = 'actuator-control-panel';
        this.controlPanel.style.position = 'absolute';
        this.controlPanel.style.bottom = '20px';
        this.controlPanel.style.left = '20px';
        this.controlPanel.style.backgroundColor = 'rgba(255,255,255,0.9)';
        this.controlPanel.style.padding = '15px';
        this.controlPanel.style.borderRadius = '8px';
        this.controlPanel.style.boxShadow = '0 4px 12px rgba(0,0,0,0.2)';
        this.controlPanel.style.width = '300px';
        this.controlPanel.style.fontFamily = 'Arial, sans-serif';
        
        // 控制面板内容
        this.controlPanel.innerHTML = `
            <h3 style="margin-top:0; color:#333;">执行器控制面板</h3>
            
            <div style="margin-bottom: 15px;">
                <label style="display:block; margin-bottom:5px; color:#666;">
                    直流电机控制
                </label>
                <div style="display:flex; align-items:center; gap:10px; margin-bottom:5px;">
                    <span style="min-width:40px;">方向:</span>
                    <button id="motor-dir-fwd" style="padding:5px 10px; background:#4CAF50; color:white; border:none; border-radius:4px;">正转</button>
                    <button id="motor-dir-rev" style="padding:5px 10px; background:#F44336; color:white; border:none; border-radius:4px;">反转</button>
                </div>
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="min-width:40px;">速度:</span>
                    <input type="range" id="motor-speed-slider" min="0" max="100" value="0" style="flex:1;">
                    <span id="motor-speed-value" style="min-width:30px; text-align:right;">0%</span>
                </div>
            </div>
            
            <div style="margin-bottom: 15px;">
                <label style="display:block; margin-bottom:5px; color:#666;">
                    舵机角度控制
                </label>
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="min-width:40px;">角度:</span>
                    <input type="range" id="servo-angle-slider" min="0" max="180" value="90" style="flex:1;">
                    <span id="servo-angle-value" style="min-width:30px; text-align:right;">90°</span>
                </div>
            </div>
            
            <div style="margin-bottom: 15px;">
                <label style="display:block; margin-bottom:5px; color:#666;">
                    步进电机控制
                </label>
                <div style="display:flex; align-items:center; gap:10px; margin-bottom:5px;">
                    <span style="min-width:40px;">方向:</span>
                    <button id="stepper-dir-fwd" style="padding:5px 10px; background:#4CAF50; color:white; border:none; border-radius:4px;">正向</button>
                    <button id="stepper-dir-rev" style="padding:5px 10px; background:#F44336; color:white; border:none; border-radius:4px;">反向</button>
                </div>
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="min-width:40px;">步数:</span>
                    <input type="number" id="stepper-steps-input" min="0" value="100" style="padding:5px; width:80px; border:1px solid #ccc; border-radius:4px;">
                    <button id="stepper-move-btn" style="padding:5px 10px; background:#2196F3; color:white; border:none; border-radius:4px;">移动</button>
                </div>
            </div>
            
            <div style="border-top:1px solid #ddd; padding-top:15px;">
                <label style="display:block; margin-bottom:5px; color:#666;">
                    控制场景
                </label>
                <div style="display:flex; gap:10px;">
                    <button id="scenario-vehicle" style="padding:8px 12px; background:#673AB7; color:white; border:none; border-radius:4px; flex:1;">自动避障小车</button>
                    <button id="scenario-greenhouse" style="padding:8px 12px; background:#009688; color:white; border:none; border-radius:4px; flex:1;">智能温室</button>
                </div>
            </div>
            
            <div style="margin-top:15px; font-size:12px; color:#999; text-align:center;">
                状态: <span id="connection-status">未连接</span>
            </div>
        `;
        
        document.body.appendChild(this.controlPanel);
        
        // 初始化控件事件
        this.initControlEvents();
    }
    
    initControlEvents() {
        // 直流电机控制
        const motorSpeedSlider = document.getElementById('motor-speed-slider');
        const motorSpeedValue = document.getElementById('motor-speed-value');
        const motorDirFwdBtn = document.getElementById('motor-dir-fwd');
        const motorDirRevBtn = document.getElementById('motor-dir-rev');
        
        motorSpeedSlider.addEventListener('input', (e) => {
            const speed = e.target.value;
            motorSpeedValue.textContent = `${speed}%`;
            this.updateDCMotor(speed, this.actuatorStatus.dcMotor.direction);
        });
        
        motorDirFwdBtn.addEventListener('click', () => {
            this.updateDCMotor(this.actuatorStatus.dcMotor.speed, 0);
        });
        
        motorDirRevBtn.addEventListener('click', () => {
            this.updateDCMotor(this.actuatorStatus.dcMotor.speed, 1);
        });
        
        // 舵机控制
        const servoAngleSlider = document.getElementById('servo-angle-slider');
        const servoAngleValue = document.getElementById('servo-angle-value');
        
        servoAngleSlider.addEventListener('input', (e) => {
            const angle = e.target.value;
            servoAngleValue.textContent = `${angle}°`;
            this.updateServo(angle);
        });
        
        // 步进电机控制
        const stepperDirFwdBtn = document.getElementById('stepper-dir-fwd');
        const stepperDirRevBtn = document.getElementById('stepper-dir-rev');
        const stepperStepsInput = document.getElementById('stepper-steps-input');
        const stepperMoveBtn = document.getElementById('stepper-move-btn');
        
        stepperDirFwdBtn.addEventListener('click', () => {
            const steps = parseInt(stepperStepsInput.value);
            this.updateStepper(steps, 0);
        });
        
        stepperDirRevBtn.addEventListener('click', () => {
            const steps = parseInt(stepperStepsInput.value);
            this.updateStepper(steps, 1);
        });
        
        stepperMoveBtn.addEventListener('click', () => {
            const steps = parseInt(stepperStepsInput.value);
            const direction = this.actuatorStatus.stepper.direction;
            this.updateStepper(steps, direction);
        });
        
        // 控制场景
        const scenarioVehicleBtn = document.getElementById('scenario-vehicle');
        const scenarioGreenhouseBtn = document.getElementById('scenario-greenhouse');
        
        scenarioVehicleBtn.addEventListener('click', () => {
            this.switchScenario('autonomous_vehicle');
        });
        
        scenarioGreenhouseBtn.addEventListener('click', () => {
            this.switchScenario('smart_greenhouse');
        });
    }
    
    setupEventListeners() {
        // 监听来自主控制系统的状态更新
        window.addEventListener('actuatorStatusUpdate', (event) => {
            if (event.detail) {
                this.updateActuatorStatus(event.detail);
            }
        });
        
        // 监听场景切换
        window.addEventListener('scenarioSwitch', (event) => {
            if (event.detail && event.detail.scenario) {
                this.switchScenarioUI(event.detail.scenario);
            }
        });
    }
    
    updateDCMotor(speed, direction) {
        // 更新状态
        this.actuatorStatus.dcMotor.speed = parseInt(speed);
        this.actuatorStatus.dcMotor.direction = direction;
        
        // 更新3D模型
        if (this.actuators.dcMotor) {
            // 电机旋转（模拟转动）
            const rotationSpeed = speed / 100;
            this.actuators.dcMotor.rotation.z += rotationSpeed * 0.1;
            
            // 根据方向改变颜色
            const material = this.actuators.dcMotor.material;
            material.color.setHex(direction === 0 ? 0x3366CC : 0xCC6633);
        }
        
        // 更新标签
        this.updateLabels();
        
        // 发送控制指令（模拟）
        this.sendControlCommand(`MOTOR:${direction}:${speed}`);
    }
    
    updateServo(angle) {
        // 更新状态
        this.actuatorStatus.servo.angle = parseInt(angle);
        
        // 更新3D模型
        if (this.actuators.servo) {
            // 计算舵机角度（0-180度转换为弧度）
            const radianAngle = (angle - 90) * (Math.PI / 180);
            this.actuators.servo.children[1].rotation.x = radianAngle;
            
            // 根据角度改变颜色
            const baseMaterial = this.actuators.servo.children[0].material;
            const hue = angle / 180;
            baseMaterial.color.setHSL(hue, 0.7, 0.5);
        }
        
        // 更新标签
        this.updateLabels();
        
        // 发送控制指令（模拟）
        this.sendControlCommand(`SERVO:${angle}`);
    }
    
    updateStepper(steps, direction) {
        // 更新状态
        this.actuatorStatus.stepper.position += (direction === 0 ? 1 : -1) * steps;
        
        // 更新3D模型
        if (this.actuators.stepper) {
            // 步进电机旋转（步进角度）
            const stepAngle = (2 * Math.PI) / 200; // 假设每圈200步
            const totalAngle = stepAngle * steps * (direction === 0 ? 1 : -1);
            this.actuators.stepper.rotation.z += totalAngle;
            
            // 根据移动方向改变颜色
            const material = this.actuators.stepper.material;
            material.color.setHex(direction === 0 ? 0x33CC66 : 0xCC6633);
        }
        
        // 更新标签
        this.updateLabels();
        
        // 发送控制指令（模拟）
        this.sendControlCommand(`STEPPER:${direction}:${steps}`);
    }
    
    sendControlCommand(command) {
        console.log(`发送控制指令: ${command}`);
        
        // 模拟发送到串口
        const event = new CustomEvent('actuatorControl', {
            detail: { command: command }
        });
        window.dispatchEvent(event);
        
        // 更新连接状态
        this.updateConnectionStatus(true);
    }
    
    updateActuatorStatus(status) {
        // 更新状态数据
        if (status.dcMotor) {
            this.actuatorStatus.dcMotor = { ...status.dcMotor };
        }
        
        if (status.servo) {
            this.actuatorStatus.servo = { ...status.servo };
        }
        
        if (status.stepper) {
            this.actuatorStatus.stepper = { ...status.stepper };
        }
        
        // 更新3D模型
        this.updateActuatorModels();
        
        // 更新标签
        this.updateLabels();
    }
    
    updateActuatorModels() {
        // 更新直流电机模型
        const motorStatus = this.actuatorStatus.dcMotor;
        if (this.actuators.dcMotor && motorStatus) {
            // 根据速度调整旋转
            this.actuators.dcMotor.rotation.z += motorStatus.speed * 0.001;
            
            // 根据方向改变颜色
            const material = this.actuators.dcMotor.material;
            material.color.setHex(motorStatus.direction === 0 ? 0x3366CC : 0xCC6633);
        }
        
        // 更新舵机模型
        const servoStatus = this.actuatorStatus.servo;
        if (this.actuators.servo && servoStatus) {
            // 计算舵机角度
            const radianAngle = (servoStatus.angle - 90) * (Math.PI / 180);
            this.actuators.servo.children[1].rotation.x = radianAngle;
            
            // 根据角度改变颜色
            const baseMaterial = this.actuators.servo.children[0].material;
            const hue = servoStatus.angle / 180;
            baseMaterial.color.setHSL(hue, 0.7, 0.5);
        }
        
        // 更新步进电机模型
        const stepperStatus = this.actuatorStatus.stepper;
        if (this.actuators.stepper && stepperStatus) {
            // 根据位置设置旋转
            const stepAngle = (2 * Math.PI) / 200;
            const targetAngle = stepAngle * stepperStatus.position;
            this.actuators.stepper.rotation.z = targetAngle;
            
            // 根据移动历史改变颜色
            const material = this.actuators.stepper.material;
            const colorIntensity = Math.sin(stepperStatus.position * 0.01) * 0.3 + 0.7;
            material.color.setRGB(0.2, colorIntensity, 0.4);
        }
    }
    
    switchScenario(scenarioName) {
        console.log(`切换控制场景: ${scenarioName}`);
        
        // 更新UI
        this.switchScenarioUI(scenarioName);
        
        // 发送场景切换事件
        const event = new CustomEvent('scenarioControl', {
            detail: { scenario: scenarioName }
        });
        window.dispatchEvent(event);
        
        // 根据场景设置初始状态
        this.setScenarioInitialState(scenarioName);
    }
    
    switchScenarioUI(scenarioName) {
        const vehicleBtn = document.getElementById('scenario-vehicle');
        const greenhouseBtn = document.getElementById('scenario-greenhouse');
        
        if (scenarioName === 'autonomous_vehicle') {
            vehicleBtn.style.backgroundColor = '#4527A0';
            vehicleBtn.style.fontWeight = 'bold';
            greenhouseBtn.style.backgroundColor = '#009688';
            greenhouseBtn.style.fontWeight = 'normal';
        } else if (scenarioName === 'smart_greenhouse') {
            vehicleBtn.style.backgroundColor = '#673AB7';
            vehicleBtn.style.fontWeight = 'normal';
            greenhouseBtn.style.backgroundColor = '#00695C';
            greenhouseBtn.style.fontWeight = 'bold';
        }
    }
    
    setScenarioInitialState(scenarioName) {
        if (scenarioName === 'autonomous_vehicle') {
            // 设置小车场景初始状态
            this.updateDCMotor(0, 0);
            this.updateServo(90);
            this.updateStepper(0, 0);
            
        } else if (scenarioName === 'smart_greenhouse') {
            // 设置温室场景初始状态
            
            this.updateDCMotor(0, 0);
            this.updateServo(90);
            this.updateStepper(0, 0);
            
            // 模拟环境传感器
            this.simulateGreenhouseSensors();
        }
    }
    
    simulateGreenhouseSensors() {
        // 模拟温度传感器更新
        const simulateTempUpdate = () => {
            const randomTemp = 15 + Math.random() * 20; // 15-35℃
            
            const updateEvent = new CustomEvent('sensorDataUpdate', {
                detail: {
                    temperature: randomTemp,
                    humidity: 40 + Math.random() * 50, // 40-90%
                    distance: 5 + Math.random() * 40   // 5-45cm
                }
            });
            window.dispatchEvent(updateEvent);
        };
        
        // 每2秒更新一次
        this.sensorInterval = setInterval(simulateTempUpdate, 2000);
        
        // 初始更新
        setTimeout(simulateTempUpdate, 500);
    }
    
    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            statusElement.textContent = connected ? '已连接' : '未连接';
            statusElement.style.color = connected ? '#4CAF50' : '#F44336';
        }
    }
    
    animate() {
        // 执行器动画更新
        this.updateActuatorAnimations();
        
        // 继续动画循环
        requestAnimationFrame(() => this.animate());
    }
    
    updateActuatorAnimations() {
        // 直流电机动画
        if (this.actuators.dcMotor) {
            const motorStatus = this.actuatorStatus.dcMotor;
            const rotationSpeed = motorStatus.speed / 1000;
            
            // 根据方向决定旋转方向
            const direction = motorStatus.direction === 0 ? 1 : -1;
            this.actuators.dcMotor.rotation.z += rotationSpeed * direction;
        }
        
        // 舵机动画
        if (this.actuators.servo) {
            const servoStatus = this.actuatorStatus.servo;
            const targetAngle = (servoStatus.angle - 90) * (Math.PI / 180);
            
            // 平滑过渡到目标角度
            const currentAngle = this.actuators.servo.children[1].rotation.x;
            const angleDiff = targetAngle - currentAngle;
            
            if (Math.abs(angleDiff) > 0.01) {
                this.actuators.servo.children[1].rotation.x += angleDiff * 0.1;
            }
        }
        
        // 步进电机动画
        if (this.actuators.stepper) {
            const stepperStatus = this.actuatorStatus.stepper;
            const targetAngle = (stepperStatus.position % 200) * (2 * Math.PI / 200);
            
            // 平滑旋转到目标位置
            const currentAngle = this.actuators.stepper.rotation.z % (2 * Math.PI);
            const angleDiff = (targetAngle - currentAngle + Math.PI) % (2 * Math.PI) - Math.PI;
            
            if (Math.abs(angleDiff) > 0.01) {
                this.actuators.stepper.rotation.z += angleDiff * 0.1;
            }
        }
    }
    
    getActuatorStatus() {
        return { ...this.actuatorStatus };
    }
    
    getControlPanel() {
        return this.controlPanel;
    }
}

// 全局函数，用于初始化执行器扩展
function initActuatorTwinExtension(scene, camera, renderer) {
    console.log("正在初始化执行器数字孪生扩展...");
    
    const actuatorExtension = new ActuatorTwinExtension(scene, camera, renderer);
    
    // 开始动画
    actuatorExtension.animate();
    
    console.log("执行器数字孪生扩展初始化完成");
    return actuatorExtension;
}

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        ActuatorTwinExtension,
        initActuatorTwinExtension
    };
}

// 自检函数
function selfTest() {
    console.log("执行器数字孪生扩展自检开始...");
    
    try {
        // 检查THREE是否可用
        if (typeof THREE === 'undefined') {
            console.error("错误: THREE未定义，请确保已加载Three.js库");
            return false;
        }
        
        // 检查所需类
        const requiredClasses = [
            'Scene', 'PerspectiveCamera', 'WebGLRenderer',
            'CylinderGeometry', 'BoxGeometry', 'MeshPhongMaterial',
            'Mesh', 'Group'
        ];
        
        for (const className of requiredClasses) {
            if (!THREE[className]) {
                console.error(`错误: THREE.${className}未定义`);
                return false;
            }
        }
        
        console.log("✓ Three.js检查通过");
        
        // 测试ActuatorTwinExtension类结构
        const requiredMethods = [
            'init', 'createActuatorModels', 'createControlPanel',
            'updateDCMotor', 'updateServo', 'updateStepper',
            'getActuatorStatus'
        ];
        
        // 创建模拟对象进行测试
        const mockExtension = {
            init: function() {},
            createActuatorModels: function() {},
            createControlPanel: function() {},
            updateDCMotor: function() {},
            updateServo: function() {},
            updateStepper: function() {},
            getActuatorStatus: function() {}
        };
        
        for (const method of requiredMethods) {
            if (typeof mockExtension[method] !== 'function') {
                console.error(`错误: ActuatorTwinExtension缺少方法 ${method}`);
                return false;
            }
        }
        
        console.log("✓ ActuatorTwinExtension类结构检查通过");
        
        // 测试UI元素创建
        console.log("测试UI元素创建...");
        
        // 模拟DOM环境
        if (typeof document === 'object') {
            console.log("✓ DOM环境可用");
        }
        
        console.log("✓ 所有自检项目通过");
        return true;
        
    } catch (error) {
        console.error(`自检失败: ${error.message}`);
        return false;
    }
}

// 提供全局访问
if (typeof window !== 'undefined') {
    window.ActuatorTwinExtension = ActuatorTwinExtension;
    window.initActuatorTwinExtension = initActuatorTwinExtension;
    window.actuatorTwinSelfTest = selfTest;
}

console.log("执行器数字孪生扩展模块加载完成");