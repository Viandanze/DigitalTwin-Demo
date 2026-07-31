<!--
  ThreeScene.vue — Three.js 3D scene embedded in Vue
  Renders the digital twin 3D scene with device visualization
  Supports device highlighting and camera focus on selection
-->

<template>
  <div ref="containerRef" class="three-scene-container">
    <!-- 3D canvas renders here -->

    <!-- Overlay: scene info -->
    <div class="scene-overlay top-left">
      <div class="overlay-item">
        <span class="overlay-label">FPS</span>
        <span class="overlay-value">{{ stats.fps }}</span>
      </div>
      <div class="overlay-item">
        <span class="overlay-label">Devices</span>
        <span class="overlay-value">{{ stats.deviceCount }}</span>
      </div>
      <div class="overlay-item">
        <span class="overlay-label">Draw Calls</span>
        <span class="overlay-value">{{ stats.drawCalls }}</span>
      </div>
    </div>

    <!-- Overlay: controls hint -->
    <div class="scene-overlay bottom-left">
      <span class="hint-text">Drag to rotate · Scroll to zoom · Click device to select</span>
    </div>

    <!-- Overlay: selected device info -->
    <div v-if="selectedDevice" class="scene-overlay top-right">
      <div class="device-detail-card">
        <div class="detail-header">
          <span class="detail-title">{{ selectedDevice.name || selectedDevice.device_id }}</span>
          <el-tag :type="statusTagType(selectedDevice.status)" size="small" effect="dark">
            {{ selectedDevice.status }}
          </el-tag>
        </div>
        <div class="detail-body">
          <div class="detail-row">
            <span class="detail-key">ID</span>
            <span class="detail-val">{{ selectedDevice.device_id }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-key">Type</span>
            <span class="detail-val">{{ selectedDevice.device_type }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-key">Location</span>
            <span class="detail-val">{{ selectedDevice.location || 'N/A' }}</span>
          </div>
          <div v-if="selectedDevice.temperature != null" class="detail-row">
            <span class="detail-key">Temp</span>
            <span class="detail-val">{{ selectedDevice.temperature }} °C</span>
          </div>
          <div v-if="selectedDevice.humidity != null" class="detail-row">
            <span class="detail-key">Humidity</span>
            <span class="detail-val">{{ selectedDevice.humidity }} %</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading overlay -->
    <div v-if="loading" class="loading-overlay">
      <el-icon class="loading-icon" :size="32"><Loading /></el-icon>
      <span>Loading 3D scene...</span>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'

const props = defineProps({
  devices: { type: Array, default: () => [] },
  selectedDeviceId: { type: String, default: null }
})

const emit = defineEmits(['device-click'])

const containerRef = ref(null)
const loading = ref(true)
const stats = reactive({ fps: 0, deviceCount: 0, drawCalls: 0 })

// Use shallowRef for Three.js objects to avoid Vue's deep reactivity overhead
const sceneRef = shallowRef(null)
const cameraRef = shallowRef(null)
const rendererRef = shallowRef(null)
const controlsRef = shallowRef(null)

let animationId = null
let clock = null
let raycaster = null
let mouse = null
let instancedMeshes = {}
let deviceMap = new Map() // device_id -> { mesh, index, type, object3D }
let highlightMesh = null
let resizeObserver = null
let fpsAccumulator = 0
let fpsFrameCount = 0
let lastFpsUpdate = 0

// ==================== Scene Initialization ====================

function initScene() {
  const container = containerRef.value
  const width = container.clientWidth
  const height = container.clientHeight

  // Scene
  const scene = new THREE.Scene()
  scene.background = new THREE.Color(0x0d0d1a)
  scene.fog = new THREE.FogExp2(0x0d0d1a, 0.008)
  sceneRef.value = scene

  // Camera
  const camera = new THREE.PerspectiveCamera(50, width / height, 0.5, 500)
  camera.position.set(30, 25, 40)
  camera.lookAt(0, 0, 0)
  cameraRef.value = camera

  // Renderer
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    powerPreference: 'high-performance'
  })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.0
  container.appendChild(renderer.domElement)
  rendererRef.value = renderer

  // Lights
  const ambient = new THREE.AmbientLight(0x404060, 0.5)
  scene.add(ambient)

  const dirLight = new THREE.DirectionalLight(0xffffff, 1.0)
  dirLight.position.set(30, 50, 20)
  dirLight.castShadow = true
  dirLight.shadow.mapSize.set(2048, 2048)
  dirLight.shadow.camera.near = 0.5
  dirLight.shadow.camera.far = 200
  dirLight.shadow.camera.left = -60
  dirLight.shadow.camera.right = 60
  dirLight.shadow.camera.top = 60
  dirLight.shadow.camera.bottom = -60
  scene.add(dirLight)

  // Hemisphere light for better ambient
  const hemiLight = new THREE.HemisphereLight(0x4488ff, 0x1a1a2e, 0.3)
  scene.add(hemiLight)

  // Ground plane
  const groundGeo = new THREE.PlaneGeometry(100, 100)
  const groundMat = new THREE.MeshStandardMaterial({
    color: 0x1a1a2e,
    roughness: 0.9,
    metalness: 0.1
  })
  const ground = new THREE.Mesh(groundGeo, groundMat)
  ground.rotation.x = -Math.PI / 2
  ground.receiveShadow = true
  scene.add(ground)

  // Grid helper
  const grid = new THREE.GridHelper(100, 50, 0x2a2a4e, 0x1a1a3e)
  grid.material.opacity = 0.5
  grid.material.transparent = true
  scene.add(grid)

  // Controls
  const controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.maxPolarAngle = Math.PI / 2.1
  controls.minDistance = 5
  controls.maxDistance = 100
  controlsRef.value = controls

  // Raycaster for click detection
  raycaster = new THREE.Raycaster()
  mouse = new THREE.Vector2()

  // Click event
  renderer.domElement.addEventListener('click', onSceneClick)

  // Clock for animation timing
  clock = new THREE.Clock()

  // Highlight mesh (a wireframe sphere that appears around selected device)
  const highlightGeo = new THREE.SphereGeometry(1.2, 16, 16)
  const highlightMat = new THREE.MeshBasicMaterial({
    color: 0x00d4ff,
    wireframe: true,
    transparent: true,
    opacity: 0.6
  })
  highlightMesh = new THREE.Mesh(highlightGeo, highlightMat)
  highlightMesh.visible = false
  scene.add(highlightMesh)

  // Resize observer
  resizeObserver = new ResizeObserver(onResize)
  resizeObserver.observe(container)

  loading.value = false
}

// ==================== Device Mesh Creation ====================

function getDeviceGeometry(type) {
  const cache = getDeviceGeometry._cache || (getDeviceGeometry._cache = {})
  if (!cache[type]) {
    switch (type) {
      case 'sensor':
        cache[type] = new THREE.BoxGeometry(0.6, 0.4, 0.6)
        break
      case 'motor':
        cache[type] = new THREE.CylinderGeometry(0.3, 0.35, 1.0, 24)
        break
      case 'controller':
        cache[type] = new THREE.BoxGeometry(0.8, 1.2, 0.8)
        break
      case 'actuator':
        cache[type] = new THREE.BoxGeometry(0.5, 0.8, 0.5)
        break
      case 'gateway':
        cache[type] = new THREE.BoxGeometry(1.0, 0.3, 0.8)
        break
      default:
        cache[type] = new THREE.BoxGeometry(0.6, 0.6, 0.6)
    }
  }
  return cache[type]
}

function getStatusColor(status) {
  const colors = {
    online: new THREE.Color(0x00ff88),
    warning: new THREE.Color(0xffaa00),
    error: new THREE.Color(0xff3333),
    offline: new THREE.Color(0x555555)
  }
  return colors[status] || colors.offline
}

function createDeviceMeshes(devices) {
  // Clear existing meshes
  Object.values(instancedMeshes).forEach((mesh) => {
    sceneRef.value.remove(mesh)
    mesh.geometry.dispose()
    mesh.material.dispose()
  })
  instancedMeshes = {}
  deviceMap.clear()

  // Group devices by type
  const groups = {}
  devices.forEach((d, idx) => {
    const type = d.device_type || 'default'
    if (!groups[type]) groups[type] = []
    groups[type].push({ device: d, index: idx })
  })

  // Create InstancedMesh per type
  Object.entries(groups).forEach(([type, items]) => {
    const geometry = getDeviceGeometry(type)
    const material = new THREE.MeshStandardMaterial({
      roughness: 0.5,
      metalness: 0.6,
      vertexColors: false
    })
    const mesh = new THREE.InstancedMesh(geometry, material, items.length)
    mesh.castShadow = true
    mesh.receiveShadow = true
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage)

    const dummy = new THREE.Object3D()
    items.forEach((item, i) => {
      const pos = item.device.position || { x: 0, y: 0, z: 0 }
      dummy.position.set(pos.x, pos.y + 0.5, pos.z) // Offset up so it sits on ground
      dummy.scale.set(1, 1, 1)
      dummy.rotation.set(0, 0, 0)
      dummy.updateMatrix()
      mesh.setMatrixAt(i, dummy.matrix)
      mesh.setColorAt(i, getStatusColor(item.device.status))

      // Map device_id to mesh info
      deviceMap.set(item.device.device_id, {
        mesh: mesh,
        index: i,
        type: type,
        position: new THREE.Vector3(pos.x, pos.y + 0.5, pos.z)
      })
    })

    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true

    sceneRef.value.add(mesh)
    instancedMeshes[type] = mesh
  })

  stats.deviceCount = devices.length
}

// ==================== Interaction ====================

function onSceneClick(event) {
  const rect = rendererRef.value.domElement.getBoundingClientRect()
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

  raycaster.setFromCamera(mouse, cameraRef.value)

  const meshes = Object.values(instancedMeshes)
  const intersects = raycaster.intersectObjects(meshes)

  if (intersects.length > 0) {
    const hit = intersects[0]
    const instanceId = hit.instanceId
    const mesh = hit.object

    // Find device_id from reverse lookup
    for (const [deviceId, info] of deviceMap) {
      if (info.mesh === mesh && info.index === instanceId) {
        emit('device-click', deviceId)
        break
      }
    }
  }
}

function focusOnDevice(deviceId) {
  const info = deviceMap.get(deviceId)
  if (!info) return

  // Move highlight mesh to device position
  highlightMesh.position.copy(info.position)
  highlightMesh.visible = true

  // Animate camera to look at device
  const targetPos = info.position.clone()
  const camOffset = new THREE.Vector3(8, 6, 8)
  const newCamPos = targetPos.clone().add(camOffset)

  // Smooth camera transition
  animateCamera(newCamPos, targetPos)

  // Pulse animation for highlight
  animateHighlight()
}

function animateCamera(targetPosition, lookAt) {
  const startPos = cameraRef.value.position.clone()
  const startTarget = controlsRef.value.target.clone()
  const duration = 800 // ms
  const startTime = performance.now()

  function step() {
    const elapsed = performance.now() - startTime
    const t = Math.min(elapsed / duration, 1)
    // Ease out cubic
    const eased = 1 - Math.pow(1 - t, 3)

    cameraRef.value.position.lerpVectors(startPos, targetPosition, eased)
    controlsRef.value.target.lerpVectors(startTarget, lookAt, eased)
    controlsRef.value.update()

    if (t < 1) {
      requestAnimationFrame(step)
    }
  }
  step()
}

function animateHighlight() {
  let scale = 1
  let growing = true
  const minScale = 1.0
  const maxScale = 1.4
  const speed = 0.03

  function pulse() {
    if (!highlightMesh.visible) return
    if (growing) {
      scale += speed
      if (scale >= maxScale) growing = false
    } else {
      scale -= speed
      if (scale <= minScale) growing = true
    }
    highlightMesh.scale.set(scale, scale, scale)
    requestAnimationFrame(pulse)
  }
  pulse()
}

// ==================== Status Update ====================

function updateDeviceStatus(deviceId, status) {
  const info = deviceMap.get(deviceId)
  if (!info) return
  info.mesh.setColorAt(info.index, getStatusColor(status))
  if (info.mesh.instanceColor) info.mesh.instanceColor.needsUpdate = true
}

// ==================== Resize ====================

function onResize() {
  const container = containerRef.value
  if (!container || !cameraRef.value || !rendererRef.value) return
  const width = container.clientWidth
  const height = container.clientHeight
  cameraRef.value.aspect = width / height
  cameraRef.value.updateProjectionMatrix()
  rendererRef.value.setSize(width, height)
}

// ==================== Animation Loop ====================

function animate() {
  animationId = requestAnimationFrame(animate)

  const delta = clock.getDelta()
  const elapsed = clock.elapsedTime

  controlsRef.value.update()

  // Update highlight rotation
  if (highlightMesh.visible) {
    highlightMesh.rotation.y = elapsed * 0.5
  }

  // Render
  rendererRef.value.render(sceneRef.value, cameraRef.value)

  // FPS calculation (update every 0.5s)
  fpsFrameCount++
  fpsAccumulator += delta
  if (elapsed - lastFpsUpdate >= 0.5) {
    stats.fps = Math.round(fpsFrameCount / fpsAccumulator)
    stats.drawCalls = rendererRef.value.info.render.calls
    fpsFrameCount = 0
    fpsAccumulator = 0
    lastFpsUpdate = elapsed
  }
}

// ==================== Utility ====================

function statusTagType(status) {
  const map = {
    online: 'success',
    warning: 'warning',
    error: 'danger',
    offline: 'info'
  }
  return map[status] || 'info'
}

// ==================== Watchers ====================

// Watch device list changes
watch(
  () => props.devices,
  (newDevices) => {
    if (sceneRef.value && newDevices.length > 0) {
      createDeviceMeshes(newDevices)
    }
  },
  { deep: false }
)

// Watch selected device changes
watch(
  () => props.selectedDeviceId,
  (newId, oldId) => {
    if (newId) {
      focusOnDevice(newId)
      // Also update highlight when data changes
      const device = props.devices.find((d) => d.device_id === newId)
      if (device) updateDeviceStatus(newId, device.status)
    } else {
      highlightMesh.visible = false
    }
  }
)

// Watch for status changes in devices
watch(
  () => props.devices.map((d) => d.status).join(','),
  () => {
    if (!sceneRef.value) return
    props.devices.forEach((d) => {
      updateDeviceStatus(d.device_id, d.status)
    })
  }
)

// Computed-like: selected device info for overlay
const selectedDevice = ref(null)
watch(
  () => [props.selectedDeviceId, props.devices],
  () => {
    if (props.selectedDeviceId) {
      selectedDevice.value = props.devices.find((d) => d.device_id === props.selectedDeviceId) || null
    } else {
      selectedDevice.value = null
    }
  },
  { deep: true, immediate: true }
)

// ==================== Lifecycle ====================

onMounted(() => {
  initScene()
  if (props.devices.length > 0) {
    createDeviceMeshes(props.devices)
  }
  animate()
})

onUnmounted(() => {
  if (animationId) cancelAnimationFrame(animationId)
  if (resizeObserver) resizeObserver.disconnect()
  if (rendererRef.value) {
    rendererRef.value.domElement.removeEventListener('click', onSceneClick)
    rendererRef.value.dispose()
    if (containerRef.value && rendererRef.value.domElement.parentNode) {
      containerRef.value.removeChild(rendererRef.value.domElement)
    }
  }
  // Dispose geometries and materials
  Object.values(instancedMeshes).forEach((mesh) => {
    mesh.geometry.dispose()
    mesh.material.dispose()
  })
  if (highlightMesh) {
    highlightMesh.geometry.dispose()
    highlightMesh.material.dispose()
  }
})

// Expose methods for parent component
defineExpose({
  focusOnDevice,
  updateDeviceStatus
})
</script>

<style scoped>
.three-scene-container {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
}

.scene-overlay {
  position: absolute;
  z-index: 10;
  pointer-events: none;
  display: flex;
  gap: 12px;
}

.top-left { top: 12px; left: 12px; }
.top-right { top: 12px; right: 12px; pointer-events: auto; }
.bottom-left { bottom: 12px; left: 12px; }

.overlay-item {
  display: flex;
  flex-direction: column;
  background: rgba(13, 13, 26, 0.8);
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid #2a2a4e;
  min-width: 50px;
}

.overlay-label {
  font-size: 9px;
  color: #666;
  text-transform: uppercase;
}

.overlay-value {
  font-size: 14px;
  font-weight: 700;
  color: #00d4ff;
  font-family: 'Courier New', monospace;
}

.hint-text {
  font-size: 10px;
  color: #555;
  background: rgba(13, 13, 26, 0.6);
  padding: 4px 8px;
  border-radius: 4px;
}

.device-detail-card {
  background: rgba(13, 13, 26, 0.92);
  border: 1px solid #2a2a4e;
  border-radius: 8px;
  padding: 10px 14px;
  min-width: 180px;
  max-width: 240px;
  backdrop-filter: blur(8px);
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #2a2a4e;
}

.detail-title {
  font-size: 13px;
  font-weight: 600;
  color: #00d4ff;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  padding: 2px 0;
}

.detail-key {
  color: #666;
}

.detail-val {
  color: #ccc;
  font-family: 'Courier New', monospace;
}

.loading-overlay {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #0d0d1a;
  color: #666;
  gap: 12px;
  z-index: 50;
}

.loading-icon {
  animation: spin 1.5s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
