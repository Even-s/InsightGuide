import type { Slide } from '@/types/presentation'

interface SlidePreviewProps {
  slide: Slide | null
}

export default function SlidePreview({ slide }: SlidePreviewProps) {
  if (!slide) {
    return (
      <section className="flex h-full min-h-0 items-center justify-center rounded border border-gray-200 bg-white">
        <p className="text-sm text-gray-500">請選擇段落</p>
      </section>
    )
  }

  return (
    <section className="flex h-full min-h-0 flex-col rounded border border-gray-200 bg-white">
      <div className="flex shrink-0 items-center justify-between border-b border-gray-200 px-4 py-3">
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold text-gray-950">
            {slide.title || `段落 ${slide.pageNumber}`}
          </h2>
          <p className="text-xs text-gray-500">段落預覽</p>
        </div>
        <span className="rounded bg-gray-100 px-2 py-1 text-xs font-medium text-gray-600">
          {slide.pageNumber}
        </span>
      </div>

      <div className="flex min-h-0 flex-1 items-center justify-center bg-gray-100 p-6">
        {slide.imageUrl ? (
          <img
            src={slide.imageUrl}
            alt={`Slide ${slide.pageNumber}`}
            className="h-full w-full rounded border border-gray-200 bg-white object-contain shadow-lg"
          />
        ) : (
          <div className="flex aspect-video w-full max-w-3xl items-center justify-center rounded border border-dashed border-gray-300 bg-white p-8 text-center">
            <div>
              <p className="text-lg font-semibold text-gray-800">
                {slide.title || `段落 ${slide.pageNumber}`}
              </p>
              <p className="mt-3 max-h-48 overflow-hidden whitespace-pre-wrap text-sm leading-6 text-gray-600">
                {slide.extractedText || slide.aiSummary || '尚未產生段落預覽'}
              </p>
            </div>
          </div>
        )}
      </div>

      {(slide.aiSummary || slide.extractedText) && (
        <div className="max-h-32 shrink-0 overflow-y-auto border-t border-gray-200 bg-gray-50 px-4 py-3">
          <p className="text-xs font-medium text-gray-600">AI 摘要 / 擷取文字</p>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
            {slide.aiSummary || slide.extractedText}
          </p>
        </div>
      )}
    </section>
  )
}
