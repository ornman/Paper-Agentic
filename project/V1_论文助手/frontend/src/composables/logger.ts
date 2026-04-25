/**
 * 前端日志模块 — 自动上报到 .tools/log/server.py
 */

const LOG_SERVER = 'http://127.0.0.1:3895'

export type LogModule = 'wps' | 'api' | 'ui' | 'general'

interface LogEntry {
  module: LogModule
  level: 'debug' | 'info' | 'warn' | 'error'
  message: string
  timestamp: string
  stack?: string
}

const queue: LogEntry[] = []
let flushTimer: ReturnType<typeof setTimeout> | null = null

function stringifyArg(arg: unknown): string {
  if (arg instanceof Error) {
    return arg.message
  }

  if (typeof arg === 'string') {
    return arg
  }

  if (arg === undefined) {
    return 'undefined'
  }

  if (arg === null) {
    return 'null'
  }

  if (typeof arg === 'object') {
    try {
      return JSON.stringify(arg)
    } catch {
      return '[object]'
    }
  }

  return String(arg)
}

function formatMessage(message: string, args: unknown[]): string {
  const suffix = args.map(stringifyArg).filter(Boolean).join(' ')
  return suffix ? `${message} ${suffix}` : message
}

function flush() {
  if (queue.length === 0) return

  const batch = queue.splice(0)
  for (const entry of batch) {
    try {
      navigator.sendBeacon?.(`${LOG_SERVER}/log`, JSON.stringify(entry))
    } catch {
      fetch(`${LOG_SERVER}/log`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entry),
        keepalive: true,
      }).catch(() => {})
    }
  }

  flushTimer = null
}

function enqueue(entry: Omit<LogEntry, 'timestamp'>) {
  queue.push({
    ...entry,
    timestamp: new Date().toISOString(),
  })

  if (!flushTimer) {
    flushTimer = setTimeout(flush, 300)
  }
}

function createLogger(module: LogModule) {
  const prefix = `[${module}]`

  return {
    debug(message: string, ...args: unknown[]) {
      console.debug(prefix, message, ...args)
    },

    info(message: string, ...args: unknown[]) {
      const fullMessage = formatMessage(message, args)
      console.info(prefix, fullMessage)
      enqueue({ module, level: 'info', message: fullMessage })
    },

    warn(message: string, ...args: unknown[]) {
      const fullMessage = formatMessage(message, args)
      console.warn(prefix, fullMessage)
      enqueue({ module, level: 'warn', message: fullMessage })
    },

    error(message: string, error?: unknown, ...args: unknown[]) {
      const fullMessage = formatMessage(message, [error, ...args].filter((item) => item !== undefined))
      console.error(prefix, fullMessage, error)
      enqueue({
        module,
        level: 'error',
        message: fullMessage,
        stack: error instanceof Error ? error.stack : undefined,
      })
    },
  }
}

export const useLogger = createLogger

export function setupGlobalErrorCapture() {
  if (typeof window === 'undefined') return

  window.addEventListener('error', (event) => {
    enqueue({
      module: 'general',
      level: 'error',
      message: `Uncaught: ${event.message} at ${event.filename}:${event.lineno}:${event.colno}`,
    })
  })

  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason
    const message = reason instanceof Error
      ? `Unhandled rejection: ${reason.message}`
      : `Unhandled rejection: ${stringifyArg(reason)}`

    enqueue({
      module: 'general',
      level: 'error',
      message,
      stack: reason instanceof Error ? reason.stack : undefined,
    })
  })
}
