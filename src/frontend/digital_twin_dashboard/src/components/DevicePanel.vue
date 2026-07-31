<!--
  DevicePanel.vue — Device list and filter panel
  Left sidebar: search, filter, device list with status indicators
-->

<template>
  <div class="device-panel">
    <!-- Search and filter -->
    <div class="panel-header">
      <el-input
        v-model="searchQuery"
        placeholder="Search devices..."
        :prefix-icon="Search"
        clearable
        size="small"
        class="search-input"
      />
      <el-select
        v-model="filterType"
        placeholder="Type"
        clearable
        size="small"
        class="filter-select"
      >
        <el-option label="All Types" value="" />
        <el-option label="Sensor" value="sensor" />
        <el-option label="Motor" value="motor" />
        <el-option label="Controller" value="controller" />
        <el-option label="Actuator" value="actuator" />
        <el-option label="Gateway" value="gateway" />
      </el-select>
      <el-select
        v-model="filterStatus"
        placeholder="Status"
        clearable
        size="small"
        class="filter-select"
      >
        <el-option label="All Status" value="" />
        <el-option label="Online" value="online" />
        <el-option label="Warning" value="warning" />
        <el-option label="Error" value="error" />
        <el-option label="Offline" value="offline" />
      </el-select>
    </div>

    <!-- Device count summary -->
    <div class="device-summary">
      <span class="summary-item">
        <el-tag type="success" size="small" effect="dark">{{ statusCounts.online }}</el-tag> Online
      </span>
      <span class="summary-item">
        <el-tag type="warning" size="small" effect="dark">{{ statusCounts.warning }}</el-tag> Warning
      </span>
      <span class="summary-item">
        <el-tag type="danger" size="small" effect="dark">{{ statusCounts.error }}</el-tag> Error
      </span>
      <span class="summary-item">
        <el-tag type="info" size="small" effect="dark">{{ statusCounts.offline }}</el-tag> Offline
      </span>
    </div>

    <!-- Device list -->
    <el-scrollbar class="device-list-scroll">
      <div
        v-for="device in filteredDevices"
        :key="device.device_id"
        class="device-item"
        :class="{
          selected: device.device_id === selectedDeviceId,
          [`status-${device.status}`]: true
        }"
        @click="$emit('select', device.device_id)"
      >
        <div class="device-item-left">
          <span class="device-status-dot" :class="`dot-${device.status}`"></span>
          <div class="device-info">
            <div class="device-name">{{ device.name || device.device_id }}</div>
            <div class="device-meta">
              <el-tag size="small" effect="plain" class="type-tag">{{ device.device_type }}</el-tag>
              <span class="device-location">{{ device.location || 'Unknown' }}</span>
            </div>
          </div>
        </div>
        <div class="device-item-right">
          <el-icon
            v-if="device.status === 'error'"
            color="#ff3333"
            size="14"
          ><WarningFilled /></el-icon>
          <el-icon
            v-else-if="device.status === 'warning'"
            color="#ffaa00"
            size="14"
          ><Warning /></el-icon>
          <el-icon
            v-else-if="device.status === 'online'"
            color="#00ff88"
            size="14"
          ><CircleCheckFilled /></el-icon>
          <el-icon v-else color="#666666" size="14"><CircleCloseFilled /></el-icon>
        </div>
      </div>
      <el-empty
        v-if="filteredDevices.length === 0"
        description="No devices found"
        :image-size="60"
      />
    </el-scrollbar>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'

const props = defineProps({
  devices: { type: Array, default: () => [] },
  selectedDeviceId: { type: String, default: null }
})

const emit = defineEmits(['select', 'filter'])

// ==================== Reactive State ====================

const searchQuery = ref('')
const filterType = ref('')
const filterStatus = ref('')

// ==================== Computed ====================

const filteredDevices = computed(() => {
  let result = props.devices

  // Search filter
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter((d) =>
      d.device_id.toLowerCase().includes(q) ||
      (d.name && d.name.toLowerCase().includes(q)) ||
      (d.location && d.location.toLowerCase().includes(q))
    )
  }

  // Type filter
  if (filterType.value) {
    result = result.filter((d) => d.device_type === filterType.value)
  }

  // Status filter
  if (filterStatus.value) {
    result = result.filter((d) => d.status === filterStatus.value)
  }

  // Sort: error first, then warning, then online, then offline
  const statusOrder = { error: 0, warning: 1, online: 2, offline: 3 }
  result = [...result].sort((a, b) => {
    const orderA = statusOrder[a.status] ?? 4
    const orderB = statusOrder[b.status] ?? 4
    if (orderA !== orderB) return orderA - orderB
    return a.device_id.localeCompare(b.device_id)
  })

  return result
})

const statusCounts = computed(() => {
  const counts = { online: 0, warning: 0, error: 0, offline: 0 }
  for (const d of props.devices) {
    if (counts[d.status] !== undefined) counts[d.status]++
  }
  return counts
})

// ==================== Watchers ====================

// Emit filter changes when filters change
watch([filterType, filterStatus], () => {
  emit('filter', {
    type: filterType.value || undefined,
    status: filterStatus.value || undefined
  })
})
</script>

<style scoped>
.device-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 12px;
  gap: 8px;
}

.panel-header {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.search-input {
  width: 100%;
}

.filter-select {
  width: 100%;
}

.device-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 11px;
  color: #888;
  padding: 4px 0;
  border-bottom: 1px solid #2a2a4e;
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 3px;
}

.device-list-scroll {
  flex: 1;
  overflow-y: auto;
}

.device-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
  margin-bottom: 4px;
  border: 1px solid transparent;
}

.device-item:hover {
  background: rgba(0, 212, 255, 0.08);
}

.device-item.selected {
  background: rgba(0, 212, 255, 0.15);
  border-color: rgba(0, 212, 255, 0.3);
}

.device-item.status-error {
  border-left: 3px solid #ff3333;
}

.device-item.status-warning {
  border-left: 3px solid #ffaa00;
}

.device-item-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.device-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-online { background: #00ff88; box-shadow: 0 0 6px #00ff88; }
.dot-warning { background: #ffaa00; box-shadow: 0 0 6px #ffaa00; }
.dot-error { background: #ff3333; box-shadow: 0 0 6px #ff3333; animation: pulse 1s infinite; }
.dot-offline { background: #666666; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.device-info {
  min-width: 0;
}

.device-name {
  font-size: 13px;
  font-weight: 500;
  color: #ddd;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.device-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
}

.type-tag {
  transform: scale(0.85);
  transform-origin: left center;
}

.device-location {
  font-size: 11px;
  color: #777;
}

.device-item-right {
  flex-shrink: 0;
  padding-left: 4px;
}
</style>
