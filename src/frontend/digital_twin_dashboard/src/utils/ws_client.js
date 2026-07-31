/**
 * ws_client.js — WebSocket Client for Digital Twin Dashboard
 * Handles real-time data communication with the backend
 *
 * Features:
 *  - Auto-reconnect with exponential backoff (delegated to ws_reconnect.js)
 *  - Heartbeat ping/pong for connection health monitoring
 *  - Message queuing during disconnection
 *  - Event-based message handling (snapshot, sensor_update, status_update)
 *  - Room subscription support
 *
 * Usage:
 *   import { createWSClient } from './ws_client.js'
 *   const ws = createWSClient('ws://localhost:8000/ws/client1', {
 *     onMessage: (msg) => console.log(msg),
 *     onConnect: () => console.log('connected'),
 *     onDisconnect: () => console.log('disconnected'),
 *     autoReconnect: true,
 *     heartbeatInterval: 10000
 *   })
 *   ws.connect()
 *   ws.send({ type: 'subscribe', room: 'lab_a' })
 */

import { ReconnectManager } from './ws_reconnect.js'

/**
 * Create a WebSocket client instance
 * @param {string} url - WebSocket URL
 * @param {Object} options - Configuration options
 * @param {Function} options.onMessage - Called when a message is received
 * @param {Function} options.onConnect - Called when connection is established
 * @param {Function} options.onDisconnect - Called when connection is lost
 * @param {Function} options.onError - Called on WebSocket error
 * @param {boolean} options.autoReconnect - Enable auto-reconnect (default: true)
 * @param {number} options.reconnectInterval - Initial reconnect delay (default: 2000ms)
 * @param {number} options.maxReconnectInterval - Max reconnect delay (default: 10000ms)
 * @param {number} options.heartbeatInterval - Heartbeat interval (default: 10000ms)
 * @param {number} options.messageQueueLimit - Max queued messages (default: 100)
 * @returns {Object} WebSocket client API
 */
export function createWSClient(url, options = {}) {
  const config = {
    onMessage: options.onMessage || (() => {}),
    onConnect: options.onConnect || (() => {}),
    onDisconnect: options.onDisconnect || (() => {}),
    onError: options.onError || (() => {}),
    autoReconnect: options.autoReconnect !== false,
    reconnectInterval: options.reconnectInterval || 2000,
    maxReconnectInterval: options.maxReconnectInterval || 10000,
    heartbeatInterval: options.heartbeatInterval || 10000,
    messageQueueLimit: options.messageQueueLimit || 100
  }

  let ws = null
  let isConnected = false
  let isManualClose = false
  let heartbeatTimer = null
  let reconnectManager = null
  let messageQueue = []
  let reconnectAttempts = 0

  // ==================== Connection ====================

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    isManualClose = false
    console.log(`[WSClient] Connecting to ${url}...`)

    try {
      ws = new WebSocket(url)
    } catch (err) {
      console.error('[WSClient] Failed to create WebSocket:', err)
      _handleDisconnect()
      return
    }

    ws.onopen = () => {
      isConnected = true
      reconnectAttempts = 0
      console.log('[WSClient] Connected')

      // Start heartbeat
      _startHeartbeat()

      // Flush queued messages
      _flushQueue()

      // Notify connection
      config.onConnect()

      // Auto-reconnect manager reset
      if (reconnectManager) reconnectManager.reset()
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        config.onMessage(data)
      } catch (err) {
        console.error('[WSClient] Failed to parse message:', err, event.data)
      }
    }

    ws.onerror = (event) => {
      console.error('[WSClient] WebSocket error:', event)
      config.onError(event)
    }

    ws.onclose = (event) => {
      console.log(`[WSClient] Connection closed: code=${event.code}, reason=${event.reason}`)
      _handleDisconnect()
    }
  }

  function disconnect() {
    isManualClose = true
    _stopHeartbeat()
    if (reconnectManager) reconnectManager.stop()

    if (ws) {
      ws.onclose = null // Prevent auto-reconnect on manual close
      ws.close(1000, 'Manual disconnect')
      ws = null
    }
    isConnected = false
    console.log('[WSClient] Disconnected (manual)')
  }

  // ==================== Message Sending ====================

  /**
   * Send a message to the server
   * If not connected, the message will be queued
   * @param {Object} message - Message object (will be JSON.stringify'd)
   * @param {boolean} queueIfDisconnected - Queue if not connected (default: true)
   * @returns {boolean} Whether the message was sent immediately
   */
  function send(message, queueIfDisconnected = true) {
    if (isConnected && ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify(message))
        return true
      } catch (err) {
        console.error('[WSClient] Failed to send message:', err)
        return false
      }
    } else if (queueIfDisconnected) {
      if (messageQueue.length >= config.messageQueueLimit) {
        messageQueue.shift() // Drop oldest message
      }
      messageQueue.push(message)
      console.log(`[WSClient] Message queued (${messageQueue.length} pending)`)
      return false
    }
    return false
  }

  /**
   * Subscribe to a room/channel
   * @param {string} room - Room name
   */
  function subscribe(room) {
    send({ type: 'subscribe', room })
  }

  /**
   * Unsubscribe from a room/channel
   * @param {string} room - Room name
   */
  function unsubscribe(room) {
    send({ type: 'unsubscribe', room })
  }

  /**
   * Request a device snapshot from the server
   */
  function requestSnapshot() {
    send({ type: 'request_snapshot' })
  }

  /**
   * Send a device control command
   * @param {string} deviceId - Target device ID
   * @param {Object} command - Command payload
   */
  function sendCommand(deviceId, command) {
    send({ type: 'command', device_id: deviceId, command })
  }

  // ==================== Heartbeat ====================

  function _startHeartbeat() {
    _stopHeartbeat()
    heartbeatTimer = setInterval(() => {
      if (isConnected) {
        send({ type: 'ping', timestamp: Date.now() })
      }
    }, config.heartbeatInterval)
  }

  function _stopHeartbeat() {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  // ==================== Reconnection ====================

  function _handleDisconnect() {
    const wasConnected = isConnected
    isConnected = false
    _stopHeartbeat()

    if (wasConnected) {
      config.onDisconnect()
    }

    if (config.autoReconnect && !isManualClose) {
      if (!reconnectManager) {
        reconnectManager = new ReconnectManager({
          initialDelay: config.reconnectInterval,
          maxDelay: config.maxReconnectInterval,
          onReconnect: () => {
            reconnectAttempts++
            console.log(`[WSClient] Reconnect attempt #${reconnectAttempts}`)
            connect()
          },
          onMaxRetries: () => {
            console.error('[WSClient] Max reconnect attempts reached. Giving up.')
          }
        })
      }
      reconnectManager.start()
    }
  }

  // ==================== Message Queue ====================

  function _flushQueue() {
    if (messageQueue.length === 0) return
    console.log(`[WSClient] Flushing ${messageQueue.length} queued messages`)
    while (messageQueue.length > 0) {
      const msg = messageQueue.shift()
      send(msg, false) // Don't re-queue during flush
    }
  }

  // ==================== Public API ====================

  return {
    connect,
    disconnect,
    send,
    subscribe,
    unsubscribe,
    requestSnapshot,
    sendCommand,
    // State accessors
    get connected() { return isConnected },
    get readyState() { return ws ? ws.readyState : WebSocket.CLOSED },
    get queuedMessages() { return messageQueue.length },
    get reconnectAttempts() { return reconnectAttempts }
  }
}

export default { createWSClient }
