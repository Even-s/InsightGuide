import { useState } from 'react'
import type { Slide } from '@/types/presentation'
import Button from '@/components/common/Button'

interface SlideViewerProps {
  slide: Slide | null
  currentSlideIndex: number
  totalSlides: number
  onPrevious: () => void
  onNext: () => void
  onOrientationChange?: (orientation: 'landscape' | 'portrait' | 'unknown') => void
}

export default function SlideViewer({
  slide,
  currentSlideIndex,
  totalSlides,
  onPrevious,
  onNext,
  onOrientationChange,
}: SlideViewerProps) {
  const [imageOrientation, setImageOrientation] = useState<'landscape' | 'portrait' | 'unknown'>('unknown')

  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget
    const aspectRatio = img.naturalWidth / img.naturalHeight

    // 判断方向：aspect ratio > 1 为横向，< 1 为直向
    const orientation = aspectRatio > 1 ? 'landscape' : 'portrait'
    setImageOrientation(orientation)
    onOrientationChange?.(orientation)
  }

  if (!slide) {
    return (
      <section className="flex h-full items-center justify-center rounded border border-gray-200 bg-white">
        <p className="text-gray-500">沒有投影片資料</p>
      </section>
    )
  }

  // 根据图片方向决定布局
  const isPortrait = imageOrientation === 'portrait'

  return (
    <section className="flex h-full min-h-0 flex-col">
      <div className="group relative flex min-h-0 flex-1 items-center justify-center overflow-hidden rounded border border-gray-200 bg-white">
        {slide.imageUrl ? (
          <img
            src={slide.imageUrl}
            alt={`Slide ${slide.pageNumber}`}
            className={`transition-all duration-300 ${
              isPortrait
                ? 'h-full w-auto max-w-[70%]' // 直向：限制最大宽度为70%，高度优先
                : 'h-full w-full object-contain' // 横向：标准显示
            }`}
            onLoad={handleImageLoad}
          />
        ) : (
          <div className="max-w-3xl px-8 text-center">
            <p className="mb-4 text-2xl font-semibold text-gray-900">
              {slide.title || `投影片 ${slide.pageNumber}`}
            </p>
            <p className="whitespace-pre-wrap text-gray-600">
              {slide.aiSummary || slide.extractedText || '等待投影片影像或文字內容'}
            </p>
          </div>
        )}

        <button
          type="button"
          onClick={onPrevious}
          disabled={currentSlideIndex === 0}
          aria-label="上一頁"
          className="absolute left-4 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-gray-950/70 text-white opacity-0 transition-opacity hover:bg-gray-950 disabled:cursor-not-allowed disabled:opacity-20 group-hover:opacity-100"
        >
          <ChevronLeftIcon className="h-6 w-6" />
        </button>
        <button
          type="button"
          onClick={onNext}
          disabled={currentSlideIndex >= totalSlides - 1}
          aria-label="下一頁"
          className="absolute right-4 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-gray-950/70 text-white opacity-0 transition-opacity hover:bg-gray-950 disabled:cursor-not-allowed disabled:opacity-20 group-hover:opacity-100"
        >
          <ChevronRightIcon className="h-6 w-6" />
        </button>
      </div>

      <div className="mt-4 flex shrink-0 flex-col gap-4">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-gray-900">
              {slide.title || `投影片 ${slide.pageNumber}`}
            </h2>
          </div>

          <div className="flex shrink-0 items-center gap-3">
            <Button size="sm" variant="secondary" onClick={onPrevious} disabled={currentSlideIndex === 0}>
              上一頁
            </Button>
            <span className="min-w-16 text-center text-sm text-gray-600">
              {totalSlides > 0 ? currentSlideIndex + 1 : 0} / {totalSlides}
            </span>
            <Button size="sm" variant="secondary" onClick={onNext} disabled={currentSlideIndex >= totalSlides - 1}>
              下一頁
            </Button>
          </div>
        </div>

      </div>
    </section>
  )
}

function ChevronLeftIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
    </svg>
  )
}

function ChevronRightIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  )
}
