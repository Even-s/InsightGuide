import type { FollowupPrompt } from './presenterUtils'

interface FollowupPromptPanelProps {
  prompt: FollowupPrompt | null
  queueLength: number
  onSkip: () => void
}

export default function FollowupPromptPanel({ prompt, queueLength, onSkip }: FollowupPromptPanelProps) {
  const promptKey = [
    prompt?.cardTitle,
    prompt?.suggestedFollowup,
  ].filter(Boolean).join('::') || 'empty'

  if (!prompt?.suggestedFollowup) return null

  return (
    <section className="absolute bottom-4 left-6 right-6 z-20" aria-live="polite">
      <div className="mx-auto max-w-5xl">
        <div className="min-w-0 rounded-2xl bg-white px-7 py-5 shadow-[0_0_20px_rgba(160,137,104,0.2),0_0_40px_rgba(160,137,104,0.1)]">
          <div className="mb-3 flex min-w-0 items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <span className="shrink-0 rounded-xl border border-wood-200 bg-wood-50 px-2.5 py-1 text-sm font-bold text-wood-500">仍需追問</span>
              {prompt.cardTitle && (
                <p key={prompt.cardTitle} className="animate-fadeIn truncate text-base font-medium text-natural-500">{prompt.cardTitle}</p>
              )}
              {queueLength > 1 && (
                <span className="shrink-0 text-xs text-natural-400">+{queueLength - 1} 題待問</span>
              )}
            </div>
            <button
              type="button"
              onClick={onSkip}
              className="shrink-0 rounded-lg border border-cream-300 bg-cream-50 px-3 py-1 text-xs font-medium text-natural-500 hover:bg-cream-100 hover:text-natural-700 transition-colors"
            >
              跳過
            </button>
          </div>
          <div key={promptKey} className="animate-fadeIn">
            <p className="text-base leading-relaxed text-natural-700">{prompt.suggestedFollowup}</p>
          </div>
        </div>
      </div>
    </section>
  )
}
