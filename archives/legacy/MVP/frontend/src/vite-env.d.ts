/// <reference types="vite/client" />

declare module '*.css?inline' {
  const content: string
  export default content
}

declare module '*.css?raw' {
  const content: string
  export default content
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

declare module 'node:fs' {
  export function readFileSync(path: string | URL, encoding: string): string
}

declare module 'node:url' {
  export function fileURLToPath(url: string | URL): string
}

declare module 'node:path' {
  export function resolve(...paths: string[]): string
  export function dirname(path: string): string
}
