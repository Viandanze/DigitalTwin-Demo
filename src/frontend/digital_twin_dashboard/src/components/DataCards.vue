<!--
  DataCards.vue — Real-time data cards
  Displays temperature, humidity, distance, pressure, motor speed, servo angle
-->

<template>
  <div class="data-cards-container">
    <div class="cards-header">
      <span class="cards-title">
        <el-icon><DataAnalysis /></el-icon>
        Real-time Data
      </span>
      <span v-if="deviceData" class="device-label">{{ deviceData.name || deviceData.device_id }}</span>
      <span v-else class="device-label">No device selected</span>
    </div>

    <div class="cards-grid">
      <!-- Temperature -->
      <div class="data-card" :class="{ active: !!deviceData?.temperature }">
        <div class="card-icon temp-icon">
          <el-icon><Sunrise /></el-icon>
        </div>
        <div class="card-body">
          <div class="card-label">Temperature</div>
          <div class="card-value">
            {{ deviceData?.temperature != null ? deviceData.temperature : '--' }}
            <span class="card-unit">°C</span>
          </div>
        </div>
        <div class="card-trend" v-if="tempTrend !== 0">
          <el-icon :color="tempTrend > 0 ? '#ff6b6b' : '#4ecdc4'" size="12">
            <component :is="tempTrend > 0 ? 'Top' : 'Bottom'" />
          </el-icon>
        </div>
      </div>

      <!-- Humidity -->
      <div class="data-card" :class="{ active: !!deviceData?.humidity }">
        <div class="card-icon humid-icon">
          <el-icon><Drizzling /></el-icon>
        </div>
        <div class="card-body">
          <div class="card-label">Humidity</div>
          <div class="card-value">
            {{ deviceData?.humidity != null ? deviceData.humidity : '--' }}
            <span class="card-unit">%</span>
          </div>
        </div>
        <div class="card-trend" v-if="humidTrend !== 0">
          <el-icon :color="humidTrend > 0 ? '#ff6b6b' : '#4ecdc4'" size="12">
            <component :is="humidTrend > 0 ? 'Top' : 'Bottom'" />
          </el-icon>
        </div>
      </div>

      <!-- Distance -->
      <div class="data-card" :class="{ active: !!deviceData?.distance }">
        <div class="card-icon dist-icon">
          <el-icon><Aim /></el-icon>
        </div>
        <div class="card-body">
          <div class="card-label">Distance</div>
          <div class="card-value">
            {{ deviceData?.distance != null ? deviceData.distance : '--' }}
            <span class="card-unit">cm</span>
          </div>
        </div>
      </div>

      <!-- Pressure -->
      <div class="data-card" :class="{ active: !!deviceData?.pressure }">
        <div class="card-icon press-icon">
          <el-icon><Odometer /></el-icon>
        </div>
        <div class="card-body">
          <div class="card-label">Pressure</div>
          <div class="card-value">
            {{ deviceData?.pressure != null ? deviceData.pressure : '--' }}
            <span class="card-unit">hPa</span>
          </div>
        </div>
      </div>

      <!-- Motor Speed -->
      <div class="data-card" :class="{ active: !!deviceData?.motor_speed }">
        <div class="card-icon motor-icon">
          <el-icon><Loading /></el-icon>
        </div>
        <div class="card-body">
          <div class="card-label">Motor Speed</div>
          <div class="card-value">
            {{ deviceData?.motor_speed != null ? deviceData.motor_speed : '--' }}
            <span class="card-unit">rpm</span>
          </div>
        </div>
      </div>

      <!-- Servo Angle -->
      <div class="data-card" :class="{ active: !!deviceData?.servo_angle }">
        <div class="card-icon servo-icon">
          <el-icon><Compass /></el-icon>
        </div>
        <div class="card-body">
          <div class="card-label">Servo Angle</div>
          <div class="card-value">
            {{ deviceData?.servo_angle != null ? deviceData.servo_angle : '--' }}
            <span class="card-unit">°</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  deviceData: { type: Object, default: null },
  allDevices: { type: Array, default: () => [] }
})

// Trend tracking (compare with previous values)
const prevTemp = ref(null)
const prevHumid = ref(null)
const tempTrend = ref(0)
const humidTrend = ref(0)

// Watch for data changes and compute trends
watch(
  () => props.deviceData?.temperature,
  (newVal, oldVal) => {
    if (newVal != null && oldVal != null) {
      tempTrend.value = newVal > oldVal ? 1 : newVal < oldVal ? -1 : 0
    }
  }
)

watch(
  () => props.deviceData?.humidity,
  (newVal, oldVal) => {
    if (newVal != null && oldVal != null) {
      humidTrend.value = newVal > oldVal ? 1 : newVal < oldVal ? -1 : 0
    }
  }
)
</script>

<style scoped>
.data-cards-container {
  display: flex;
  flex-direction: column;
  padding: 8px 12px;
  background: #16213e;
  height: 100%;
  overflow: hidden;
}

.cards-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.cards-title {
  font-size: 13px;
  font-weight: 600;
  color: #00d4ff;
  display: flex;
  align-items: center;
  gap: 6px;
}

.device-label {
  font-size: 11px;
  color: #888;
}

.cards-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  flex: 1;
  overflow-y: auto;
}

.data-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: rgba(26, 26, 46, 0.6);
  border-radius: 8px;
  border: 1px solid #2a2a4e;
  transition: all 0.3s;
  opacity: 0.5;
}

.data-card.active {
  opacity: 1;
  border-color: rgba(0, 212, 255, 0.2);
}

.data-card.active:hover {
  border-color: rgba(0, 212, 255, 0.4);
  background: rgba(0, 212, 255, 0.05);
}

.card-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 14px;
}

.temp-icon { background: rgba(255, 107, 107, 0.15); color: #ff6b6b; }
.humid-icon { background: rgba(78, 205, 196, 0.15); color: #4ecdc4; }
.dist-icon { background: rgba(255, 170, 0, 0.15); color: #ffaa00; }
.press-icon { background: rgba(155, 89, 182, 0.15); color: #9b59b6; }
.motor-icon { background: rgba(52, 152, 219, 0.15); color: #3498db; }
.servo-icon { background: rgba(46, 204, 113, 0.15); color: #2ecc71; }

.card-body {
  flex: 1;
  min-width: 0;
}

.card-label {
  font-size: 10px;
  color: #777;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.card-value {
  font-size: 16px;
  font-weight: 700;
  color: #e0e0e0;
  font-family: 'Courier New', monospace;
  line-height: 1.2;
}

.card-unit {
  font-size: 11px;
  font-weight: 400;
  color: #666;
  margin-left: 2px;
}

.card-trend {
  flex-shrink: 0;
}
</style>
