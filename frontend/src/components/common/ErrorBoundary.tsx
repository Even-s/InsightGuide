import { Component, type ReactNode, type ErrorInfo } from 'react'
import Button from './Button'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    }
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return {
      hasError: true,
      error,
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
    this.setState({
      error,
      errorInfo,
    })
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="flex min-h-screen items-center justify-center bg-cream-100 p-6">
          <div className="w-full max-w-2xl rounded-lg border border-red-200 bg-white p-8 shadow-lg">
            <div className="mb-4 flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
                <svg className="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-natural-700">發生錯誤</h1>
                <p className="text-sm text-natural-400">應用程式遇到意外錯誤</p>
              </div>
            </div>

            <div className="mb-6">
              <div className="rounded-lg bg-red-50 p-4">
                <p className="mb-2 font-semibold text-red-900">錯誤訊息：</p>
                <p className="font-mono text-sm text-red-800">
                  {this.state.error?.message || '未知錯誤'}
                </p>
              </div>

              {import.meta.env.DEV && this.state.errorInfo && (
                <details className="mt-4">
                  <summary className="cursor-pointer text-sm font-medium text-natural-600 hover:text-natural-700">
                    顯示詳細錯誤資訊
                  </summary>
                  <div className="mt-2 rounded-lg bg-cream-200 p-4">
                    <pre className="overflow-auto text-xs text-natural-700">
                      {this.state.error?.stack}
                    </pre>
                    <pre className="mt-2 overflow-auto text-xs text-natural-500">
                      {this.state.errorInfo.componentStack}
                    </pre>
                  </div>
                </details>
              )}
            </div>

            <div className="flex gap-3">
              <Button onClick={this.handleReset}>
                重試
              </Button>
              <Button variant="secondary" onClick={() => window.location.reload()}>
                重新載入頁面
              </Button>
              <Button variant="ghost" onClick={() => window.history.back()}>
                返回
              </Button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
