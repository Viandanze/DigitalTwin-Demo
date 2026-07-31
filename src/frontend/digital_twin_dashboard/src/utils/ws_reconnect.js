/**
 * ws_reconnect.js — WebSocket Auto-Reconnect Manager
 * Handles exponential backoff reconnection strategy
 *
 * Features:
 *  - Exponential backoff with jitter to prevent thundering herd
 *  - Configurable max retry limit
 *  - Reset on successful connection
 *  - Pause/resume capability
 *  - Event callbacks for reconnection lifecycle
 *
 * Usage:
 *   import { ReconnectManager } from './ws_reconnect.js'
 *   const mgr = new ReconnectManager({
 *     initialDelay: 2000,
 *     maxDelay: 30000,
 *     maxRetries: 20,
 *     onReconnect: () => ws.connect(),
 *     onMaxRetries: () => console.error('Giving up')
 *   })
 *   mgr.start()   // Begin reconnection attempts
 *   mgr.reset()   // Reset on successful connection
 *   mgr.stop()    // Stop all reconnection attempts
 */

/**
 * Reconnect Manager Class
 */
export class ReconnectManager {
  /**
   * @param {Object} options - Configuration
   * @param {number} options.initialDelay - Initial delay in ms (default: 2000)
   * @param {number} options.maxDelay - Maximum delay in ms (default: 30000)
   * @param {number} options.maxRetries - Max retry attempts, 0 = infinite (default: 0)
   * @param {number} options.backoffFactor - Multiplier for exponential backoff (default: 1.5)
   * @param {number} options.jitter - Jitter factor 0-1 (default: 0.3)
   * @param {Function} options.onReconnect - Called before each reconnect attempt
   * @param {Function} options.onMaxRetries - Called when max retries are exhausted
   * @param {Function} options.onSchedule - Called when a reconnect is scheduled (delay, attempt)
   */
  constructor(options = {}) {
    this.initialDelay = options.initialDelay || 2000
    this.maxDelay = options.maxDelay || 30000
    this.maxRetries = options.maxRetries || 0  // 0 = infinite
    this.backoffFactor = options.backoffFactor || 1.5
    this.jitter = options.jitter !== undefined ? options.jitter : 0.3
    this.onReconnect = options.onReconnect || (() => {})
    this.onMaxRetries = options.onMaxRetries || (() => {})
    this.onSchedule = options.onSchedule || (() => {})

    // Internal state
    this._currentDelay = this.initialDelay
    this._attempt = 0
    this._timer = null
    this._running = false
    this._paused = false
  }

  /**
   * Start the reconnection cycle
   */
  start() {
    if (this._running) return
    this._running = true
    this._paused = false
    this._scheduleReconnect()
  }

  /**
   * Stop all reconnection attempts
   */
  stop() {
    this._running = false
    if (this._timer) {
      clearTimeout(this._timer)
      this._timer = null
    }
  }

  /**
   * Pause reconnection (maintains state, can resume)
   */
  pause() {
    this._paused = true
    if (this._timer) {
      clearTimeout(this._timer)
      this._timer = null
    }
  }

  /**
   * Resume reconnection after pause
   */
  resume() {
    if (!this._running || !this._paused) return
    this._paused = false
    this._scheduleReconnect()
  }

  /**
   * Reset the backoff to initial state (call on successful connection)
   */
  reset() {
    this._currentDelay = this.initialDelay
    this._attempt = 0
    if (this._timer) {
      clearTimeout(this._timer)
      this._timer = null
    }
  }

  /**
   * Get current state information
   */
  getState() {
    return {
      running: this._running,
      paused: this._paused,
      attempt: this._attempt,
      currentDelay: this._currentDelay,
      maxRetries: this.maxRetries,
      willRetry: this.maxRetries === 0 || this._attempt < this.maxRetries
    }
  }

  // ==================== Internal Methods ====================

  /**
   * Schedule the next reconnection attempt with exponential backoff + jitter
   * @private
   */
  _scheduleReconnect() {
    if (!this._running || this._paused) return

    // Check max retries
    if (this.maxRetries > 0 && this._attempt >= this.maxRetries) {
      console.error(`[ReconnectManager] Max retries (${this.maxRetries}) reached`)
      this.onMaxRetries()
      this._running = false
      return
    }

    // Calculate delay with exponential backoff
    const baseDelay = Math.min(this._currentDelay, this.maxDelay)

    // Add jitter: random +/- jitter fraction of the base delay
    const jitterAmount = baseDelay * this.jitter
    const jitteredDelay = baseDelay + (Math.random() * 2 - 1) * jitterAmount
    const finalDelay = Math.max(1000, Math.round(jitteredDelay)) // Minimum 1s

    this._attempt++
    console.log(
      `[ReconnectManager] Scheduling reconnect #${this._attempt} ` +
      `in ${finalDelay}ms (base: ${baseDelay}ms, jitter: ±${jitterAmount.toFixed(0)}ms)`
    )

    this.onSchedule(finalDelay, this._attempt)

    this._timer = setTimeout(() => {
      this._timer = null
      if (!this._running || this._paused) return

      // Execute reconnect callback
      this.onReconnect()

      // Increase delay for next attempt (exponential backoff)
      this._currentDelay = Math.min(
        this._currentDelay * this.backoffFactor,
        this.maxDelay
      )

      // Note: The next _scheduleReconnect will be called by the WS client
      // if the reconnection attempt fails again (via onclose handler)
    }, finalDelay)
  }

  /**
   * Notify that a reconnection attempt failed, schedule next one
   */
  notifyFailed() {
    if (this._running && !this._paused) {
      this._scheduleReconnect()
    }
  }
}

/**
 * Create a reconnect manager with default settings
 * Convenience factory function
 */
export function createReconnectManager(options = {}) {
  return new ReconnectManager(options)
}

export default { ReconnectManager, createReconnectManager }
