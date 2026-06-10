import { useEffect } from 'react'
import { createPortal } from 'react-dom'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  children: React.ReactNode
  title?: string
}

export default function Modal({ isOpen, onClose, children, title }: ModalProps) {
  // ESC 鍵關閉
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
      // 禁止背景滾動
      document.body.style.overflow = 'hidden'
    }

    return () => {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = 'unset'
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* 背景遮罩 */}
      <div
        className="absolute inset-0 bg-natural-800/40 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Modal 內容 */}
      <div className="relative w-full max-w-2xl max-h-[90vh] flex flex-col bg-cream-50 rounded-2xl shadow-natural-lg border border-cream-300 overflow-hidden">
        {/* 標題列 */}
        {title && (
          <div className="shrink-0 flex items-center justify-between px-6 py-4 border-b border-cream-300 bg-wood-50">
            <h2 className="text-xl font-medium text-natural-700 tracking-wide leading-relaxed">
              {title}
            </h2>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-cream-100 transition-colors"
              aria-label="關閉"
            >
              <svg className="w-5 h-5 text-natural-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* 內容區 */}
        <div className="flex-1 overflow-y-auto p-6">
          {children}
        </div>
      </div>
    </div>,
    document.body
  )
}
