<!--
  App.vue — Main Layout
  Digital Twin Dashboard
  Layout: Top navigation + Left device panel + Center 3D scene + Bottom data cards
-->

<template>
  <div class="dashboard-container">
    <!-- ==================== Top Navigation ==================== -->
    <header class="dashboard-header">
      <div class="header-left">
        <h1 class="dashboard-title">
          <el-icon><Monitor /></el-icon>
          Digital Twin Dashboard
        </h1>
      </div>
      <div class="header-center">
        <el-tag :type="wsConnected ? 'success' : 'danger'" effect="dark" round>
          <el-icon><component :is="wsConnected ? 'Connection' : 'Disconnect'" /></el-icon>
          {{ wsConnected ? 'Connected' : 'Disconnected' }}
        </el-tag>
        <el-tag type="info" effect="plain" round>
          <el-icon><Timer /></el-icon>
          {{ currentTime }}
        </el-tag>
      </div>
      <div class="header-right">
        <el-badge :value="alertCount" :hidden="alertCount === 0" :max="99">
          <el-button :icon="Bell" circle @click="showAlerts = !showAlerts" />
        </el-badge>
        <el-button :icon="Refresh" circle @click="refreshAll" :loading="refreshing" />
      </div>
    </header>

    <!-- ==================== Main Content Area ==================== -->
    <main class="dashboard-main">
      <!-- Left: Device Panel -->
      <aside class="panel-left" :class="{ collapsed: !showDevicePanel }">
        <DevicePanel
          :devices="devices"
          :selected-device-id="selectedDeviceId"
          @select="handleDeviceSelect"
          @filter="handleFilterChange"
        />
      </aside>

      <!-- Center: 3D Scene -->
      <section class="panel-center">
        <ThreeScene
          ref="threeSceneRef"
          :devices="devices"
          :selected-device-id="selectedDeviceId"
          @device-click="handle3DDeviceClick"
        />
      </section>

      <!-- Right: Alert List (toggleable) -->
      <aside class="panel-right" v-if="showAlerts">
        <AlertList
          :alerts="alerts"
          @acknowledge="handleAlertAck"
          @click-device="handleAlertDeviceClick"
        />
      </aside>
    </main>

    <!-- ==================== Bottom: Data Cards ==================== -->
    <footer class="dashboard-footer">
      <DataCards
        :device-data="selectedDeviceData"
        :all-devices="devices"
      />
      <TrendChart
        :device-id="selectedDeviceId"
        :history-data="historyData"
        @metric-change="handleMetricChange"
      />
    </footer>

    <!-- ==================== Mobile Toggle Buttons ==================== -->
    <div class="mobile-toggles">
      <el-button
        :type="showDevicePanel ? 'primary' : 'default'"
        :icon="showDevicePanel ? 'Fold' : 'Expand'"
        circle
        @click="showDevicePanel = !showDevicePanel"
        class="toggle-btn toggle-devices"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { Bell, Refresh } from '@element-plus/icons-vue'
import DevicePanel from './components/DevicePanel.vue'
import DataCards from './components/DataCards.vue'
import TrendChart from './components/TrendChart.vue'
import ThreeScene from './components/ThreeScene.vue'
import AlertList from './components/AlertList.vue'
import { createWSClient } from './utils/ws_client.js'

// ==================== Reactive State ====================

const devices = ref([])
const selectedDeviceId = ref(null)
const alerts = ref([])
const historyData = ref({})
const wsConnected = ref(false)
const refreshing = ref(false)
const showAlerts = ref(false)
const showDevicePanel = ref(true)
const currentTime = ref('')
const threeSceneRef = ref(null)

// WebSocket client instance
let wsClient = null

// Timer for clock display
let clockTimer = null

// ==================== Computed ====================

const selectedDeviceData = computed(() => {
  if (!selectedDeviceId.value) return null
  return devices.value.find((d) => d.device_id === selectedDeviceId.value) || null
})

const alertCount = computed(() => alerts.value.filter((a) => !a.acknowledged).length)

// ==================== Methods ====================

/**
 * Handle device selection from DevicePanel
 * Triggers 3D scene highlight + camera focus
 */
function handleDeviceSelect(deviceId) {
  selectedDeviceId.value = deviceId
  // The ThreeScene component watches selectedDeviceId and will focus the camera
}

/**
 * Handle device click from the 3D scene (raycasting)
 */
function handle3DDeviceClick(deviceId) {
  selectedDeviceId.value = deviceId
}

/**
 * Handle filter changes from DevicePanel
 */
function handleFilterChange(filter) {
  // Fetch filtered device list from API
  fetchDevices(filter)
}

/**
 * Handle metric change from TrendChart
 */
function handleMetricChange(metric) {
  fetchHistory(selectedDeviceId.value, metric)
}

/**
 * Handle alert acknowledgment
 */
function handleAlertAck(alertId) {
  const alert = alerts.value.find((a) => a.id === alertId)
  if (alert) alert.acknowledged = true
}

/**
 * Handle clicking a device from an alert
 */
function handleAlertDeviceClick(deviceId) {
  selectedDeviceId.value = deviceId
  showDevicePanel.value = true
}

/**
 * Refresh all data
 */
async function refreshAll() {
  refreshing.value = true
  await Promise.all([
    fetchDevices(),
    fetchAlerts()
  ])
  refreshing.value = false
}

/**
 * Fetch device list from API
 */
async function fetchDevices(filter = {}) {
  try {
    const params = new URLSearchParams()
    if (filter.type) params.set('device_type', filter.type)
    if (filter.status) params.set('status', filter.status)
    if (filter.location) params.set('location', filter.location)
    params.set('page', '1')
    params.set('page_size', '100')

    const res = await fetch(`/api/v2/devices?${params}`)
    const data = await res.json()
    devices.value = data
  } catch (err) {
    console.error('[App] Failed to fetch devices:', err)
    // Fallback to mock data for development
    devices.value = generateMockDevices()
  }
}

/**
 * Fetch alerts from API
 */
async function fetchAlerts() {
  try {
    const res = await fetch('/api/v2/alerts/rules')
    if (res.ok) {
      alerts.value = await res.json()
    }
  } catch (err) {
    console.error('[App] Failed to fetch alerts:', err)
  }
}

/**
 * Fetch historical data for trend chart
 */
async function fetchHistory(deviceId, metric) {
  if (!deviceId) return
  try {
    const res = await fetch(`/api/v2/history/${deviceId}/${metric}?limit=100`)
    if (res.ok) {
      const data = await res.json()
      historyData.value = { ...historyData.value, [metric]: data.data || [] }
    }
  } catch (err) {
    console.error('[App] Failed to fetch history:', err)
  }
}

/**
 * Generate mock devices for development without backend
 */
function generateMockDevices() {
  const types = ['sensor', 'motor', 'controller', 'actuator']
  const statuses = ['online', 'online', 'online', 'warning', 'error', 'offline']
  const locations = ['Lab A', 'Lab B', 'Lab C', 'Server Room']
  const mock = []
  for (let i = 1; i <= 12; i++) {
    const type = types[i % types.length]
    mock.push({
      device_id: `${type}_${String(i).padStart(3, '0')}`,
      device_type: type,
      name: `${type.charAt(0).toUpperCase() + type.slice(1)} #${i}`,
      location: locations[i % locations.length],
      status: statuses[i % statuses.length],
      temperature: type === 'sensor' ? (20 + Math.random() * 15).toFixed(1) : null,
      humidity: type === 'sensor' ? (30 + Math.random() * 40).toFixed(1) : null,
      distance: type === 'sensor' ? (Math.random() * 100).toFixed(1) : null,
      pressure: type === 'sensor' ? (990 + Math.random() * 30).toFixed(1) : null,
      motor_speed: type === 'motor' ? Math.floor(Math.random() * 255) : null,
      servo_angle: type === 'actuator' ? Math.floor(Math.random() * 180) : null,
      position: {
        x: (Math.random() - 0.5) * 40,
        y: 0,
        z: (Math.random() - 0.5) * 40
      },
      timestamp: Date.now()
    })
  }
  return mock
}

/**
 * WebSocket message handler
 */
function handleWSMessage(msg) {
  if (!msg || !msg.type) return

  switch (msg.type) {
    case 'snapshot':
      // Initial device snapshot on connect
      if (msg.devices) {
        const deviceList = Object.values(msg.devices).map((d) => ({
          ...d,
          position: { x: (Math.random() - 0.5) * 40, y: 0, z: (Math.random() - 0.5) * 40 }
        }))
        devices.value = deviceList
      }
      break

    case 'sensor_update':
      // Update specific device sensor data
      {
        const device = devices.value.find((d) => d.device_id === msg.device_id)
        if (device) {
          if (msg.sensor_type === 'temperature') device.temperature = msg.value
          else if (msg.sensor_type === 'humidity') device.humidity = msg.value
          else if (msg.sensor_type === 'distance') device.distance = msg.value
          else if (msg.sensor_type === 'pressure') device.pressure = msg.value
          else if (msg.sensor_type === 'motor') device.motor_speed = msg.value
          else if (msg.sensor_type === 'servo') device.servo_angle = msg.value
          device.timestamp = msg.timestamp
        }
      }
      break

    case 'status_update':
      {
        const device = devices.value.find((d) => d.device_id === msg.device_id)
        if (device) {
          device.status = msg.status
          device.timestamp = msg.timestamp
        }
        // Generate alert for error/warning status
        if (msg.status === 'error' || msg.status === 'warning') {
          alerts.value.unshift({
            id: `alert_${Date.now()}`,
            device_id: msg.device_id,
            severity: msg.status === 'error' ? 'critical' : 'warning',
            message: `Device ${msg.device_id} status changed to ${msg.status}`,
            timestamp: msg.timestamp,
            acknowledged: false
          })
        }
      }
      break

    case 'pong':
      // Heartbeat response — connection is alive
      break
  }
}

// ==================== Lifecycle ====================

onMounted(() => {
  // Update clock every second
  clockTimer = setInterval(() => {
    currentTime.value = new Date().toLocaleTimeString()
  }, 1000)

  // Initialize WebSocket connection
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/ws/dashboard_${Date.now()}`

  wsClient = createWSClient(wsUrl, {
    onMessage: handleWSMessage,
    onConnect: () => { wsConnected.value = true },
    onDisconnect: () => { wsConnected.value = false },
    autoReconnect: true,
    reconnectInterval: 2000,
    maxReconnectInterval: 10000,
    heartbeatInterval: 10000
  })
  wsClient.connect()

  // Fetch initial data
  fetchDevices()
})

onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
  if (wsClient) wsClient.disconnect()
})

// Watch for device selection changes to fetch history
watch(selectedDeviceId, (newId) => {
  if (newId) {
    fetchHistory(newId, 'temperature')
  }
})
</script>

<style scoped>
.dashboard-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: #0d0d1a;
  color: #e0e0e0;
}

/* Header */
.dashboard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 56px;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-bottom: 1px solid #2a2a4e;
  flex-shrink: 0;
  z-index: 100;
}

.dashboard-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #00d4ff;
}

.header-center {
  display: flex;
  gap: 12px;
  align-items: center;
}

.header-right {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* Main content area */
.dashboard-main {
  display: flex;
  flex: 1;
  overflow: hidden;
  gap: 1px;
  background: #1a1a2e;
}

.panel-left {
  width: 280px;
  flex-shrink: 0;
  background: #16213e;
  overflow-y: auto;
  transition: width 0.3s ease, margin 0.3s ease;
}

.panel-left.collapsed {
  width: 0;
  margin-left: -1px;
  overflow: hidden;
}

.panel-center {
  flex: 1;
  position: relative;
  background: #0d0d1a;
  overflow: hidden;
}

.panel-right {
  width: 300px;
  flex-shrink: 0;
  background: #16213e;
  overflow-y: auto;
}

/* Footer (data cards + trend chart) */
.dashboard-footer {
  display: flex;
  gap: 1px;
  height: 200px;
  flex-shrink: 0;
  background: #1a1a2e;
  border-top: 1px solid #2a2a4e;
}

.dashboard-footer > * {
  flex: 1;
}

/* Mobile toggle buttons */
.mobile-toggles {
  display: none;
}

/* Responsive styles are in responsive.css */
</style>
