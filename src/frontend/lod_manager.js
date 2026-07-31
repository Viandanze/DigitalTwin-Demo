/**
 * lod_manager.js
 * Three.js LOD (Level of Detail) Manager
 * Week19 Day1 — Automatic model precision switching based on camera distance
 *
 * Features:
 *  - Three-tier LOD: HIGH / MEDIUM / LOW
 *  - Works with InstancedMesh and individual Mesh objects
 *  - Distance-based + screen-size-based hybrid culling
 *  - Hysteresis band to prevent flickering at LOD boundaries
 *  - Performance target: 1000 devices @ >= 30fps
 *
 * Usage:
 *   import LODManager from './lod_manager.js';
 *   const lod = new LODManager(camera, renderer);
 *   lod.registerDevice(deviceMesh, { high: highGeo, medium: medGeo, low: lowGeo });
 *   // Call in animation loop:
 *   lod.update(cameraPosition);
 */

// ==================== LOD Level Definitions ====================

const LOD_LEVEL = {
  HIGH: 0,    // Full detail — close range
  MEDIUM: 1,  // Reduced detail — mid range
  LOW: 2,     // Minimal detail — far range
  HIDDEN: 3,  // Not rendered at all
};

// Default distance thresholds (in world units)
const DEFAULT_THRESHOLDS = {
  high: 25,      // Within this distance -> HIGH
  medium: 60,    // Within this distance -> MEDIUM
  low: 120,      // Within this distance -> LOW
  // Beyond low -> HIDDEN
};

// Hysteresis margin to prevent LOD flickering (percentage of threshold)
const HYSTERESIS = 0.1;

// ==================== LOD Manager Class ====================

class LODManager {
  /**
   * @param {THREE.Camera} camera - The active camera
   * @param {THREE.WebGLRenderer} renderer - The WebGL renderer
   * @param {Object} options - Configuration options
   */
  constructor(camera, renderer, options = {}) {
    this.camera = camera;
    this.renderer = renderer;

    // Distance thresholds (customizable)
    this.thresholds = { ...DEFAULT_THRESHOLDS, ...options.thresholds };

    // Registered LOD entries
    // Each entry: { object, geometries: {high, medium, low}, currentLevel, position, type }
    this.entries = [];

    // InstancedMesh entries (special handling)
    // Each entry: { mesh, deviceData: [{position, index, currentLevel}], geometries }
    this.instancedEntries = [];

    // Performance stats
    this.stats = {
      totalObjects: 0,
      highCount: 0,
      mediumCount: 0,
      lowCount: 0,
      hiddenCount: 0,
      switches: 0,       // Total LOD switches this frame
      totalSwitches: 0,  // Cumulative switches
      updateTime: 0,     // Last update time in ms
    };

    // Update throttling (don't update every frame for performance)
    this.updateInterval = options.updateInterval || 3; // every N frames
    this._frameCounter = 0;

    // Temp vectors (reused to avoid GC pressure)
    this._tmpVec = new THREE.Vector3();
    this._tmpMatrix = new THREE.Matrix4();

    // Callback when LOD level changes
    this.onLevelChange = null;

    // Screen-size-based LOD (optional, more accurate but more expensive)
    this.useScreenSizeLod = options.useScreenSizeLod || false;
    this.screenSizeThresholds = {
      high: 0.15,   // > 15% of screen height -> HIGH
      medium: 0.05, // > 5% -> MEDIUM
      low: 0.01,    // > 1% -> LOW
    };

    console.log('[LODManager] Initialized with thresholds:', this.thresholds);
  }

  // ==================== Registration ====================

  /**
   * Register an individual mesh for LOD management
   * @param {THREE.Mesh} mesh - The mesh to manage
   * @param {Object} geometries - { high: THREE.BufferGeometry, medium: ..., low: ... }
   * @param {Object} metadata - Additional device info { id, type, isCritical }
   */
  registerMesh(mesh, geometries, metadata = {}) {
    const entry = {
      object: mesh,
      geometries: geometries,
      currentLevel: LOD_LEVEL.HIGH,
      position: mesh.position.clone(),
      id: metadata.id || mesh.uuid,
      type: metadata.type || 'unknown',
      isCritical: metadata.isCritical || false,
      // Hysteresis tracking
      _hysteresisLevel: LOD_LEVEL.HIGH,
    };

    // Set initial geometry to high
    mesh.geometry = geometries.high;

    this.entries.push(entry);
    this.stats.totalObjects++;
    return entry;
  }

  /**
   * Register an InstancedMesh for LOD management
   * Uses multiple InstancedMesh objects (one per LOD level) and swaps visibility
   *
   * @param {Object} lodMeshes - { high: InstancedMesh, medium: InstancedMesh, low: InstancedMesh }
   * @param {Array} deviceData - [{ position: {x,y,z}, index, id, type, isCritical }]
   * @param {Object} metadata - Group metadata
   */
  registerInstancedMesh(lodMeshes, deviceData, metadata = {}) {
    const entry = {
      meshes: {
        [LOD_LEVEL.HIGH]: lodMeshes.high,
        [LOD_LEVEL.MEDIUM]: lodMeshes.medium,
        [LOD_LEVEL.LOW]: lodMeshes.low,
      },
      deviceData: deviceData.map((d) => ({
        position: new THREE.Vector3(d.position.x, d.position.y, d.position.z),
        index: d.index,
        id: d.id,
        type: d.type || 'unknown',
        isCritical: d.isCritical || false,
        currentLevel: LOD_LEVEL.HIGH,
      })),
      type: metadata.type || 'unknown',
      // Track which level each InstancedMesh is currently active
      activeLevels: new Set([LOD_LEVEL.HIGH]),
    };

    // Initially show only high-detail mesh
    lodMeshes.medium.visible = false;
    lodMeshes.low.visible = false;
    lodMeshes.high.visible = true;

    this.instancedEntries.push(entry);
    this.stats.totalObjects += deviceData.length;
    return entry;
  }

  /**
   * Unregister a mesh or instanced group
   * @param {string} id - Entry ID to remove
   */
  unregister(id) {
    this.entries = this.entries.filter((e) => e.id !== id);
    // For instanced, search by group metadata
    this.instancedEntries = this.instancedEntries.filter((e) =>
      !e.deviceData.some((d) => d.id === id)
    );
    this.stats.totalObjects = this.entries.length +
      this.instancedEntries.reduce((sum, e) => sum + e.deviceData.length, 0);
  }

  // ==================== LOD Update Logic ====================

  /**
   * Main update method — call this in the animation loop
   * @param {THREE.Vector3} cameraPosition - Current camera world position
   */
  update(cameraPosition) {
    this._frameCounter++;
    if (this._frameCounter < this.updateInterval) return;

    this._frameCounter = 0;
    const startTime = performance.now();
    this.stats.switches = 0;
    this.stats.highCount = 0;
    this.stats.mediumCount = 0;
    this.stats.lowCount = 0;
    this.stats.hiddenCount = 0;

    // Update individual meshes
    this._updateIndividualMeshes(cameraPosition);

    // Update instanced meshes
    this._updateInstancedMeshes(cameraPosition);

    // Update timing stats
    this.stats.updateTime = performance.now() - startTime;
    this.stats.totalSwitches += this.stats.switches;
  }

  /**
   * Update LOD for individual mesh entries
   */
  _updateIndividualMeshes(cameraPosition) {
    for (const entry of this.entries) {
      const distance = cameraPosition.distanceTo(entry.position);
      const newLevel = this._computeLODLevel(distance, entry);

      if (newLevel !== entry.currentLevel) {
        this._applyLODMesh(entry, newLevel);
        entry.currentLevel = newLevel;
        this.stats.switches++;

        if (this.onLevelChange) {
          this.onLevelChange(entry.id, newLevel, distance);
        }
      }

      this._incrementLevelStat(entry.currentLevel);
    }
  }

  /**
   * Update LOD for instanced mesh entries
   * Strategy: Group devices by their LOD level, then rebuild instance matrices
   * for each LOD mesh to only include devices at that level
   */
  _updateInstancedMeshes(cameraPosition) {
    for (const entry of this.instancedEntries) {
      // Group devices by target LOD level
      const levelGroups = {
        [LOD_LEVEL.HIGH]: [],
        [LOD_LEVEL.MEDIUM]: [],
        [LOD_LEVEL.LOW]: [],
        [LOD_LEVEL.HIDDEN]: [],
      };

      for (const device of entry.deviceData) {
        const distance = cameraPosition.distanceTo(device.position);
        const newLevel = this._computeLODLevel(distance, device);

        if (newLevel !== device.currentLevel) {
          device.currentLevel = newLevel;
          this.stats.switches++;
        }

        levelGroups[newLevel].push(device);
      }

      // Rebuild instance matrices for each LOD level
      const dummy = new THREE.Object3D();

      for (const level of [LOD_LEVEL.HIGH, LOD_LEVEL.MEDIUM, LOD_LEVEL.LOW]) {
        const mesh = entry.meshes[level];
        const devices = levelGroups[level];

        if (devices.length === 0) {
          mesh.visible = false;
          mesh.count = 0;
          continue;
        }

        mesh.visible = true;
        mesh.count = devices.length;

        for (let i = 0; i < devices.length; i++) {
          const pos = devices[i].position;
          dummy.position.copy(pos);
          dummy.scale.set(1, 1, 1);
          dummy.rotation.set(0, 0, 0);
          dummy.updateMatrix();
          mesh.setMatrixAt(i, dummy.matrix);
        }

        mesh.instanceMatrix.needsUpdate = true;
        this._incrementLevelStat(level, devices.length);
      }

      this.stats.hiddenCount += levelGroups[LOD_LEVEL.HIDDEN].length;
    }
  }

  /**
   * Compute the appropriate LOD level based on distance
   * Includes hysteresis to prevent flickering
   */
  _computeLODLevel(distance, entry) {
    // Critical devices always at least MEDIUM (never fully hidden unless very far)
    const isCritical = entry.isCritical;

    // Current level for hysteresis
    const currentLevel = entry.currentLevel !== undefined ? entry.currentLevel : LOD_LEVEL.HIGH;

    // Apply hysteresis: if currently at a lower LOD, require going closer to upgrade
    const highThresh = this.thresholds.high;
    const medThresh = this.thresholds.medium;
    const lowThresh = this.thresholds.low;

    // Hysteresis margins
    const highHyst = highThresh * (1 + HYSTERESIS);
    const medHyst = medThresh * (1 + HYSTERESIS);
    const lowHyst = lowThresh * (1 + HYSTERESIS);

    let newLevel;

    if (this.useScreenSizeLod) {
      newLevel = this._computeScreenSizeLOD(entry);
    } else {
      // Distance-based with hysteresis
      switch (currentLevel) {
        case LOD_LEVEL.HIGH:
          if (distance > highHyst) {
            newLevel = distance > medHyst ? LOD_LEVEL.LOW : LOD_LEVEL.MEDIUM;
          } else {
            newLevel = LOD_LEVEL.HIGH;
          }
          break;
        case LOD_LEVEL.MEDIUM:
          if (distance < highThresh * (1 - HYSTERESIS)) {
            newLevel = LOD_LEVEL.HIGH;
          } else if (distance > medHyst) {
            newLevel = LOD_LEVEL.LOW;
          } else {
            newLevel = LOD_LEVEL.MEDIUM;
          }
          break;
        case LOD_LEVEL.LOW:
          if (distance < medThresh * (1 - HYSTERESIS)) {
            newLevel = distance < highThresh * (1 - HYSTERESIS) ? LOD_LEVEL.HIGH : LOD_LEVEL.MEDIUM;
          } else if (distance > lowHyst && !isCritical) {
            newLevel = LOD_LEVEL.HIDDEN;
          } else {
            newLevel = LOD_LEVEL.LOW;
          }
          break;
        case LOD_LEVEL.HIDDEN:
          if (distance < lowThresh * (1 - HYSTERESIS)) {
            newLevel = distance < medThresh * (1 - HYSTERESIS)
              ? (distance < highThresh * (1 - HYSTERESIS) ? LOD_LEVEL.HIGH : LOD_LEVEL.MEDIUM)
              : LOD_LEVEL.LOW;
          } else {
            newLevel = LOD_LEVEL.HIDDEN;
          }
          break;
        default:
          newLevel = LOD_LEVEL.HIGH;
      }
    }

    // Critical devices: never hide, minimum LOW
    if (isCritical && newLevel === LOD_LEVEL.HIDDEN) {
      newLevel = LOD_LEVEL.LOW;
    }

    return newLevel;
  }

  /**
   * Compute LOD based on projected screen size (more accurate, more expensive)
   */
  _computeScreenSizeLOD(entry) {
    const pos = entry.position || entry.position;
    this._tmpVec.copy(pos);
    this._tmpVec.project(this.camera);

    // If behind camera, hide
    if (this._tmpVec.z > 1) return LOD_LEVEL.HIDDEN;

    // Compute screen-space size (approximate using bounding sphere radius)
    const radius = entry.object ? this._getBoundingRadius(entry.object) : 0.5;
    const distance = this.camera.position.distanceTo(pos);
    const screenRadius = radius / (distance * Math.tan((this.camera.fov * Math.PI / 180) / 2));
    const screenRatio = screenRadius * 2; // Diameter as fraction of screen height

    if (screenRatio > this.screenSizeThresholds.high) return LOD_LEVEL.HIGH;
    if (screenRatio > this.screenSizeThresholds.medium) return LOD_LEVEL.MEDIUM;
    if (screenRatio > this.screenSizeThresholds.low) return LOD_LEVEL.LOW;
    return LOD_LEVEL.HIDDEN;
  }

  /**
   * Get approximate bounding radius of a mesh
   */
  _getBoundingRadius(mesh) {
    if (!mesh.geometry.boundingSphere) {
      mesh.geometry.computeBoundingSphere();
    }
    return mesh.geometry.boundingSphere ? mesh.geometry.boundingSphere.radius : 0.5;
  }

  /**
   * Apply LOD geometry swap to an individual mesh entry
   */
  _applyLODMesh(entry, level) {
    const mesh = entry.object;

    switch (level) {
      case LOD_LEVEL.HIGH:
        mesh.geometry = entry.geometries.high;
        mesh.visible = true;
        break;
      case LOD_LEVEL.MEDIUM:
        mesh.geometry = entry.geometries.medium;
        mesh.visible = true;
        break;
      case LOD_LEVEL.LOW:
        mesh.geometry = entry.geometries.low;
        mesh.visible = true;
        break;
      case LOD_LEVEL.HIDDEN:
        mesh.visible = false;
        break;
    }
  }

  /**
   * Increment level statistics
   */
  _incrementLevelStat(level, count = 1) {
    switch (level) {
      case LOD_LEVEL.HIGH: this.stats.highCount += count; break;
      case LOD_LEVEL.MEDIUM: this.stats.mediumCount += count; break;
      case LOD_LEVEL.LOW: this.stats.lowCount += count; break;
      case LOD_LEVEL.HIDDEN: this.stats.hiddenCount += count; break;
    }
  }

  // ==================== Geometry Generation Helpers ====================

  /**
   * Generate three-tier LOD geometries from a base high-detail geometry
   * @param {THREE.BufferGeometry} highGeo - Original high-detail geometry
   * @returns {Object} { high, medium, low }
   */
  static generateLODGeometries(highGeo) {
    // HIGH: Use original geometry (already high detail)
    const high = highGeo;

    // MEDIUM: Simplify to ~50% of vertices
    const medium = highGeo.clone();
    medium.mergeVertices(0.02); // Merge vertices within 0.02 tolerance
    if (medium.index) {
      // Simple decimation: remove every other triangle
      const index = medium.index.array;
      const newIndex = [];
      for (let i = 0; i < index.length; i += 6) {
        // Keep first triangle, skip second
        newIndex.push(index[i], index[i + 1], index[i + 2]);
      }
      medium.setIndex(newIndex);
    }

    // LOW: Simplify to ~20% of vertices (or use bounding box)
    const low = new THREE.BoxGeometry(
      highGeo.boundingBox ? (highGeo.boundingBox.max.x - highGeo.boundingBox.min.x) : 1,
      highGeo.boundingBox ? (highGeo.boundingBox.max.y - highGeo.boundingBox.min.y) : 1,
      highGeo.boundingBox ? (highGeo.boundingBox.max.z - highGeo.boundingBox.min.z) : 1
    );

    // Ensure bounding data is computed
    high.computeBoundingBox();
    high.computeBoundingSphere();
    medium.computeBoundingBox();
    medium.computeBoundingSphere();
    low.computeBoundingBox();
    low.computeBoundingSphere();

    return { high, medium, low };
  }

  /**
   * Generate LOD geometries for common device types
   * @param {string} type - Device type (sensor, motor, controller)
   * @returns {Object} { high, medium, low }
   */
  static generateDeviceLOD(type) {
    switch (type) {
      case 'sensor':
        return {
          high: new THREE.BoxGeometry(0.4, 0.3, 0.4, 2, 2, 2),
          medium: new THREE.BoxGeometry(0.4, 0.3, 0.4),
          low: new THREE.BoxGeometry(0.4, 0.3, 0.4),
        };
      case 'motor':
        return {
          high: new THREE.CylinderGeometry(0.25, 0.3, 0.8, 32),
          medium: new THREE.CylinderGeometry(0.25, 0.3, 0.8, 12),
          low: new THREE.CylinderGeometry(0.25, 0.3, 0.8, 6),
        };
      case 'controller':
        return {
          high: new THREE.BoxGeometry(0.6, 1.0, 0.6, 3, 4, 3),
          medium: new THREE.BoxGeometry(0.6, 1.0, 0.6, 1, 2, 1),
          low: new THREE.BoxGeometry(0.6, 1.0, 0.6),
        };
      default:
        return {
          high: new THREE.BoxGeometry(0.5, 0.5, 0.5, 2, 2, 2),
          medium: new THREE.BoxGeometry(0.5, 0.5, 0.5),
          low: new THREE.BoxGeometry(0.5, 0.5, 0.5),
        };
    }
  }

  // ==================== Utility Methods ====================

  /**
   * Set custom distance thresholds
   * @param {Object} thresholds - { high, medium, low }
   */
  setThresholds(thresholds) {
    this.thresholds = { ...this.thresholds, ...thresholds };
    console.log('[LODManager] Thresholds updated:', this.thresholds);
  }

  /**
   * Get current performance statistics
   * @returns {Object} Stats object
   */
  getStats() {
    return { ...this.stats };
  }

  /**
   * Get a human-readable summary of LOD distribution
   */
  getSummary() {
    const s = this.stats;
    return {
      total: s.totalObjects,
      distribution: {
        high: `${s.highCount} (${((s.highCount / s.totalObjects) * 100).toFixed(1)}%)`,
        medium: `${s.mediumCount} (${((s.mediumCount / s.totalObjects) * 100).toFixed(1)}%)`,
        low: `${s.lowCount} (${((s.lowCount / s.totalObjects) * 100).toFixed(1)}%)`,
        hidden: `${s.hiddenCount} (${((s.hiddenCount / s.totalObjects) * 100).toFixed(1)}%)`,
      },
      switchesThisFrame: s.switches,
      totalSwitches: s.totalSwitches,
      updateTimeMs: s.updateTime.toFixed(2),
    };
  }

  /**
   * Force all entries to a specific LOD level (useful for debugging)
   * @param {number} level - LOD_LEVEL value
   */
  forceLODLevel(level) {
    for (const entry of this.entries) {
      this._applyLODMesh(entry, level);
      entry.currentLevel = level;
    }
    console.log(`[LODManager] Forced all ${this.entries.length} meshes to level ${level}`);
  }

  /**
   * Dispose all resources
   */
  dispose() {
    this.entries = [];
    this.instancedEntries = [];
    this.stats = {
      totalObjects: 0, highCount: 0, mediumCount: 0,
      lowCount: 0, hiddenCount: 0, switches: 0,
      totalSwitches: 0, updateTime: 0,
    };
    console.log('[LODManager] Disposed');
  }
}

// ==================== Export ====================

export { LODManager, LOD_LEVEL };
export default LODManager;
