/**
 * 系统联调Three.js调试面板扩展
 * 扩展现有Three.js数字孪生场景，添加实时调试面板
 * 显示系统状态、故障码、诊断建议、性能指标和日志信息
 */

class DebugPanel {
    constructor(options = {}) {
        // 配置选项
        this.apiBaseUrl = options.apiBaseUrl || 'http://localhost:5000';
        this.refreshInterval = options.refreshInterval || 1000; // 1秒
        this.containerId = options.containerId || 'debug-panel';
        this.panelVisible = options.panelVisible !== false;
        this.maxLogEntries = options.maxLogEntries || 50;
        
        // 状态变量
        this.isInitialized = false;
        this.refreshTimer = null;
        this.systemStatus = 'normal'; // normal, warning, error
        this.faultCodes = [];
        this.performanceMetrics = {};
        this.logEntries = [];
        
        // DOM元素
        this.container = null;
        this.panelElement = null;
        this.statusIndicator = null;
        this.faultList = null;
        this.metricsTable = null;
        this.logDisplay = null;
        this.controlPanel = null;
        
        // Three.js引用（可选）
        this.scene = options.scene;
        this.renderer = options.renderer;
        this.deviceMeshes = options.deviceMeshes || {};
        
        // 故障注入状态
        this.activeFaults = new Map();
        
        // 初始化
        this.init();
    }
    
    /**
     * 初始化调试面板
     */
    init() {
        if (this.isInitialized) {
            return;
        }
        
        console.log('🐛 初始化系统调试面板...');
        
        // 创建面板
        this.createPanel();
        
        // 开始数据刷新
        this.startRefreshing();
        
        // 初始化性能监控
        this.initPerformanceMonitoring();
        
        this.isInitialized = true;
        console.log('✅ 调试面板初始化完成');
    }
    
    /**
     * 创建调试面板DOM结构
     */
    createPanel() {
        // 创建主容器
        this.container = document.createElement('div');
        this.container.id = this.containerId;
        this.container.style.cssText = `
            position: absolute;
            top: 20px;
            right: 20px;
            width: 400px;
            max-height: 80vh;
            background: rgba(0, 0, 0, 0.85);
            color: #fff;
            border-radius: 10px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 12px;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
            z-index: 1000;
            display: ${this.panelVisible ? 'block' : 'none'};
        `;
        
        // 创建标题栏
        const titleBar = document.createElement('div');
        titleBar.style.cssText = `
            background: linear-gradient(90deg, #2c3e50, #34495e);
            color: #ecf0f1;
            padding: 12px 16px;
            font-weight: bold;
            font-size: 14px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #7f8c8d;
        `;
        
        const titleText = document.createElement('span');
        titleText.textContent = '🐛 数字孪生系统调试面板';
        
        const closeBtn = document.createElement('button');
        closeBtn.textContent = '×';
        closeBtn.style.cssText = `
            background: #e74c3c;
            color: white;
            border: none;
            border-radius: 50%;
            width: 24px;
            height: 24px;
            cursor: pointer;
            font-size: 16px;
            line-height: 1;
            padding: 0;
        `;
        closeBtn.onclick = () => this.toggleVisibility();
        
        titleBar.appendChild(titleText);
        titleBar.appendChild(closeBtn);
        
        // 创建内容区域
        const contentArea = document.createElement('div');
        contentArea.style.cssText = `
            padding: 16px;
            overflow-y: auto;
            max-height: calc(80vh - 100px);
        `;
        
        // 1. 系统状态指示器
        const statusSection = this.createStatusSection();
        contentArea.appendChild(statusSection);
        
        // 2. 故障码列表
        const faultSection = this.createFaultSection();
        contentArea.appendChild(faultSection);
        
        // 3. 性能指标表格
        const metricsSection = this.createMetricsSection();
        contentArea.appendChild(metricsSection);
        
        // 4. 实时日志显示
        const logSection = this.createLogSection();
        contentArea.appendChild(logSection);
        
        // 5. 故障注入控制面板
        const controlSection = this.createControlSection();
        contentArea.appendChild(controlSection);
        
        // 组装面板
        this.container.appendChild(titleBar);
        this.container.appendChild(contentArea);
        
        // 添加到页面
        document.body.appendChild(this.container);
        
        // 保存引用
        this.panelElement = this.container;
    }
    
    /**
     * 创建系统状态指示器
     */
    createStatusSection() {
        const section = document.createElement('div');
        section.style.marginBottom = '20px';
        
        const title = document.createElement('div');
        title.textContent = '📊 系统状态';
        title.style.cssText = `
            font-weight: bold;
            margin-bottom: 8px;
            color: #3498db;
            font-size: 13px;
        `;
        
        const statusContainer = document.createElement('div');
        statusContainer.style.cssText = `
            display: flex;
            align-items: center;
            background: rgba(52, 73, 94, 0.5);
            border-radius: 6px;
            padding: 10px;
        `;
        
        this.statusIndicator = document.createElement('div');
        this.statusIndicator.style.cssText = `
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 10px;
            background: #2ecc71;
            box-shadow: 0 0 10px #2ecc71;
            transition: all 0.3s;
        `;
        
        const statusText = document.createElement('div');
        statusText.id = 'system-status-text';
        statusText.textContent = '系统运行正常';
        statusText.style.flex = '1';
        
        const uptimeDisplay = document.createElement('div');
        uptimeDisplay.id = 'system-uptime';
        uptimeDisplay.textContent = '运行时间: 00:00:00';
        uptimeDisplay.style.fontSize = '11px';
        uptimeDisplay.style.color = '#bdc3c7';
        
        statusContainer.appendChild(this.statusIndicator);
        statusContainer.appendChild(statusText);
        statusContainer.appendChild(uptimeDisplay);
        
        section.appendChild(title);
        section.appendChild(statusContainer);
        
        return section;
    }
    
    /**
     * 创建故障码列表
     */
    createFaultSection() {
        const section = document.createElement('div');
        section.style.marginBottom = '20px';
        
        const title = document.createElement('div');
        title.textContent = '⚠️ 活动故障';
        title.style.cssText = `
            font-weight: bold;
            margin-bottom: 8px;
            color: #e74c3c;
            font-size: 13px;
        `;
        
        this.faultList = document.createElement('div');
        this.faultList.id = 'fault-list';
        this.faultList.style.cssText = `
            background: rgba(231, 76, 60, 0.1);
            border: 1px solid rgba(231, 76, 60, 0.3);
            border-radius: 6px;
            padding: 10px;
            min-height: 60px;
            max-height: 120px;
            overflow-y: auto;
            font-size: 11px;
        `;
        
        const noFaults = document.createElement('div');
        noFaults.id = 'no-faults-message';
        noFaults.textContent = '暂无活动故障';
        noFaults.style.color = '#95a5a6';
        noFaults.style.textAlign = 'center';
        noFaults.style.padding = '10px';
        
        this.faultList.appendChild(noFaults);
        
        section.appendChild(title);
        section.appendChild(this.faultList);
        
        return section;
    }
    
    /**
     * 创建性能指标表格
     */
    createMetricsSection() {
        const section = document.createElement('div');
        section.style.marginBottom = '20px';
        
        const title = document.createElement('div');
        title.textContent = '⚡ 性能指标';
        title.style.cssText = `
            font-weight: bold;
            margin-bottom: 8px;
            color: #f39c12;
            font-size: 13px;
        `;
        
        this.metricsTable = document.createElement('table');
        this.metricsTable.style.cssText = `
            width: 100%;
            border-collapse: collapse;
            font-size: 11px;
        `;
        
        // 表头
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        headerRow.style.background = '#2c3e50';
        
        const th1 = document.createElement('th');
        th1.textContent = '指标';
        th1.style.padding = '6px 8px';
        th1.style.textAlign = 'left';
        th1.style.borderBottom = '1px solid #7f8c8d';
        
        const th2 = document.createElement('th');
        th2.textContent = '数值';
        th2.style.padding = '6px 8px';
        th2.style.textAlign = 'right';
        th2.style.borderBottom = '1px solid #7f8c8d';
        
        const th3 = document.createElement('th');
        th3.textContent = '状态';
        th3.style.padding = '6px 8px';
        th3.style.textAlign = 'center';
        th3.style.borderBottom = '1px solid #7f8c8d';
        
        headerRow.appendChild(th1);
        headerRow.appendChild(th2);
        headerRow.appendChild(th3);
        thead.appendChild(headerRow);
        
        // 表体
        const tbody = document.createElement('tbody');
        tbody.id = 'metrics-body';
        
        // 初始行
        const initialMetrics = [
            { name: '帧率 (FPS)', value: '--', unit: 'fps', status: 'normal' },
            { name: '渲染延迟', value: '--', unit: 'ms', status: 'normal' },
            { name: '内存使用', value: '--', unit: 'MB', status: 'normal' },
            { name: 'CPU占用', value: '--', unit: '%', status: 'normal' },
            { name: '网络延迟', value: '--', unit: 'ms', status: 'normal' },
            { name: '数据更新', value: '--', unit: 'Hz', status: 'normal' }
        ];
        
        initialMetrics.forEach(metric => {
            const row = this.createMetricRow(metric);
            tbody.appendChild(row);
        });
        
        this.metricsTable.appendChild(thead);
        this.metricsTable.appendChild(tbody);
        
        section.appendChild(title);
        section.appendChild(this.metricsTable);
        
        return section;
    }
    
    /**
     * 创建指标行
     */
    createMetricRow(metric) {
        const row = document.createElement('tr');
        row.style.borderBottom = '1px solid rgba(127, 140, 141, 0.2)';
        
        // 指标名称
        const nameCell = document.createElement('td');
        nameCell.textContent = metric.name;
        nameCell.style.padding = '6px 8px';
        
        // 数值
        const valueCell = document.createElement('td');
        valueCell.textContent = `${metric.value} ${metric.unit}`;
        valueCell.style.padding = '6px 8px';
        valueCell.style.textAlign = 'right';
        valueCell.style.fontFamily = 'monospace';
        
        // 状态指示器
        const statusCell = document.createElement('td');
        statusCell.style.padding = '6px 8px';
        statusCell.style.textAlign = 'center';
        
        const statusDot = document.createElement('div');
        statusDot.style.cssText = `
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin: 0 auto;
            background: ${this.getStatusColor(metric.status)};
        `;
        
        statusCell.appendChild(statusDot);
        
        row.appendChild(nameCell);
        row.appendChild(valueCell);
        row.appendChild(statusCell);
        
        return row;
    }
    
    /**
     * 创建实时日志显示
     */
    createLogSection() {
        const section = document.createElement('div');
        section.style.marginBottom = '20px';
        
        const title = document.createElement('div');
        title.textContent = '📝 系统日志';
        title.style.cssText = `
            font-weight: bold;
            margin-bottom: 8px;
            color: #9b59b6;
            font-size: 13px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        `;
        
        const clearBtn = document.createElement('button');
        clearBtn.textContent = '清空';
        clearBtn.style.cssText = `
            background: #9b59b6;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 10px;
            cursor: pointer;
        `;
        clearBtn.onclick = () => this.clearLogs();
        
        title.appendChild(clearBtn);
        
        this.logDisplay = document.createElement('div');
        this.logDisplay.id = 'log-display';
        this.logDisplay.style.cssText = `
            background: rgba(44, 62, 80, 0.7);
            border-radius: 6px;
            padding: 10px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 10px;
            line-height: 1.4;
            max-height: 150px;
            overflow-y: auto;
            white-space: pre-wrap;
        `;
        
        // 初始日志消息
        const initialLog = `[${new Date().toLocaleTimeString()}] 调试面板已启动\n`;
        this.addLogEntry(initialLog);
        
        section.appendChild(title);
        section.appendChild(this.logDisplay);
        
        return section;
    }
    
    /**
     * 创建故障注入控制面板
     */
    createControlSection() {
        const section = document.createElement('div');
        
        const title = document.createElement('div');
        title.textContent = '🔧 故障注入控制';
        title.style.cssText = `
            font-weight: bold;
            margin-bottom: 8px;
            color: #1abc9c;
            font-size: 13px;
        `;
        
        this.controlPanel = document.createElement('div');
        this.controlPanel.style.cssText = `
            background: rgba(26, 188, 156, 0.1);
            border: 1px solid rgba(26, 188, 156, 0.3);
            border-radius: 6px;
            padding: 10px;
        `;
        
        // 故障场景选择
        const faultSelect = document.createElement('div');
        faultSelect.style.marginBottom = '10px';
        
        const selectLabel = document.createElement('label');
        selectLabel.textContent = '选择故障场景: ';
        selectLabel.style.fontSize = '11px';
        selectLabel.style.marginRight = '8px';
        
        const select = document.createElement('select');
        select.id = 'fault-scenario-select';
        select.style.cssText = `
            background: #2c3e50;
            color: white;
            border: 1px solid #7f8c8d;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 11px;
            flex: 1;
        `;
        
        const faultScenarios = [
            { id: 'sensor_out_of_range', name: '传感器数据越界' },
            { id: 'sensor_stuck', name: '传感器数据卡滞' },
            { id: 'serial_timeout', name: '串口通信超时' },
            { id: 'mqtt_disconnect', name: 'MQTT连接断开' },
            { id: 'high_cpu_usage', name: 'CPU使用率过高' }
        ];
        
        faultScenarios.forEach(scenario => {
            const option = document.createElement('option');
            option.value = scenario.id;
            option.textContent = scenario.name;
            select.appendChild(option);
        });
        
        faultSelect.appendChild(selectLabel);
        faultSelect.appendChild(select);
        
        // 注入控制按钮
        const buttonGroup = document.createElement('div');
        buttonGroup.style.display = 'flex';
        buttonGroup.style.gap = '8px';
        
        const injectBtn = document.createElement('button');
        injectBtn.textContent = '注入故障';
        injectBtn.style.cssText = `
            background: #e74c3c;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-size: 11px;
            cursor: pointer;
            flex: 1;
        `;
        injectBtn.onclick = () => this.injectFault();
        
        const recoverBtn = document.createElement('button');
        recoverBtn.textContent = '恢复故障';
        recoverBtn.style.cssText = `
            background: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-size: 11px;
            cursor: pointer;
            flex: 1;
        `;
        recoverBtn.onclick = () => this.recoverFault();
        
        buttonGroup.appendChild(injectBtn);
        buttonGroup.appendChild(recoverBtn);
        
        this.controlPanel.appendChild(faultSelect);
        this.controlPanel.appendChild(buttonGroup);
        
        section.appendChild(title);
        section.appendChild(this.controlPanel);
        
        return section;
    }
    
    /**
     * 开始数据刷新
     */
    startRefreshing() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }
        
        this.refreshTimer = setInterval(() => {
            this.updatePanel();
        }, this.refreshInterval);
        
        console.log('🔄 启动调试面板数据刷新');
    }
    
    /**
     * 停止数据刷新
     */
    stopRefreshing() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
        
        console.log('🛑 停止调试面板数据刷新');
    }
    
    /**
     * 初始化性能监控
     */
    initPerformanceMonitoring() {
        // 监控Three.js渲染性能
        if (this.renderer) {
            this.performanceMetrics.fps = 60;
            this.performanceMetrics.frameTime = 16.7;
            
            let frameCount = 0;
            let lastTime = performance.now();
            
            const updatePerformance = () => {
                frameCount++;
                const currentTime = performance.now();
                const delta = currentTime - lastTime;
                
                if (delta >= 1000) {
                    this.performanceMetrics.fps = Math.round((frameCount * 1000) / delta);
                    this.performanceMetrics.frameTime = delta / frameCount;
                    
                    frameCount = 0;
                    lastTime = currentTime;
                }
                
                requestAnimationFrame(updatePerformance);
            };
            
            requestAnimationFrame(updatePerformance);
        }
        
        // 模拟其他性能指标
        this.performanceMetrics.memoryUsage = 120;
        this.performanceMetrics.cpuUsage = 45;
        this.performanceMetrics.networkLatency = 120;
        this.performanceMetrics.dataUpdateRate = 0.95;
    }
    
    /**
     * 更新面板数据
     */
    updatePanel() {
        // 更新系统状态
        this.updateStatus();
        
        // 更新故障列表
        this.updateFaultList();
        
        // 更新性能指标
        this.updateMetrics();
        
        // 更新运行时间
        this.updateUptime();
    }
    
    /**
     * 更新系统状态
     */
    updateStatus() {
        // 模拟状态变化
        const statusColors = {
            normal: '#2ecc71',
            warning: '#f39c12',
            error: '#e74c3c'
        };
        
        // 更新状态指示器
        this.statusIndicator.style.background = statusColors[this.systemStatus];
        this.statusIndicator.style.boxShadow = `0 0 10px ${statusColors[this.systemStatus]}`;
        
        // 更新状态文本
        const statusText = document.getElementById('system-status-text');
        if (statusText) {
            const statusMessages = {
                normal: '系统运行正常',
                warning: '系统存在警告',
                error: '系统发生故障'
            };
            statusText.textContent = statusMessages[this.systemStatus];
        }
    }
    
    /**
     * 更新故障列表
     */
    updateFaultList() {
        const faultList = document.getElementById('fault-list');
        if (!faultList) return;
        
        // 清空当前列表
        faultList.innerHTML = '';
        
        if (this.faultCodes.length === 0) {
            const noFaults = document.createElement('div');
            noFaults.id = 'no-faults-message';
            noFaults.textContent = '暂无活动故障';
            noFaults.style.color = '#95a5a6';
            noFaults.style.textAlign = 'center';
            noFaults.style.padding = '10px';
            faultList.appendChild(noFaults);
        } else {
            this.faultCodes.forEach(fault => {
                const faultItem = document.createElement('div');
                faultItem.style.cssText = `
                    padding: 6px 8px;
                    margin-bottom: 4px;
                    background: rgba(231, 76, 60, 0.2);
                    border-radius: 4px;
                    border-left: 3px solid #e74c3c;
                `;
                
                const faultCode = document.createElement('div');
                faultCode.textContent = `故障码: ${fault.code}`;
                faultCode.style.fontWeight = 'bold';
                faultCode.style.fontSize = '10px';
                
                const faultDesc = document.createElement('div');
                faultDesc.textContent = fault.description;
                faultDesc.style.fontSize = '9px';
                faultDesc.style.color = '#ecf0f1';
                faultDesc.style.marginTop = '2px';
                
                faultItem.appendChild(faultCode);
                faultItem.appendChild(faultDesc);
                faultList.appendChild(faultItem);
            });
        }
    }
    
    /**
     * 更新性能指标
     */
    updateMetrics() {
        const tbody = document.getElementById('metrics-body');
        if (!tbody) return;
        
        // 更新指标数据
        const metrics = [
            { name: '帧率 (FPS)', value: this.performanceMetrics.fps || 0, unit: 'fps', status: this.getMetricStatus('fps', this.performanceMetrics.fps) },
            { name: '渲染延迟', value: this.performanceMetrics.frameTime ? this.performanceMetrics.frameTime.toFixed(1) : '--', unit: 'ms', status: this.getMetricStatus('frameTime', this.performanceMetrics.frameTime) },
            { name: '内存使用', value: this.performanceMetrics.memoryUsage || 0, unit: 'MB', status: this.getMetricStatus('memory', this.performanceMetrics.memoryUsage) },
            { name: 'CPU占用', value: this.performanceMetrics.cpuUsage || 0, unit: '%', status: this.getMetricStatus('cpu', this.performanceMetrics.cpuUsage) },
            { name: '网络延迟', value: this.performanceMetrics.networkLatency || 0, unit: 'ms', status: this.getMetricStatus('network', this.performanceMetrics.networkLatency) },
            { name: '数据更新', value: this.performanceMetrics.dataUpdateRate ? this.performanceMetrics.dataUpdateRate.toFixed(2) : '--', unit: 'Hz', status: this.getMetricStatus('updateRate', this.performanceMetrics.dataUpdateRate) }
        ];
        
        // 清空并重建表格
        tbody.innerHTML = '';
        metrics.forEach(metric => {
            const row = this.createMetricRow(metric);
            tbody.appendChild(row);
        });
    }
    
    /**
     * 获取指标状态
     */
    getMetricStatus(type, value) {
        if (value === undefined || value === null) return 'normal';
        
        const thresholds = {
            fps: { warning: 30, error: 15 },
            frameTime: { warning: 33, error: 66 },
            memory: { warning: 200, error: 300 },
            cpu: { warning: 70, error: 90 },
            network: { warning: 200, error: 500 },
            updateRate: { warning: 0.8, error: 0.5 }
        };
        
        const threshold = thresholds[type];
        if (!threshold) return 'normal';
        
        if (value <= threshold.error) return 'error';
        if (value <= threshold.warning) return 'warning';
        return 'normal';
    }
    
    /**
     * 获取状态颜色
     */
    getStatusColor(status) {
        const colors = {
            normal: '#2ecc71',
            warning: '#f39c12',
            error: '#e74c3c'
        };
        return colors[status] || '#95a5a6';
    }
    
    /**
     * 更新运行时间
     */
    updateUptime() {
        const uptimeDisplay = document.getElementById('system-uptime');
        if (!uptimeDisplay) return;
        
        // 模拟运行时间（在实际系统中应从启动时间计算）
        const hours = Math.floor((Date.now() / 1000 / 3600) % 24);
        const minutes = Math.floor((Date.now() / 1000 / 60) % 60);
        const seconds = Math.floor((Date.now() / 1000) % 60);
        
        uptimeDisplay.textContent = `运行时间: ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }
    
    /**
     * 添加日志条目
     */
    addLogEntry(message) {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = `[${timestamp}] ${message}`;
        
        this.logEntries.push(logEntry);
        
        // 保持最大条目数
        if (this.logEntries.length > this.maxLogEntries) {
            this.logEntries.shift();
        }
        
        // 更新显示
        this.updateLogDisplay();
    }
    
    /**
     * 更新日志显示
     */
    updateLogDisplay() {
        if (!this.logDisplay) return;
        
        this.logDisplay.textContent = this.logEntries.join('\n');
        
        // 滚动到底部
        this.logDisplay.scrollTop = this.logDisplay.scrollHeight;
    }
    
    /**
     * 清空日志
     */
    clearLogs() {
        this.logEntries = [];
        this.updateLogDisplay();
        this.addLogEntry('日志已清空');
    }
    
    /**
     * 注入故障
     */
    injectFault() {
        const select = document.getElementById('fault-scenario-select');
        if (!select) return;
        
        const faultId = select.value;
        const faultName = select.options[select.selectedIndex].text;
        
        // 记录活动故障
        this.activeFaults.set(faultId, {
            id: faultId,
            name: faultName,
            injectedAt: Date.now()
        });
        
        // 添加故障码
        this.addFaultCode(faultId, faultName);
        
        // 更新系统状态
        this.systemStatus = 'error';
        
        // 添加日志
        this.addLogEntry(`注入故障: ${faultName}`);
        
        console.log(`🔴 注入故障: ${faultName}`);
        
        // 在实际系统中，这里应该调用后端API触发实际故障
        this.simulateFaultInjection(faultId);
    }
    
    /**
     * 恢复故障
     */
    recoverFault() {
        const select = document.getElementById('fault-scenario-select');
        if (!select) return;
        
        const faultId = select.value;
        const faultName = select.options[select.selectedIndex].text;
        
        // 移除活动故障
        if (this.activeFaults.has(faultId)) {
            this.activeFaults.delete(faultId);
        }
        
        // 移除故障码
        this.removeFaultCode(faultId);
        
        // 如果没有活动故障，恢复系统状态
        if (this.activeFaults.size === 0) {
            this.systemStatus = 'normal';
        }
        
        // 添加日志
        this.addLogEntry(`恢复故障: ${faultName}`);
        
        console.log(`🟢 恢复故障: ${faultName}`);
        
        // 在实际系统中，这里应该调用后端API恢复故障
        this.simulateFaultRecovery(faultId);
    }
    
    /**
     * 添加故障码
     */
    addFaultCode(code, description) {
        // 避免重复添加
        if (!this.faultCodes.some(f => f.code === code)) {
            this.faultCodes.push({
                code: code,
                description: description,
                timestamp: Date.now()
            });
        }
    }
    
    /**
     * 移除故障码
     */
    removeFaultCode(code) {
        this.faultCodes = this.faultCodes.filter(f => f.code !== code);
    }
    
    /**
     * 模拟故障注入
     */
    simulateFaultInjection(faultId) {
        // 根据故障ID模拟不同的故障效果
        switch (faultId) {
            case 'sensor_out_of_range':
                this.performanceMetrics.dataUpdateRate = 0.3;
                break;
            case 'serial_timeout':
                this.performanceMetrics.networkLatency = 800;
                break;
            case 'high_cpu_usage':
                this.performanceMetrics.cpuUsage = 95;
                break;
        }
    }
    
    /**
     * 模拟故障恢复
     */
    simulateFaultRecovery(faultId) {
        // 恢复指标到正常值
        switch (faultId) {
            case 'sensor_out_of_range':
                this.performanceMetrics.dataUpdateRate = 0.95;
                break;
            case 'serial_timeout':
                this.performanceMetrics.networkLatency = 120;
                break;
            case 'high_cpu_usage':
                this.performanceMetrics.cpuUsage = 45;
                break;
        }
    }
    
    /**
     * 切换面板可见性
     */
    toggleVisibility() {
        this.panelVisible = !this.panelVisible;
        this.panelElement.style.display = this.panelVisible ? 'block' : 'none';
        
        const action = this.panelVisible ? '显示' : '隐藏';
        this.addLogEntry(`${action}调试面板`);
    }
    
    /**
     * 设置系统状态
     */
    setSystemStatus(status) {
        const validStatus = ['normal', 'warning', 'error'];
        if (validStatus.includes(status)) {
            this.systemStatus = status;
            this.updateStatus();
        }
    }
    
    /**
     * 获取面板元素
     */
    getPanelElement() {
        return this.panelElement;
    }
    
    /**
     * 销毁面板
     */
    destroy() {
        this.stopRefreshing();
        
        if (this.panelElement && this.panelElement.parentNode) {
            this.panelElement.parentNode.removeChild(this.panelElement);
        }
        
        console.log('🗑️ 调试面板已销毁');
    }
}

// 导出类
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DebugPanel;
} else {
    // 浏览器环境，添加到全局
    window.DebugPanel = DebugPanel;
}