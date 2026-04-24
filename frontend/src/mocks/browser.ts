import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'

// Export as `worker` — Plan 09 main.tsx does:
//   const { worker } = await import('./mocks/browser')
//   await worker.start({ onUnhandledRequest: 'bypass' })
export const worker = setupWorker(...handlers)
