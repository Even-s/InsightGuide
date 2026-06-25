import '@testing-library/jest-dom'

class MockEventSource {
  url: string
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onopen: ((event: Event) => void) | null = null
  readyState = 0
  constructor(url: string) {
    this.url = url
  }
  close() {}
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() { return false }
}

globalThis.EventSource = MockEventSource as unknown as typeof EventSource
