import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import {
  interviewRoundsAPI,
  type InterviewGenerationMode,
  type InterviewRound,
  type InterviewSeries,
} from '@/api/interviewRounds'
import type { StakeholderProfile } from '@/api/projects'
import type { InterviewSession } from '@/types/interview'

interface InterviewRoundModalProps {
  projectId: string
  profile: StakeholderProfile
  sessions: InterviewSession[]
  initialView: 'create' | 'history'
  initialSeriesId?: string
  onClose: () => void
  onGuideCreated: (documentId: string) => void
}

const modeOptions: Array<{
  value: InterviewGenerationMode
  title: string
  description: string
}> = [
  { value: 'follow_up', title: '產生延伸追問', description: '依據先前洞察補問不同問題。' },
  { value: 'continue_unfinished', title: '延續未完成題目', description: '優先處理尚未取得答案的內容。' },
  { value: 'validate', title: '重新驗證結論', description: '用新問題確認既有理解是否正確。' },
  { value: 'new_scope', title: '建立新主題', description: '同一位受訪者，但本輪探索不同範圍。' },
]

const statusLabels: Record<string, string> = {
  draft: '草稿',
  guide_ready: '大綱就緒',
  scheduled: '已排程',
  interviewing: '訪談中',
  completed: '已完成',
}

export function InterviewRoundModal({
  projectId,
  profile,
  sessions,
  initialView,
  initialSeriesId,
  onClose,
  onGuideCreated,
}: InterviewRoundModalProps) {
  const [view, setView] = useState(initialView)
  const [series, setSeries] = useState<InterviewSeries[]>([])
  const [roundsBySeries, setRoundsBySeries] = useState<Record<string, InterviewRound[]>>({})
  const [selectedSeriesId, setSelectedSeriesId] = useState('new')
  const [topicTitle, setTopicTitle] = useState('')
  const [objective, setObjective] = useState('')
  const [generationMode, setGenerationMode] = useState<InterviewGenerationMode>('follow_up')
  const [sourceSessionIds, setSourceSessionIds] = useState<string[]>([])
  const [focusTopics, setFocusTopics] = useState('')
  const [durationMinutes, setDurationMinutes] = useState(30)
  const [excludeCompleted, setExcludeCompleted] = useState(true)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const endedSessions = useMemo(
    () => sessions
      .filter(session => session.status === 'ended')
      .sort((a, b) => new Date(b.endedAt || b.createdAt).getTime() - new Date(a.endedAt || a.createdAt).getTime()),
    [sessions],
  )

  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', closeOnEscape)

    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', closeOnEscape)
    }
  }, [onClose])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    interviewRoundsAPI.listSeries(projectId, profile.id)
      .then(async items => {
        const roundEntries = await Promise.all(
          items.map(async item => [item.id, await interviewRoundsAPI.listRounds(item.id)] as const),
        )
        if (cancelled) return
        setSeries(items)
        setRoundsBySeries(Object.fromEntries(roundEntries))
        if (items.length) {
          const initialSeries = items.find(item => item.id === initialSeriesId) || items[0]
          setSelectedSeriesId(initialSeries.id)
          setTopicTitle(initialSeries.title)
        } else {
          setTopicTitle(profile.roleTitle || '一般訪談主題')
          setGenerationMode('new_scope')
        }
        if (endedSessions[0]) setSourceSessionIds([endedSessions[0].id])
      })
      .catch(() => setError('無法載入訪談輪次'))
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [endedSessions, initialSeriesId, profile.id, profile.roleTitle, projectId])

  const selectSeries = (value: string) => {
    setSelectedSeriesId(value)
    if (value === 'new') {
      setTopicTitle('')
      setGenerationMode('new_scope')
      return
    }
    const target = series.find(item => item.id === value)
    if (target) {
      setTopicTitle(target.title)
      if (generationMode === 'new_scope') setGenerationMode('follow_up')
    }
  }

  const toggleSourceSession = (sessionId: string) => {
    setSourceSessionIds(previous => previous.includes(sessionId)
      ? previous.filter(id => id !== sessionId)
      : [...previous, sessionId])
  }

  const createNextRound = async () => {
    if (!objective.trim()) {
      setError('請先填寫本輪訪談目的')
      return
    }
    if (selectedSeriesId === 'new' && !topicTitle.trim()) {
      setError('請輸入新主題名稱')
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      const targetSeries = selectedSeriesId === 'new'
        ? await interviewRoundsAPI.createSeries(projectId, profile.id, { title: topicTitle.trim() })
        : series.find(item => item.id === selectedSeriesId)
      if (!targetSeries) throw new Error('series not found')

      const interviewRound = await interviewRoundsAPI.createRound(targetSeries.id, {
        objective: objective.trim(),
        generationMode,
        sourceSessionIds,
        focusTopics: focusTopics.split(/[、,，\n]/).map(item => item.trim()).filter(Boolean),
        excludeCompletedQuestions: excludeCompleted,
      })
      const guide = await interviewRoundsAPI.generateGuide(interviewRound.id, {
        durationMinutes,
        interviewStyle: generationMode === 'validate' ? 'validation' : 'exploratory',
      })
      onGuideCreated(guide.documentId)
    } catch (requestError: unknown) {
      const apiError = requestError as { response?: { data?: { detail?: string } } }
      setError(apiError.response?.data?.detail || '建立下一輪訪談失敗')
    } finally {
      setSubmitting(false)
    }
  }

  const allRoundRows = series.flatMap(item =>
    (roundsBySeries[item.id] || []).map(round => ({ series: item, round })),
  ).sort((a, b) => new Date(b.round.createdAt).getTime() - new Date(a.round.createdAt).getTime())

  return createPortal(
    <div
      className="fixed inset-0 z-[100] isolate flex items-center justify-center bg-natural-900/30 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="訪談輪次"
      onMouseDown={event => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div className="relative z-[101] flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-cream-300 bg-white shadow-xl">
        <header className="flex items-start justify-between border-b border-cream-300 px-6 py-5">
          <div>
            <p className="text-xs font-semibold tracking-[0.14em] text-sage-500">INTERVIEW ROUNDS</p>
            <h2 className="mt-1 text-xl font-semibold text-natural-800">{profile.name}的訪談規劃</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="關閉" className="text-2xl leading-none text-natural-400 hover:text-natural-700">×</button>
        </header>

        <nav className="flex border-b border-cream-300 px-6" aria-label="訪談輪次功能">
          <button type="button" onClick={() => setView('create')} className={`border-b-2 px-1 py-3 text-sm font-semibold ${view === 'create' ? 'border-sage-500 text-sage-600' : 'border-transparent text-natural-400'}`}>開始下一輪</button>
          <button type="button" onClick={() => setView('history')} className={`ml-7 border-b-2 px-1 py-3 text-sm font-semibold ${view === 'history' ? 'border-sage-500 text-sage-600' : 'border-transparent text-natural-400'}`}>歷史輪次 · {allRoundRows.length}</button>
        </nav>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {loading ? (
            <p className="py-12 text-center text-sm text-natural-400">載入訪談輪次中…</p>
          ) : view === 'history' ? (
            <div className="space-y-0">
              {allRoundRows.length === 0 ? (
                <p className="py-12 text-center text-sm text-natural-400">尚未建立訪談輪次</p>
              ) : allRoundRows.map(({ series: item, round }, index) => {
                const recordSessionId = [...round.sessionIds].reverse().find(id => endedSessions.some(session => session.id === id))
                  || round.sessionIds[round.sessionIds.length - 1]
                return (
                  <article key={round.id} className="grid grid-cols-[44px_minmax(0,1fr)_auto] gap-4 border-b border-cream-300 py-5 first:pt-0 last:border-b-0">
                    <div className="flex h-9 w-9 items-center justify-center bg-sage-50 text-xs font-semibold text-sage-600">{String(index + 1).padStart(2, '0')}</div>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-semibold text-natural-700">{item.title} · 第 {round.roundNumber} 輪</h3>
                        <span className="text-xs text-natural-400">{statusLabels[round.status] || round.status}</span>
                      </div>
                      <p className="mt-1 text-sm leading-6 text-natural-500">{round.objective || '未設定訪談目的'}</p>
                      <p className="mt-2 text-xs text-natural-400">大綱 V{round.guideVersion || round.roundNumber} · {round.cardCount} 題 · {formatDate(round.createdAt)}</p>
                      {round.focusTopics.length > 0 && <p className="mt-1 text-xs text-natural-400">聚焦：{round.focusTopics.join('、')}</p>}
                    </div>
                    <div className="flex items-start gap-2">
                      {round.guideDocumentId && (
                        <button type="button" onClick={() => onGuideCreated(round.guideDocumentId!)} className="rounded-lg border border-cream-300 px-3 py-1.5 text-xs font-medium text-natural-600 hover:border-sage-300 hover:text-sage-600">查看大綱</button>
                      )}
                      {recordSessionId && (
                        <button type="button" onClick={() => window.location.assign(`/sessions/${recordSessionId}/insight-memo`)} className="rounded-lg bg-sage-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-sage-600">訪談紀錄</button>
                      )}
                    </div>
                  </article>
                )
              })}
            </div>
          ) : (
            <div className="space-y-6">
              <Field label="1. 選擇訪談主題">
                <select aria-label="訪談主題" value={selectedSeriesId} onChange={event => selectSeries(event.target.value)} className="w-full rounded-lg border border-cream-400 bg-white px-3 py-2.5 text-sm text-natural-700 outline-none focus:border-sage-400">
                  {series.map(item => <option key={item.id} value={item.id}>{item.title}（{item.roundsCount} 輪）</option>)}
                  <option value="new">＋ 建立新主題</option>
                </select>
                {selectedSeriesId === 'new' && <input value={topicTitle} onChange={event => setTopicTitle(event.target.value)} placeholder="例如：例外掛號處理" className="mt-2 w-full rounded-lg border border-cream-400 px-3 py-2.5 text-sm outline-none focus:border-sage-400" />}
              </Field>

              <Field label="2. 設定本輪目的">
                <textarea value={objective} onChange={event => setObjective(event.target.value)} rows={3} placeholder="例如：釐清第一次訪談未確認的臨時取消與跨科掛號流程" className="w-full resize-none rounded-lg border border-cream-400 px-3 py-2.5 text-sm leading-6 outline-none focus:border-sage-400" />
              </Field>

              <Field label="3. 選擇參考訪談">
                {endedSessions.length === 0 ? <p className="text-sm text-natural-400">目前沒有可參考的已完成訪談。</p> : (
                  <div className="divide-y divide-cream-200 border-y border-cream-300">
                    {endedSessions.map((session, index) => (
                      <label key={session.id} className="flex cursor-pointer items-center gap-3 py-3 text-sm text-natural-600">
                        <input type="checkbox" checked={sourceSessionIds.includes(session.id)} onChange={() => toggleSourceSession(session.id)} className="accent-sage-500" />
                        <span>第 {endedSessions.length - index} 場 · {formatDate(session.endedAt || session.createdAt)}</span>
                      </label>
                    ))}
                  </div>
                )}
              </Field>

              <Field label="4. 選擇大綱產生方式">
                <div className="grid gap-2 sm:grid-cols-2">
                  {modeOptions.map(option => (
                    <label key={option.value} className={`cursor-pointer rounded-lg border p-3 ${generationMode === option.value ? 'border-sage-400 bg-sage-50' : 'border-cream-300'}`}>
                      <div className="flex items-center gap-2">
                        <input type="radio" name="generation-mode" checked={generationMode === option.value} onChange={() => setGenerationMode(option.value)} className="accent-sage-500" />
                        <span className="text-sm font-semibold text-natural-700">{option.title}</span>
                      </div>
                      <p className="mt-1 pl-5 text-xs leading-5 text-natural-400">{option.description}</p>
                    </label>
                  ))}
                </div>
              </Field>

              <Field label="5. 補充聚焦範圍">
                <input value={focusTopics} onChange={event => setFocusTopics(event.target.value)} placeholder="以頓號或逗號分隔，例如：臨時取消、跨科掛號" className="w-full rounded-lg border border-cream-400 px-3 py-2.5 text-sm outline-none focus:border-sage-400" />
                <div className="mt-3 flex flex-wrap items-center gap-5 text-sm text-natural-500">
                  <label className="flex items-center gap-2"><input type="checkbox" checked={excludeCompleted} onChange={event => setExcludeCompleted(event.target.checked)} className="accent-sage-500" />避免重複已完成問題</label>
                  <label className="flex items-center gap-2">訪談時間<select value={durationMinutes} onChange={event => setDurationMinutes(Number(event.target.value))} className="rounded border border-cream-300 bg-white px-2 py-1"><option value={20}>20 分鐘</option><option value={30}>30 分鐘</option><option value={45}>45 分鐘</option><option value={60}>60 分鐘</option></select></label>
                </div>
              </Field>
            </div>
          )}
          {error && <p className="mt-5 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600" role="alert">{error}</p>}
        </div>

        {view === 'create' && !loading && (
          <footer className="flex items-center justify-between border-t border-cream-300 px-6 py-4">
            <p className="text-xs text-natural-400">建立後會先進入新大綱預覽，舊輪次不會被修改。</p>
            <div className="flex gap-2">
              <button type="button" onClick={onClose} className="rounded-lg border border-cream-300 px-4 py-2 text-sm text-natural-600">取消</button>
              <button type="button" onClick={createNextRound} disabled={submitting} className="rounded-lg bg-sage-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sage-600 disabled:opacity-50">{submitting ? '正在建立大綱…' : '建立並預覽大綱'}</button>
            </div>
          </footer>
        )}
      </div>
    </div>,
    document.body,
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <section><h3 className="mb-2 text-sm font-semibold text-natural-700">{label}</h3>{children}</section>
}

function formatDate(value?: string) {
  if (!value) return '日期未記錄'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '日期未記錄'
  return new Intl.DateTimeFormat('zh-TW', { year: 'numeric', month: 'numeric', day: 'numeric' }).format(date)
}
