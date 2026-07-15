import { useState } from 'react'
import type {
  AudioDiagnosticsSnapshot,
  AudioProcessingProfile,
} from '@/hooks/useAudioDiagnostics'

interface AudioDiagnosticsPanelProps {
  enabled: boolean
  profile: AudioProcessingProfile
  diagnostics: AudioDiagnosticsSnapshot
  profileLocked: boolean
  onEnabledChange: (enabled: boolean) => void
  onProfileChange: (profile: AudioProcessingProfile) => void
  onReset: () => void
}

const eventLabels: Record<string, string> = {
  speech_started: '偵測到語音開始',
  speech_stopped: '偵測到語音停止',
  transcript_completed: '完成一段辨識',
  transcript_failed: '辨識失敗',
  realtime_error: 'Realtime 錯誤',
}

function formatBoolean(value: boolean | undefined) {
  if (value === undefined) return '未回報'
  return value ? '開啟' : '關閉'
}

function FrequencyBar({ label, range, value }: { label: string; range: string; value?: number }) {
  const resolvedValue = Math.max(0, Math.min(100, value ?? 0))
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-medium text-natural-500">{label}</span>
        <span className="font-mono text-natural-300">{range} · {value ?? 0}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-cream-200">
        <div
          className="h-full rounded-full bg-sage-400 transition-[width] duration-300 ease-out"
          style={{ width: `${resolvedValue}%` }}
        />
      </div>
    </div>
  )
}

export default function AudioDiagnosticsPanel({
  enabled,
  profile,
  diagnostics,
  profileLocked,
  onEnabledChange,
  onProfileChange,
  onReset,
}: AudioDiagnosticsPanelProps) {
  const [isOpen, setIsOpen] = useState(false)
  const settings = diagnostics.trackSettings

  return (
    <div className="pointer-events-none fixed bottom-20 right-4 top-[4.5rem] z-[70] flex flex-col items-end">
      <button
        type="button"
        aria-expanded={isOpen}
        onClick={() => setIsOpen(previous => !previous)}
        className="pointer-events-auto flex shrink-0 items-center gap-2 rounded-xl border border-cream-300 bg-white px-3 py-2 text-xs font-medium text-natural-500 shadow-sm transition-colors hover:border-sage-200 hover:text-sage-600"
      >
        <span className={`h-2 w-2 rounded-full ${enabled ? (diagnostics.active ? 'animate-pulse bg-sage-400' : 'bg-wood-300') : 'bg-natural-200'}`} />
        音訊診斷
      </button>

      {isOpen && (
        <aside className="pointer-events-auto mt-2 min-h-0 w-[min(23rem,calc(100vw-2rem))] flex-1 overflow-hidden rounded-2xl border border-cream-300 bg-white shadow-natural animate-fadeIn">
          <div className="h-full overflow-y-auto overscroll-contain p-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-sm font-semibold text-natural-700">音訊診斷模式</h2>
              <p className="mt-1 text-xs leading-relaxed text-natural-400">資料只顯示在本頁，不會額外上傳錄音。</p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={enabled}
              aria-label="啟用音訊診斷模式"
              onClick={() => onEnabledChange(!enabled)}
              className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${enabled ? 'bg-sage-400' : 'bg-natural-200'}`}
            >
              <span className={`absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${enabled ? 'translate-x-5' : 'translate-x-0'}`} />
            </button>
          </div>

          <div className={`mt-4 space-y-4 transition-opacity ${enabled ? 'opacity-100' : 'pointer-events-none opacity-40'}`}>
            <section>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-xs font-semibold tracking-wide text-natural-500">A/B 音訊處理</h3>
                {profileLocked && <span className="text-[11px] text-wood-400">請先暫停再切換</span>}
              </div>
              <div className="grid grid-cols-2 gap-2 rounded-xl bg-cream-100 p-1">
                <button
                  type="button"
                  disabled={profileLocked}
                  onClick={() => onProfileChange('standard')}
                  className={`rounded-lg px-2 py-2 text-xs transition-colors disabled:cursor-not-allowed ${profile === 'standard' ? 'bg-white font-semibold text-sage-600 shadow-sm' : 'text-natural-400 hover:text-natural-600'}`}
                >
                  標準處理
                </button>
                <button
                  type="button"
                  disabled={profileLocked}
                  onClick={() => onProfileChange('raw')}
                  className={`rounded-lg px-2 py-2 text-xs transition-colors disabled:cursor-not-allowed ${profile === 'raw' ? 'bg-white font-semibold text-sage-600 shadow-sm' : 'text-natural-400 hover:text-natural-600'}`}
                >
                  原始音訊
                </button>
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-natural-400">
                {profile === 'standard'
                  ? '回音消除開啟、自動增益開啟、降噪關閉。'
                  : '回音消除、自動增益與降噪全部關閉，使用單聲道 48 kHz。'}
              </p>
            </section>

            <section className="border-t border-cream-200 pt-3">
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-natural-500">瀏覽器實際設定</h3>
              {settings ? (
                <div className="space-y-2 text-xs">
                  <p className="truncate text-natural-600" title={settings.deviceLabel}>{settings.deviceLabel}</p>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-natural-400">
                    <span>取樣率</span><span className="text-right font-mono text-natural-600">{settings.sampleRate ? `${settings.sampleRate} Hz` : '未回報'}</span>
                    <span>聲道</span><span className="text-right text-natural-600">{settings.channelCount ?? '未回報'}</span>
                    <span>回音消除</span><span className="text-right text-natural-600">{formatBoolean(settings.echoCancellation)}</span>
                    <span>自動增益</span><span className="text-right text-natural-600">{formatBoolean(settings.autoGainControl)}</span>
                    <span>降噪</span><span className="text-right text-natural-600">{formatBoolean(settings.noiseSuppression)}</span>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-natural-300">開始或繼續訪談後顯示實際設定。</p>
              )}
            </section>

            <section className="border-t border-cream-200 pt-3">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-xs font-semibold tracking-wide text-natural-500">輸入頻率能量</h3>
                <span className={`text-[11px] ${diagnostics.active ? 'text-sage-500' : 'text-natural-300'}`}>
                  {diagnostics.active ? '即時量測中' : '等待麥克風'}
                </span>
              </div>
              <div className="space-y-2.5">
                <FrequencyBar label="低頻" range="80–300 Hz" value={diagnostics.frequencyLevels?.low} />
                <FrequencyBar label="中頻" range="300–2000 Hz" value={diagnostics.frequencyLevels?.mid} />
                <FrequencyBar label="高頻" range="2–8 kHz" value={diagnostics.frequencyLevels?.high} />
              </div>
              {diagnostics.analyserError && (
                <p role="alert" className="mt-2 text-xs text-red-600">{diagnostics.analyserError}</p>
              )}
            </section>

            <section className="border-t border-cream-200 pt-3">
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-natural-500">Realtime 傳輸</h3>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs text-natural-400">
                <span>連線</span><span className="text-right text-natural-600">{diagnostics.connectionState}</span>
                <span>Codec</span><span className="truncate text-right text-natural-600" title={diagnostics.codec ?? ''}>{diagnostics.codec ?? '等待連線'}</span>
                <span>已送出</span><span className="text-right font-mono text-natural-600">{Math.round(diagnostics.bytesSent / 1024)} KB</span>
                <span>語音區段</span><span className="text-right font-mono text-natural-600">{diagnostics.speechStartedCount}/{diagnostics.speechStoppedCount}</span>
                <span>辨識片段</span><span className="text-right font-mono text-natural-600">{diagnostics.transcriptCompletedCount}</span>
              </div>
              {diagnostics.lastCompletedTranscript && (
                <div className="mt-2 rounded-lg bg-cream-100 px-3 py-2">
                  <p className="mb-1 text-[11px] font-medium text-natural-400">最後辨識</p>
                  <p className="line-clamp-3 text-xs leading-relaxed text-natural-600">{diagnostics.lastCompletedTranscript}</p>
                </div>
              )}
            </section>

            <section className="border-t border-cream-200 pt-3">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-xs font-semibold tracking-wide text-natural-500">事件紀錄</h3>
                <button type="button" onClick={onReset} className="text-[11px] text-natural-400 hover:text-sage-600">清除</button>
              </div>
              {diagnostics.events.length > 0 ? (
                <ol className="space-y-1.5">
                  {[...diagnostics.events].reverse().map(event => (
                    <li key={event.id} className="flex gap-2 text-[11px] leading-relaxed">
                      <span className="shrink-0 font-mono text-natural-300">{event.time}</span>
                      <span className="min-w-0 text-natural-500">
                        {eventLabels[event.type] ?? event.type}
                        {event.detail ? ` · ${event.detail}` : ''}
                      </span>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-xs text-natural-300">尚無診斷事件。</p>
              )}
            </section>
          </div>
          </div>
        </aside>
      )}
    </div>
  )
}
