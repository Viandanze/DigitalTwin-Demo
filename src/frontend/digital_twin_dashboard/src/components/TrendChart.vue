<!--
  TrendChart.vue — ECharts trend chart component
  Displays time-series data for the selected device and metric
-->

<template>
  <div class="trend-chart-container">
    <div class="chart-header">
      <span class="chart-title">
        <el-icon><TrendCharts /></el-icon>
        Trend Analysis
      </span>
      <el-radio-group v-model="selectedMetric" size="small" @change="handleMetricChange">
        <el-radio-button label="temperature">Temp</el-radio-button>
        <el-radio-button label="humidity">Humidity</el-radio-button>
        <el-radio-button label="distance">Distance</el-radio-button>
        <el-radio-button label="pressure">Pressure</el-radio-button>
      </el-radio-group>
    </div>
    <div ref="chartRef" class="chart-canvas"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  deviceId: { type: String, default: null },
  historyData: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['metric-change'])

const chartRef = ref(null)
const selectedMetric = ref('temperature')
let chartInstance = null
let resizeObserver = null

// ==================== Chart Configuration ====================

function getChartOption(metric, data) {
  const metricConfig = {
    temperature: { name: 'Temperature (°C)', color: '#ff6b6b', unit: '°C' },
    humidity: { name: 'Humidity (%)', color: '#4ecdc4', unit: '%' },
    distance: { name: 'Distance (cm)', color: '#ffaa00', unit: 'cm' },
    pressure: { name: 'Pressure (hPa)', color: '#9b59b6', unit: 'hPa' },
  }

  const config = metricConfig[metric] || metricConfig.temperature

  // Format data for ECharts
  const chartData = (data || []).map((item) => {
    const timestamp = item.timestamp
      ? new Date(item.timestamp * 1000).toLocaleTimeString()
      : ''
    return [timestamp, item.value]
  })

  return {
    grid: {
      top: 10,
      right: 15,
      bottom: 25,
      left: 40
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(26, 26, 46, 0.95)',
      borderColor: '#2a2a4e',
      textStyle: { color: '#e0e0e0', fontSize: 11 },
      formatter: (params) => {
        const p = params[0]
        return `${p.axisValue}<br/>${config.name}: <b>${p.value[1]}</b> ${config.unit}`
      }
    },
    xAxis: {
      type: 'category',
      data: chartData.map((d) => d[0]),
      axisLine: { lineStyle: { color: '#333355' } },
      axisLabel: {
        color: '#777',
        fontSize: 9,
        rotate: 0,
        hideOverlap: true
      },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: { color: '#777', fontSize: 9 },
      splitLine: { lineStyle: { color: '#1a1a2e', type: 'dashed' } }
    },
    series: [
      {
        name: config.name,
        type: 'line',
        data: chartData.map((d) => d[1]),
        smooth: true,
        symbol: 'none',
        lineStyle: { color: config.color, width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: config.color + '40' },
            { offset: 1, color: config.color + '00' }
          ])
        },
        // Mark line for average
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#666', type: 'dashed', width: 1 },
          label: { color: '#999', fontSize: 9 },
          data: chartData.length > 0 ? [
            { type: 'average', name: 'Avg' }
          ] : []
        }
      }
    ],
    animation: true,
    animationDuration: 300,
    animationEasing: 'cubicOut'
  }
}

// ==================== Chart Lifecycle ====================

function initChart() {
  if (!chartRef.value) return
  chartInstance = echarts.init(chartRef.value, null, {
    renderer: 'canvas'
  })
  updateChart()

  // Resize observer for responsive chart
  resizeObserver = new ResizeObserver(() => {
    if (chartInstance) chartInstance.resize()
  })
  resizeObserver.observe(chartRef.value)
}

function updateChart() {
  if (!chartInstance) return
  const data = props.historyData[selectedMetric.value] || []
  chartInstance.setOption(getChartOption(selectedMetric.value, data), true)
}

function handleMetricChange(metric) {
  selectedMetric.value = metric
  emit('metric-change', metric)
  updateChart()
}

// ==================== Watchers ====================

// Update chart when history data changes
watch(
  () => props.historyData,
  () => updateChart(),
  { deep: true }
)

// Update chart when device changes
watch(
  () => props.deviceId,
  () => updateChart()
)

// ==================== Lifecycle ====================

onMounted(() => {
  nextTick(() => initChart())
})

onUnmounted(() => {
  if (resizeObserver) resizeObserver.disconnect()
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>

<style scoped>
.trend-chart-container {
  display: flex;
  flex-direction: column;
  padding: 8px 12px;
  background: #16213e;
  height: 100%;
  overflow: hidden;
}

.chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: #00d4ff;
  display: flex;
  align-items: center;
  gap: 6px;
}

.chart-canvas {
  flex: 1;
  min-height: 120px;
  width: 100%;
}

/* Override Element Plus radio button colors for dark theme */
:deep(.el-radio-button__inner) {
  background: #1a1a2e;
  border-color: #2a2a4e;
  color: #888;
  font-size: 11px;
  padding: 4px 10px;
}

:deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: #00d4ff;
  border-color: #00d4ff;
  color: #0d0d1a;
  box-shadow: -1px 0 0 0 #00d4ff;
}
</style>
