/**
 * 云端同步Three.js扩展 - 云端数据面板
 * 扩展现有Three.js场景，添加实时显示云端传感器数据的面板
 * 支持从Flask API获取数据，并更新AGV运输车和机械臂的孪生体状态
 */

class CloudDataPanel {
    constructor(options = {}) {
        // 配置选项
        this.apiBaseUrl = options.apiBaseUrl || 'http://localhost:5000';
        this.refreshInterval = options.refreshInterval || 2000; // 2秒
        this.containerId = options.containerId || 'cloud-data-panel';
        this.panelVisible = options.panelVisible !== false;
        
        // 状态变量
        this.isInitialized = false;
        this.refreshTimer = null;
        this.latestSensorData = null;
        this.deviceStatus = {};
        
        // DOM元素
        this.container = null;
        this.panelElement = null;
        this.dataTable = null;
        this.statusIndicators = {};
        
        // Three.js引用（可选）
        this.scene = options.scene;
        this.deviceMeshes = options.deviceMeshes || {};
        
        // 初始化
        this.init();
    }
    
    /**
     * 初始化云端数据面板
     */
    init() {
        if (this.isInitialized) {
            return;
        }
        
        console.log('🌥️ 初始化云端数据面板...');
        
        // 创建容器
        this.createPanel();
        
        // 开始数据刷新
        this.startRefreshing();
        
        this.isInitialized = true;
        console.log('✅ 云端数据面板初始化完成');
    }
    
    /**
     * 创建面板DOM元素
     */
    createPanel() {
        // 检查是否已存在容器
        let existingContainer = document.getElementById(this.containerId);
        if (existingContainer) {
            this.container = existingContainer;
        } else {
            // 创建新容器
            this.container = document.createElement('div');
            this.container.id = this.containerId;
            this.container.className = 'cloud-data-panel';
            
            // 样式
            Object.assign(this.container.style, {
                position: 'absolute',
                top: '20px',
                right: '20px',
                width: '350px',
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                color: 'white',
                borderRadius: '10px',
                padding: '15px',
                fontFamily: 'Arial, sans-serif',
                fontSize: '14px',
                zIndex: '1000',
                boxShadow: '0 4px 8px rgba(0, 0, 0, 0.3)',
                display: this.panelVisible ? 'block' : 'none'
            });
            
            // 添加到body
            document.body.appendChild(this.container);
        }
        
        // 面板标题
        const title = document.createElement('h3');
        title.textContent = '🌥️ 云端传感器数据';
        title.style.marginTop = '0';
        title.style.marginBottom = '15px';
        title.style.color = '#4fc3f7';
        this.container.appendChild(title);
        
        // 刷新控制
        const refreshControl = document.createElement('div');
        refreshControl.style.marginBottom = '10px';
        refreshControl.style.display = 'flex';
        refreshControl.style.justifyContent = 'space-between';
        refreshControl.style.alignItems = 'center';
        
        const refreshLabel = document.createElement('span');
        refreshLabel.textContent = '自动刷新:';
        refreshLabel.style.fontSize = '12px';
        
        const toggleButton = document.createElement('button');
        toggleButton.textContent = this.panelVisible ? '暂停' : '继续';
        toggleButton.style.padding = '3px 10px';
        toggleButton.style.backgroundColor = '#2196f3';
        toggleButton.style.color = 'white';
        toggleButton.style.border = 'none';
        toggleButton.style.borderRadius = '3px';
        toggleButton.style.cursor = 'pointer';
        toggleButton.style.fontSize = '12px';
        
        toggleButton.addEventListener('click', () => {
            this.panelVisible = !this.panelVisible;
            this.container.style.display = this.panelVisible ? 'block' : 'none';
            toggleButton.textContent = this.panelVisible ? '暂停' : '继续';
            
            if (this.panelVisible) {
                this.startRefreshing();
            } else {
                this.stopRefreshing();
            }
        });
        
        refreshControl.appendChild(refreshLabel);
        refreshControl.appendChild(toggleButton);
        this.container.appendChild(refreshControl);
        
        // 数据表格容器
        this.dataTable = document.createElement('div');
        this.dataTable.className = 'cloud-data-table';
        this.container.appendChild(this.dataTable);
        
        // 状态指示器容器
        const statusContainer = document.createElement('div');
        statusContainer.className = 'device-status-container';
        statusContainer.style.marginTop = '15px';
        statusContainer.style.paddingTop = '10px';
        statusContainer.style.borderTop = '1px solid #444';
        
        const statusTitle = document.createElement('h4');
        statusTitle.textContent = '设备状态';
        statusTitle.style.marginTop = '0';
        statusTitle.style.marginBottom = '10px';
        statusTitle.style.color = '#81c784';
        statusContainer.appendChild(statusTitle);
        
        this.statusIndicators.container = statusContainer;
        this.container.appendChild(statusContainer);
        
        // 初始加载消息
        this.showLoadingMessage();
    }
    
    /**
     * 显示加载消息
     */
    showLoadingMessage() {
        this.dataTable.innerHTML = `
            <div style="text-align: center; padding: 20px;">
                <div class="loading-spinner" style="
                    border: 3px solid rgba(255, 255, 255, 0.3);
                    border-radius: 50%;
                    border-top: 3px solid #4fc3f7;
                    width: 30px;
                    height: 30px;
                    animation: spin 1s linear infinite;
                    margin: 0 auto 10px;
                "></div>
                <p>正在连接云端数据源...</p>
            </div>
        `;
        
        // 添加CSS动画
        if (!document.querySelector('#cloud-panel-styles')) {
            const style = document.createElement('style');
            style.id = 'cloud-panel-styles';
            style.textContent = `
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            `;
            document.head.appendChild(style);
        }
    }
    
    /**
     * 显示错误消息
     */
    showErrorMessage(error) {
        this.dataTable.innerHTML = `
            <div style="
                background-color: rgba(244, 67, 54, 0.2);
                border-left: 4px solid #f44336;
                padding: 10px;
                margin-bottom: 10px;
                border-radius: 3px;
            ">
                <strong>❌ 连接失败</strong>
                <p style="margin: 5px 0 0; font-size: 12px;">${error}</p>
                <button id="retry-btn" style="
                    margin-top: 8px;
                    padding: 3px 10px;
                    background-color: #f44336;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    cursor: pointer;
                    font-size: 12px;
                ">重试</button>
            </div>
        `;
        
        document.getElementById('retry-btn')?.addEventListener('click', () => {
            this.fetchSensorData();
        });
    }
    
    /**
     * 开始定期刷新数据
     */
    startRefreshing() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }
        
        // 立即获取一次数据
        this.fetchSensorData();
        
        // 设置定时刷新
        this.refreshTimer = setInterval(() => {
            this.fetchSensorData();
        }, this.refreshInterval);
        
        console.log(`🔄 云端数据刷新已启动，间隔: ${this.refreshInterval/1000}秒`);
    }
    
    /**
     * 停止刷新数据
     */
    stopRefreshing() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
            console.log('⏸️ 云端数据刷新已暂停');
        }
    }
    
    /**
     * 从API获取传感器数据
     */
    async fetchSensorData() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/sensor/latest?limit=10`);
            
            if (!response.ok) {
                throw new Error(`API请求失败: ${response.status} ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                this.latestSensorData = data.data;
                this.updatePanelDisplay();
                this.updateDeviceStatus();
                
                // 如果有Three.js场景，更新孪生体状态
                if (this.scene) {
                    this.updateThreeJSState();
                }
                
                console.log('✅ 云端数据更新成功，数量:', data.count);
            } else {
                throw new Error(data.error || 'API返回失败状态');
            }
            
        } catch (error) {
            console.error('❌ 获取云端数据失败:', error);
            this.showErrorMessage(error.message);
        }
    }
    
    /**
     * 更新面板显示
     */
    updatePanelDisplay() {
        if (!this.latestSensorData || this.latestSensorData.length === 0) {
            this.dataTable.innerHTML = '<p>暂无传感器数据</p>';
            return;
        }
        
        // 按设备分组
        const groupedByDevice = {};
        this.latestSensorData.forEach(item => {
            const deviceId = item.device_id;
            if (!groupedByDevice[deviceId]) {
                groupedByDevice[deviceId] = [];
            }
            groupedByDevice[deviceId].push(item);
        });
        
        let html = '';
        
        // 为每个设备生成表格
        Object.entries(groupedByDevice).forEach(([deviceId, sensors]) => {
            html += `
                <div class="device-data-group" style="margin-bottom: 15px;">
                    <div style="
                        background-color: rgba(79, 195, 247, 0.2);
                        padding: 8px 10px;
                        border-radius: 5px;
                        margin-bottom: 8px;
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                    ">
                        <strong>📱 ${deviceId}</strong>
                        <span style="font-size: 11px; color: #bbb;">
                            ${sensors[0].timestamp ? new Date(sensors[0].timestamp).toLocaleTimeString() : ''}
                        </span>
                    </div>
                    <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                        <thead>
                            <tr style="background-color: rgba(255, 255, 255, 0.1);">
                                <th style="text-align: left; padding: 5px;">传感器</th>
                                <th style="text-align: left; padding: 5px;">数值</th>
                                <th style="text-align: left; padding: 5px;">单位</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            sensors.slice(0, 5).forEach(sensor => {
                // 根据数值范围决定颜色
                let valueColor = '#ffffff';
                let value = sensor.value;
                
                // 温度传感器颜色编码
                if (sensor.sensor_type === 'temperature') {
                    if (value > 30) valueColor = '#ff5252';  // 高温红色
                    else if (value < 20) valueColor = '#448aff'; // 低温蓝色
                }
                // 距离传感器颜色编码
                else if (sensor.sensor_type === 'distance') {
                    if (value < 20) valueColor = '#ff5252';  // 近距离红色（危险）
                    else if (value < 50) valueColor = '#ffb74d'; // 中距离橙色
                }
                // 光照传感器颜色编码
                else if (sensor.sensor_type === 'light') {
                    if (value > 80) valueColor = '#ffeb3b';  // 强光黄色
                    else if (value < 20) valueColor = '#757575'; // 弱光灰色
                }
                // 电池/电量颜色编码
                else if (sensor.sensor_name && sensor.sensor_name.includes('电池')) {
                    if (value > 70) valueColor = '#81c784';  // 高电量绿色
                    else if (value > 30) valueColor = '#ffb74d'; // 中电量橙色
                    else valueColor = '#ff5252';  // 低电量红色
                }
                
                html += `
                    <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                        <td style="padding: 5px;">
                            <div style="font-weight: bold;">${sensor.sensor_name || sensor.sensor_id}</div>
                            <div style="font-size: 10px; color: #bbb;">${sensor.sensor_type}</div>
                        </td>
                        <td style="padding: 5px;">
                            <span style="color: ${valueColor}; font-weight: bold;">${value}</span>
                        </td>
                        <td style="padding: 5px; color: #bbb;">${sensor.unit || ''}</td>
                    </tr>
                `;
            });
            
            html += `
                        </tbody>
                    </table>
                </div>
            `;
        });
        
        this.dataTable.innerHTML = html;
    }
    
    /**
     * 更新设备状态
     */
    updateDeviceStatus() {
        if (!this.latestSensorData) return;
        
        // 收集每个设备的最新状态
        this.latestSensorData.forEach(item => {
            const deviceId = item.device_id;
            if (!this.deviceStatus[deviceId]) {
                this.deviceStatus[deviceId] = {
                    lastUpdate: item.timestamp,
                    sensors: {}
                };
            }
            
            this.deviceStatus[deviceId].sensors[item.sensor_id] = {
                value: item.value,
                unit: item.unit,
                type: item.sensor_type,
                name: item.sensor_name
            };
            
            this.deviceStatus[deviceId].lastUpdate = item.timestamp;
        });
        
        // 更新状态指示器
        this.updateStatusIndicators();
    }
    
    /**
     * 更新状态指示器显示
     */
    updateStatusIndicators() {
        const container = this.statusIndicators.container;
        if (!container) return;
        
        // 清除现有状态指示器（除了标题）
        const existingStatus = container.querySelectorAll('.status-indicator');
        existingStatus.forEach(el => el.remove());
        
        // 为每个设备创建状态指示器
        Object.entries(this.deviceStatus).forEach(([deviceId, status]) => {
            const indicator = document.createElement('div');
            indicator.className = 'status-indicator';
            indicator.style.marginBottom = '8px';
            indicator.style.padding = '8px';
            indicator.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
            indicator.style.borderRadius = '5px';
            
            // 计算最后更新时间
            const lastUpdate = new Date(status.lastUpdate);
            const now = new Date();
            const minutesAgo = Math.floor((now - lastUpdate) / 1000 / 60);
            
            // 状态颜色（基于最后更新时间）
            let statusColor = '#81c784';  // 绿色
            let statusText = '在线';
            
            if (minutesAgo > 5) {
                statusColor = '#ff5252';  // 红色
                statusText = '离线';
            } else if (minutesAgo > 1) {
                statusColor = '#ffb74d';  // 橙色
                statusText = '延迟';
            }
            
            // 提取关键传感器数据
            const sensors = Object.values(status.sensors);
            const tempSensor = sensors.find(s => s.type === 'temperature');
            const distanceSensor = sensors.find(s => s.type === 'distance');
            const batterySensor = sensors.find(s => s.name && s.name.includes('电池'));
            
            indicator.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>${deviceId}</strong>
                        <span style="
                            background-color: ${statusColor};
                            color: white;
                            font-size: 10px;
                            padding: 1px 6px;
                            border-radius: 3px;
                            margin-left: 8px;
                        ">${statusText}</span>
                    </div>
                    <span style="font-size: 10px; color: #bbb;">
                        ${minutesAgo}分钟前
                    </span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-top: 5px; font-size: 11px;">
                    ${tempSensor ? `<div>🌡️ ${tempSensor.value}${tempSensor.unit}</div>` : ''}
                    ${distanceSensor ? `<div>📏 ${distanceSensor.value}${distanceSensor.unit}</div>` : ''}
                    ${batterySensor ? `<div>🔋 ${batterySensor.value}${batterySensor.unit}</div>` : ''}
                </div>
            `;
            
            container.appendChild(indicator);
        });
    }
    
    /**
     * 更新Three.js场景中的孪生体状态
     */
    updateThreeJSState() {
        if (!this.scene || !this.deviceMeshes) return;
        
        // 更新AGV运输车状态
        if (this.deviceMeshes.agv) {
            const agvStatus = this.deviceStatus['agv_001'] || this.deviceStatus['raspberry_pi_001'];
            
            if (agvStatus) {
                // 更新电池电量指示
                const battery = agvStatus.sensors['battery'] || agvStatus.sensors['battery_agv'];
                if (battery && this.deviceMeshes.agv.batteryIndicator) {
                    // 这里可以更新Three.js对象的材质或颜色
                    const batteryLevel = battery.value;
                    let batteryColor = 0x00ff00;  // 绿色
                    
                    if (batteryLevel < 30) batteryColor = 0xff0000;  // 红色
                    else if (batteryLevel < 60) batteryColor = 0xff9900; // 橙色
                    
                    this.deviceMeshes.agv.batteryIndicator.material.color.setHex(batteryColor);
                }
                
                // 更新温度指示
                const temperature = agvStatus.sensors['temperature'] || agvStatus.sensors['temp_agv'];
                if (temperature && this.deviceMeshes.agv.temperatureIndicator) {
                    const tempValue = temperature.value;
                    let tempColor = 0xffffff;  // 白色
                    
                    if (tempValue > 30) tempColor = 0xff0000;  // 红色
                    else if (tempValue < 20) tempColor = 0x0000ff; // 蓝色
                    
                    this.deviceMeshes.agv.temperatureIndicator.material.color.setHex(tempColor);
                }
            }
        }
        
        // 更新机械臂状态
        if (this.deviceMeshes.arm) {
            const armStatus = this.deviceStatus['arm_001'];
            
            if (armStatus) {
                // 更新关节角度（如果有对应传感器）
                const jointSensors = Object.values(armStatus.sensors).filter(s => 
                    s.name && s.name.includes('关节')
                );
                
                // 这里可以根据传感器数据调整机械臂的关节角度
                // 实际实现取决于Three.js模型的关节控制系统
            }
        }
        
        console.log('🔄 Three.js孪生体状态已更新');
    }
    
    /**
     * 发送控制指令到API
     */
    async sendControlCommand(device, command, params = {}) {
        try {
            const payload = {
                device: device,
                command: command,
                params: params
            };
            
            const response = await fetch(`${this.apiBaseUrl}/api/control/command`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
            
            if (!response.ok) {
                throw new Error(`控制指令发送失败: ${response.status} ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                console.log(`✅ 控制指令发送成功: ${device} - ${command}`, data);
                return data;
            } else {
                throw new Error(data.error || '控制指令执行失败');
            }
            
        } catch (error) {
            console.error('❌ 发送控制指令失败:', error);
            throw error;
        }
    }
    
    /**
     * 销毁面板，清理资源
     */
    destroy() {
        this.stopRefreshing();
        
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
        
        this.isInitialized = false;
        console.log('🗑️ 云端数据面板已销毁');
    }
}

// 导出类以供使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CloudDataPanel;
} else {
    // 浏览器全局变量
    window.CloudDataPanel = CloudDataPanel;
}