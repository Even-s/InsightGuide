/**
 * New Project Page
 *
 * Users create a new project by entering a title and description.
 * Voice input: records user's spoken description, then AI parses it into
 * structured fields (title + description) and auto-fills the form.
 */

import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { createProject, listProjects, voiceToProjectFields, type Project } from '@/api/projects'

export default function DocumentUploadPage() {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const [recentProjects, setRecentProjects] = useState<Project[]>([])

  // Voice recording state
  const [isRecording, setIsRecording] = useState(false)
  const [isProcessingVoice, setIsProcessingVoice] = useState(false)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const navigate = useNavigate()

  useEffect(() => {
    listProjects().then(res => setRecentProjects(res.projects.slice(0, 5))).catch(() => {})
  }, [])

  const startRecording = async () => {
    setLocalError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      chunksRef.current = []

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        if (blob.size < 1000) return

        setIsProcessingVoice(true)
        try {
          const result = await voiceToProjectFields(blob)
          if (result.parsed.title) setTitle(result.parsed.title)
          if (result.parsed.description) {
            const parts: string[] = []
            if (result.parsed.description) parts.push(result.parsed.description)
            if (result.parsed.business_domain) parts.push(`領域：${result.parsed.business_domain}`)
            if (result.parsed.key_objectives?.length) parts.push(`目標：${result.parsed.key_objectives.join('、')}`)
            if (result.parsed.out_of_scope?.length) parts.push(`不含：${result.parsed.out_of_scope.join('、')}`)
            setDescription(parts.join('\n'))
          } else if (result.transcript) {
            setDescription(result.transcript)
          }
        } catch (error: unknown) {
          const axiosErr = error as { response?: { data?: { detail?: string } } }
          const msg = axiosErr?.response?.data?.detail
            || (error instanceof Error ? error.message : '語音辨識失敗')
          setLocalError(msg)
        } finally {
          setIsProcessingVoice(false)
        }
      }

      mediaRecorder.start()
      mediaRecorderRef.current = mediaRecorder
      setIsRecording(true)
    } catch {
      setLocalError('無法存取麥克風，請確認瀏覽器權限')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
    setIsRecording(false)
  }

  const handleSubmit = async () => {
    if (!title.trim() || !description.trim()) return
    setSubmitting(true)
    setLocalError(null)

    try {
      const newProject = await createProject({
        title: title.trim(),
        description: description.trim(),
      })
      navigate(`/projects/${newProject.id}`)
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : '建立失敗'
      setLocalError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const canSubmit = title.trim() && description.trim() && !submitting && !isRecording && !isProcessingVoice

  return (
    <div className="flex min-h-screen flex-col bg-cream-100">
      <nav className="mx-auto flex w-full max-w-7xl flex-none items-center justify-between px-4 py-5 sm:px-8">
        <button
          type="button"
          onClick={() => navigate('/')}
          className="text-xl font-medium leading-relaxed tracking-wide text-natural-700 transition-colors hover:text-sage-600 sm:text-2xl"
        >
          InsightGuide
        </button>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="inline-flex items-center gap-1.5 rounded-xl px-2.5 py-2.5 text-sm font-medium text-natural-500 transition-colors hover:bg-cream-50 hover:text-sage-600 focus:outline-none focus:ring-2 focus:ring-sage-300 focus:ring-offset-2 focus:ring-offset-cream-100 sm:px-3.5"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            回首頁
          </button>
          <button
            type="button"
            onClick={() => navigate('/projects')}
            className="inline-flex items-center gap-2 rounded-xl border border-cream-300 bg-white px-3 py-2.5 text-sm font-medium text-natural-600 shadow-sm transition-all hover:border-sage-200 hover:bg-sage-50 hover:text-sage-600 focus:outline-none focus:ring-2 focus:ring-sage-300 focus:ring-offset-2 focus:ring-offset-cream-100 sm:px-4"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 6.5A2.5 2.5 0 016.5 4h3l2 2h6A2.5 2.5 0 0120 8.5v9a2.5 2.5 0 01-2.5 2h-11A2.5 2.5 0 014 17V6.5z" />
            </svg>
            管理專案
          </button>
        </div>
      </nav>

      <main className="mx-auto w-full max-w-2xl flex-1 px-8 pb-12 pt-6">
        {/* Hero */}
        <div className="text-center mb-10">
          <h2 className="text-3xl font-semibold leading-tight text-natural-800">
            新建專案
          </h2>
          <p className="mx-auto mt-4 max-w-md text-base leading-relaxed text-natural-600">
            告訴我你想了解什麼，我來幫你規劃該找誰聊、該問什麼。
          </p>
        </div>

        <div className="space-y-6">
          {/* Voice input - separate standalone action */}
          <div className="w-full rounded-lg border border-cream-300 bg-white p-6 shadow-natural">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-natural-700">語音建立</p>
                <p className="text-xs text-natural-500 mt-0.5">說出專案背景，AI 自動填入名稱與描述</p>
              </div>
              <button
                onClick={isRecording ? stopRecording : startRecording}
                disabled={isProcessingVoice}
                className={`flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-medium transition-all ${
                  isRecording
                    ? 'bg-red-50 border border-red-300 text-red-600 hover:bg-red-100'
                    : isProcessingVoice
                    ? 'bg-cream-100 border border-cream-300 text-natural-400'
                    : 'bg-sage-50 border border-sage-300 text-sage-600 hover:bg-sage-100'
                } disabled:opacity-60 disabled:cursor-not-allowed`}
              >
                {isRecording ? (
                  <>
                    <span className="relative flex h-2.5 w-2.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75"></span>
                      <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-red-500"></span>
                    </span>
                    停止錄音
                  </>
                ) : isProcessingVoice ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    分析中...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                    </svg>
                    開始錄音
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Project title + description */}
          <div className="w-full rounded-lg border border-cream-300 bg-white p-8 shadow-natural space-y-5">
            <div>
              <label className="mb-2 block text-base font-medium leading-relaxed tracking-wide text-natural-700">
                專案名稱
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="例：線上預約系統"
                className="w-full px-4 py-3 text-sm leading-relaxed text-natural-700 bg-cream-50 border border-cream-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-sage-400"
              />
            </div>
            <div>
              <label className="mb-2 block text-base font-medium leading-relaxed tracking-wide text-natural-700">
                專案描述
              </label>
              <textarea
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="例：開發診所線上預約系統，目標用戶為櫃台人員與病患。需了解現行預約流程與痛點，須整合 HIS 掛號系統。"
                className="w-full h-36 px-4 py-3 text-sm leading-relaxed text-natural-700 bg-cream-50 border border-cream-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-sage-400 resize-y"
              />
              <p className="mt-2 text-xs text-natural-500">描述越完整，AI 產生的訪談計劃越精準。</p>
            </div>
          </div>

          {/* Error */}
          {localError && (
            <div className="motion-status-in bg-red-50 rounded-xl p-4 border border-red-200">
              <p className="text-sm text-red-700">{localError}</p>
            </div>
          )}

          {/* Submit */}
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="w-full bg-sage-400 text-white py-4 px-6 rounded-xl font-medium tracking-wide shadow-natural text-base leading-relaxed
              hover:bg-sage-500 disabled:bg-cream-300 disabled:text-natural-400 disabled:cursor-not-allowed
              transition-all transform hover:scale-[1.02] disabled:hover:scale-100"
          >
            {submitting ? '建立中...' : '建立專案'}
          </button>
        </div>

        {/* Recent projects */}
        {recentProjects.length > 0 && (
          <div className="motion-reveal-in mt-14">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-natural-500 tracking-wide">近期專案</h3>
              <button
                onClick={() => navigate('/projects')}
                className="text-xs text-sage-600 hover:text-sage-700 underline"
              >
                查看全部
              </button>
            </div>
            <div className="space-y-2">
              {recentProjects.map((p, projectIndex) => (
                <button
                  key={p.id}
                  onClick={() => navigate(`/projects/${p.id}`)}
                  className="motion-surface-in w-full flex items-center justify-between px-5 py-3.5 bg-white border border-cream-200 rounded-xl hover:border-sage-300 hover:shadow-sm transition-all text-left"
                  style={{ animationDelay: `${projectIndex * 40}ms` }}
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-natural-800 truncate">{p.title}</p>
                    {p.description && (
                      <p className="text-xs text-natural-500 truncate mt-0.5">{p.description}</p>
                    )}
                  </div>
                  <svg className="w-4 h-4 text-natural-400 flex-shrink-0 ml-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
