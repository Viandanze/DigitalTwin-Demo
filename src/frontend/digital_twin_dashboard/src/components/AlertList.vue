<!--
  AlertList.vue — Alert list panel
  Right sidebar: real-time alerts with severity levels and acknowledgment
-->

<template>
  <div class="alert-list-container">
    <div class="alert-header">
      <span class="alert-title">
        <el-icon><BellFilled /></el-icon>
        Alerts
      </span>
      <el-badge :value="unacknowledgedCount" :hidden="unacknowledgedCount === 0" :max="99" type="danger">
        <el-button size="small" text @click="acknowledgeAll" :disabled="unacknowledgedCount === 0">
          Ack All
        </el-button>
      </el-badge>
    </div>

    <!-- Severity filter -->
    <div class="severity-filters">
      <el-radio-group v-model="filterSeverity" size="small">
        <el-radio-button label="">All</el-radio-button>
        <el-radio-button label="critical">Critical</el-radio-button>
        <el-radio-button label="warning">Warning</el-radio-button>
        <el-radio-button label="info">Info</el-radio-button>
      </el-radio-group>
    </div>

    <!-- Alert list -->
    <el-scrollbar class="alert-scroll">
      <div
        v-for="alert in filteredAlerts"
        :key="alert.id"
        class="alert-item"
        :class="[`severity-${alert.severity}`, { acknowledged: alert.acknowledged }]"
        @click="$emit('click-device', alert.device_id)"
      >
        <div class="alert-item-left">
          <el-icon
            class="alert-icon"
            :color="severityColor(alert.severity)"
            size="16"
          >
            <component :is="severityIcon(alert.severity)" />
          </el-icon>
          <div class="alert-content">
            <div class="alert-message">{{ alert.message }}</div>
            <div class="alert-meta">
              <span class="alert-device">{{ alert.device_id }}</span>
              <span class="alert-time">{{ formatTime(alert.timestamp) }}</span>
            </div>
          </div>
        </div>
        <div class="alert-item-right">
          <el-button
            v-if="!alert.acknowledged"
            size="small"
            text
            circle
            @click.stop="$emit('acknowledge', alert.id)"
          >
            <el-icon><Check /></el-icon>
          </el-button>
          <el-icon v-else color="#555" size="14"><CircleCheck /></el-icon>
        </div>
      </div>

      <el-empty
        v-if="filteredAlerts.length === 0"
        description="No alerts"
        :image-size="50"
      />
    </el-scrollbar>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  alerts: { type: Array, default: () => [] }
})

const emit = defineEmits(['acknowledge', 'click-device'])

const filterSeverity = ref('')

// ==================== Computed ====================

const filteredAlerts = computed(() => {
  if (!filterSeverity.value) return props.alerts
  return props.alerts.filter((a) => a.severity === filterSeverity.value)
})

const unacknowledgedCount = computed(() =>
  props.alerts.filter((a) => !a.acknowledged).length
)

// ==================== Methods ====================

function severityColor(severity) {
  const map = {
    critical: '#ff3333',
    warning: '#ffaa00',
    info: '#409eff'
  }
  return map[severity] || '#666'
}

function severityIcon(severity) {
  const map = {
    critical: 'CircleCloseFilled',
    warning: 'WarningFilled',
    info: 'InfoFilled'
  }
  return map[severity] || 'InfoFilled'
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  const date = typeof timestamp === 'number'
    ? new Date(timestamp * 1000)
    : new Date(timestamp)
  return date.toLocaleTimeString()
}

function acknowledgeAll() {
  props.alerts.forEach((a) => {
    if (!a.acknowledged) emit('acknowledge', a.id)
  })
}
</script>

<style scoped>
.alert-list-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 12px;
  gap: 8px;
}

.alert-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.alert-title {
  font-size: 14px;
  font-weight: 600;
  color: #00d4ff;
  display: flex;
  align-items: center;
  gap: 6px;
}

.severity-filters {
  padding-bottom: 4px;
  border-bottom: 1px solid #2a2a4e;
}

.alert-scroll {
  flex: 1;
  overflow-y: auto;
}

.alert-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
  margin-bottom: 4px;
  border-left: 3px solid transparent;
}

.alert-item:hover {
  background: rgba(0, 212, 255, 0.06);
}

.alert-item.severity-critical {
  border-left-color: #ff3333;
}

.alert-item.severity-warning {
  border-left-color: #ffaa00;
}

.alert-item.severity-info {
  border-left-color: #409eff;
}

.alert-item.acknowledged {
  opacity: 0.5;
}

.alert-item-left {
  display: flex;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.alert-icon {
  flex-shrink: 0;
  margin-top: 1px;
}

.alert-content {
  min-width: 0;
}

.alert-message {
  font-size: 12px;
  color: #ccc;
  line-height: 1.4;
}

.alert-meta {
  display: flex;
  gap: 8px;
  margin-top: 3px;
}

.alert-device {
  font-size: 10px;
  color: #00d4ff;
  font-family: 'Courier New', monospace;
}

.alert-time {
  font-size: 10px;
  color: #555;
}

.alert-item-right {
  flex-shrink: 0;
}

/* Override Element Plus radio button for dark theme */
:deep(.el-radio-button__inner) {
  background: #1a1a2e;
  border-color: #2a2a4e;
  color: #888;
  font-size: 10px;
  padding: 3px 8px;
}

:deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: #00d4ff;
  border-color: #00d4ff;
  color: #0d0d1a;
  box-shadow: -1px 0 0 0 #00d4ff;
}
</style>
