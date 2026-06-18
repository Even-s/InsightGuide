import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listProjects, createProject, deleteProject, voiceToProjectFields, type Project } from '@/api/projects'

export default function ProjectListPage() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [creating, setCreating] = useState(false)

  // Voice input state
  const [isRecording, setIsRecording] = useState(false)
  const [isProcessingVoice, setIsProcessingVoice] = useState(false)
  const [voiceTranscript, setVoiceTranscript] = useState('')
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const streamRef = useRef<MediaStream | null>(null)

  const loadProjects = useCallback(async () => {
    try {
      setLoading(true)
      const data = await listProjects()
      setProjects(data.projects)
    } catch (err) {
      console.error('Failed to load projects:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadProjects() }, [loadProjects])

  const handleCreate = async () => {
    if (!newTitle.trim()) return
    setCreating(true)
    try {
      const project = await createProject({
        title: newTitle.trim(),
        description: newDescription.trim() || undefined,
      })
      setShowCreate(false)
      setNewTitle('')
      setNewDescription('')
      navigate(`/projects/${project.id}`)
    } catch (err) {
      console.error('Failed to create project:', err)
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('確定要刪除此專案？')) return
    try {
      await deleteProject(id)
      setProjects(prev => prev.filter(p => p.id !== id))
    } catch (err) {
      console.error('Failed to delete project:', err)
    }
  }

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      audioChunksRef.current = []

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'
      const recorder = new MediaRecorder(stream, { mimeType })

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data)
      }

      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        streamRef.current = null

        const blob = new Blob(audioChunksRef.current, { type: mimeType })
        audioChunksRef.current = []

        if (blob.size < 1000) return

        setIsProcessingVoice(true)
        try {
          const result = await voiceToProjectFields(blob)
          setVoiceTranscript(result.transcript)

          // Auto-fill form fields from parsed result
          const p = result.parsed
          if (p.title) setNewTitle(p.title)
          if (p.description) setNewDescription(p.description)
        } catch (err) {
          console.error('Voice processing failed:', err)
        } finally {
          setIsProcessingVoice(false)
        }
      }

      mediaRecorderRef.current = recorder
      recorder.start()
      setIsRecording(true)
    } catch (err) {
      console.error('Failed to start recording:', err)
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
      mediaRecorderRef.current = null
    }
    setIsRecording(false)
  }

  const statusLabel: Record<string, string> = {
    active: '進行中',
    planning: '規劃中',
    interviewing: '訪談中',
    ready_for_brd: '可生成 BRD',
    completed: '已完成',
  }

  const statusColor: Record<string, string> = {
    active: 'bg-blue-100 text-blue-800',
    planning: 'bg-cream-100 text-natural-700',
    interviewing: 'bg-yellow-100 text-yellow-800',
    ready_for_brd: 'bg-green-100 text-green-800',
    completed: 'bg-purple-100 text-purple-800',
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-natural-800">專案列表</h1>
          <p className="text-natural-500 mt-1">管理 BRD 需求訪談專案</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => navigate('/projects/manage')}
            className="px-4 py-2 border border-cream-300 text-natural-700 rounded-lg hover:bg-cream-50 transition-colors"
          >
            管理面板
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 bg-sage-400 text-white rounded-lg hover:bg-sage-500 transition-colors"
          >
            + 建立專案
          </button>
        </div>
      </div>

      {/* Create dialog */}
      {showCreate && (
        <div className="mb-8 p-6 bg-white rounded-xl border border-cream-200 shadow-natural">
          <h2 className="text-lg font-semibold mb-4">建立新專案</h2>

          {/* Voice Input */}
          <div className="mb-5 p-4 bg-sage-50 rounded-lg border border-sage-100">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-sage-800">語音輸入</span>
              <span className="text-xs text-sage-500">
                {isRecording ? '錄音中...' : isProcessingVoice ? '分析中...' : '按下麥克風描述你的專案'}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={isRecording ? stopRecording : startRecording}
                disabled={isProcessingVoice}
                className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${
                  isRecording
                    ? 'bg-red-500 hover:bg-red-600 animate-pulse'
                    : isProcessingVoice
                    ? 'bg-cream-300 cursor-not-allowed'
                    : 'bg-sage-400 hover:bg-sage-500'
                }`}
              >
                {isProcessingVoice ? (
                  <svg className="w-5 h-5 text-white animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : isRecording ? (
                  <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
                    <rect x="6" y="6" width="12" height="12" rx="2" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                  </svg>
                )}
              </button>
              <div className="flex-1">
                {isRecording && (
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                    <span className="text-sm text-red-600">正在錄音，說完後按停止</span>
                  </div>
                )}
                {isProcessingVoice && (
                  <span className="text-sm text-sage-600">正在轉錄與分析語音...</span>
                )}
                {voiceTranscript && !isRecording && !isProcessingVoice && (
                  <div className="text-xs text-natural-500">
                    <span className="font-medium">辨識結果：</span>{voiceTranscript.slice(0, 100)}{voiceTranscript.length > 100 ? '...' : ''}
                  </div>
                )}
                {!isRecording && !isProcessingVoice && !voiceTranscript && (
                  <span className="text-sm text-natural-500">
                    例：「我想做一個 CRM 系統，主要目標是統一需求追蹤，減少版本混亂」
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-natural-700 mb-1">專案名稱 *</label>
              <input
                type="text"
                value={newTitle}
                onChange={e => setNewTitle(e.target.value)}
                placeholder="例：CRM 需求管理系統"
                className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400 focus:border-sage-400"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-natural-700 mb-1">專案描述</label>
              <textarea
                value={newDescription}
                onChange={e => setNewDescription(e.target.value)}
                placeholder="簡述專案背景與目標"
                rows={2}
                className="w-full px-3 py-2 border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400 focus:border-sage-400"
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleCreate}
                disabled={creating || !newTitle.trim()}
                className="px-4 py-2 bg-sage-400 text-white rounded-lg hover:bg-sage-500 disabled:opacity-50 transition-colors"
              >
                {creating ? '建立中...' : '建立專案'}
              </button>
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 bg-cream-100 text-natural-700 rounded-lg hover:bg-cream-200 transition-colors"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Project list */}
      {loading ? (
        <div className="text-center py-12 text-natural-500">載入中...</div>
      ) : projects.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-natural-500 mb-4">尚無專案</p>
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 bg-sage-400 text-white rounded-lg hover:bg-sage-500 transition-colors"
          >
            建立第一個專案
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {projects.map(project => (
            <div
              key={project.id}
              className="p-5 bg-white rounded-xl border border-cream-200 hover:border-sage-300 hover:shadow-md transition-all cursor-pointer"
              onClick={() => navigate(`/projects/${project.id}`)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h3 className="text-lg font-semibold text-natural-800">{project.title}</h3>
                    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${statusColor[project.status] || 'bg-cream-100 text-natural-700'}`}>
                      {statusLabel[project.status] || project.status}
                    </span>
                  </div>
                  {project.description && (
                    <p className="text-natural-600 mt-1 text-sm">{project.description}</p>
                  )}
                </div>
                <button
                  onClick={e => { e.stopPropagation(); handleDelete(project.id) }}
                  className="p-2 text-natural-400 hover:text-red-500 transition-colors"
                  title="刪除專案"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Navigation link to legacy pages */}
      <div className="mt-8 pt-6 border-t border-cream-200">
        <button
          onClick={() => navigate('/prep-sessions')}
          className="text-sm text-natural-500 hover:text-sage-600 transition-colors"
        >
          前往獨立訪談模式 (PrepSessions) &rarr;
        </button>
      </div>
    </div>
  )
}
