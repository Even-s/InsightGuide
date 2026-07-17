import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '@/api/client'
import {
  deleteProject,
  getStakeholderPlan,
  listProjects,
  type Project,
  type StakeholderPlan,
} from '@/api/projects'

interface SessionInfo {
  id: string
  status: string
  endedAt?: string
}

interface ProjectCardData {
  project: Project
  plan: StakeholderPlan | null
  completedInterviews: number
  totalStakeholders: number
  progressPercentage: number
  lastInterviewDate?: string
  hasInterviews: boolean
  userFriendlyStatus: string
}

export default function ProjectSessionsPage() {
  const navigate = useNavigate()
  const [projectCards, setProjectCards] = useState<ProjectCardData[]>([])
  const [loading, setLoading] = useState(true)
  const [deletingProjectId, setDeletingProjectId] = useState<string | null>(null)

  const getUserFriendlyStatus = (status: string): string => {
    const statusMap: Record<string, string> = {
      active: '進行中',
      planning: '規劃中',
      interviewing: '訪談中',
      ready_for_brd: '已完成',
      completed: '已完成',
    }
    return statusMap[status] || '規劃中'
  }

  const getStatusBadgeClass = (status: string): string => {
    const classMap: Record<string, string> = {
      active: 'bg-emerald-100 text-emerald-700',
      planning: 'bg-cream-200 text-natural-700',
      interviewing: 'bg-blue-100 text-blue-700',
      ready_for_brd: 'bg-purple-100 text-purple-700',
      completed: 'bg-purple-100 text-purple-700',
    }
    return classMap[status] || 'bg-cream-200 text-natural-700'
  }

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      const { projects } = await listProjects()

      // Load details for each project
      const cards = await Promise.all(
        projects.map(async (project) => {
          try {
            // Fetch stakeholder plan
            const plan = await getStakeholderPlan(project.id).catch(() => null)

            // Fetch interview sessions
            const sessionsRes = await apiClient.get('/api/interview-sessions/', {
              params: { limit: 100, projectId: project.id }
            }).catch(() => ({ data: { sessions: [] } }))

            const sessions: SessionInfo[] = sessionsRes.data.sessions || []
            const completedSessions = sessions.filter(s => s.status === 'ended')

            // Calculate progress
            const totalStakeholders = plan?.profiles.length || 0
            const completedInterviews = completedSessions.length
            const progressPercentage = plan?.summary.progress_percentage || 0

            // Find most recent interview date
            let lastInterviewDate: string | undefined
            if (completedSessions.length > 0) {
              const sortedSessions = completedSessions
                .filter(s => s.endedAt)
                .sort((a, b) => new Date(b.endedAt!).getTime() - new Date(a.endedAt!).getTime())
              if (sortedSessions.length > 0) {
                lastInterviewDate = sortedSessions[0].endedAt
              }
            }

            return {
              project,
              plan,
              completedInterviews,
              totalStakeholders,
              progressPercentage,
              lastInterviewDate,
              hasInterviews: sessions.length > 0,
              userFriendlyStatus: getUserFriendlyStatus(project.status),
            }
          } catch (err) {
            console.error(`Failed to load data for project ${project.id}:`, err)
            return {
              project,
              plan: null,
              completedInterviews: 0,
              totalStakeholders: 0,
              progressPercentage: 0,
              hasInterviews: false,
              userFriendlyStatus: getUserFriendlyStatus(project.status),
            }
          }
        })
      )

      setProjectCards(cards)
    } catch (err) {
      console.error('Failed to load projects:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const handleDeleteProject = async (project: Project) => {
    const confirmed = window.confirm(
      `確定要刪除「${project.title}」嗎？\n\n所有受訪者、訪談記錄與分析結果都會一併刪除，此操作無法復原。`,
    )
    if (!confirmed) return

    try {
      setDeletingProjectId(project.id)
      await deleteProject(project.id)
      setProjectCards(cards => cards.filter(card => card.project.id !== project.id))
    } catch (err) {
      console.error(`Failed to delete project ${project.id}:`, err)
      window.alert('刪除專案失敗，請稍後再試。')
    } finally {
      setDeletingProjectId(null)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-cream-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block w-8 h-8 border-4 border-sage-400 border-t-transparent rounded-full animate-spin mb-3"></div>
          <p className="text-natural-600">載入專案中...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-cream-50">
      <div className="max-w-6xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="flex justify-between items-center mb-10">
          <div>
            <h1 className="text-3xl font-bold text-natural-900">我的專案</h1>
            <p className="text-natural-600 mt-2">管理您的需求探索專案</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => navigate('/')}
              className="inline-flex items-center gap-1.5 rounded-xl px-3.5 py-2.5 text-sm font-medium text-natural-500 transition-colors hover:bg-cream-100 hover:text-sage-600 focus:outline-none focus:ring-2 focus:ring-sage-300 focus:ring-offset-2 focus:ring-offset-cream-50"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              回首頁
            </button>
            <button
              type="button"
              onClick={() => navigate('/projects/new')}
              className="inline-flex items-center gap-1.5 rounded-xl bg-sage-500 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-sage-600 focus:outline-none focus:ring-2 focus:ring-sage-300 focus:ring-offset-2 focus:ring-offset-cream-50"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v14m7-7H5" />
              </svg>
              新增專案
            </button>
          </div>
        </div>

        {/* Project Cards Grid */}
        {projectCards.length === 0 ? (
          <div className="motion-fade-in text-center py-20 bg-white rounded-2xl border border-cream-200 shadow-sm">
            <div className="mb-6">
              <svg className="w-20 h-20 mx-auto text-natural-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <p className="text-lg text-natural-600 mb-6">尚無專案，建立第一個需求探索專案</p>
            <button
              onClick={() => navigate('/projects/new')}
              className="px-6 py-3 bg-sage-500 text-white rounded-lg hover:bg-sage-600 transition-colors shadow-sm"
            >
              建立專案
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {projectCards.map((card, cardIndex) => (
              <div
                key={card.project.id}
                className="motion-surface-in bg-white rounded-2xl border border-cream-200 shadow-sm hover:shadow-md transition-all overflow-hidden"
                style={{ animationDelay: `${Math.min(cardIndex * 45, 225)}ms` }}
              >
                {/* Card Header */}
                <div className="p-6 border-b border-cream-100">
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="text-xl font-semibold text-natural-900 flex-1">
                      {card.project.title}
                    </h3>
                    <span className={`px-3 py-1 text-xs font-medium rounded-full whitespace-nowrap ml-3 ${getStatusBadgeClass(card.project.status)}`}>
                      {card.userFriendlyStatus}
                    </span>
                  </div>
                  {card.project.description && (
                    <p className="text-sm text-natural-600 line-clamp-2 mb-4">
                      {card.project.description}
                    </p>
                  )}
                </div>

                {/* Card Body */}
                <div className="p-6 space-y-4">
                  {/* Progress Bar */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-natural-700">專案進度</span>
                      <span className="text-sm font-semibold text-sage-600">
                        {Math.round(card.progressPercentage)}%
                      </span>
                    </div>
                    <div className="h-2.5 bg-cream-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-sage-400 to-sage-500 rounded-full transition-all duration-500"
                        style={{ width: `${card.progressPercentage}%` }}
                      />
                    </div>
                  </div>

                  {/* Stats */}
                  <div className="grid grid-cols-2 gap-4 py-3">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-natural-800">
                        {card.completedInterviews}/{card.totalStakeholders}
                      </div>
                      <div className="text-xs text-natural-500 mt-1">已完成受訪者</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-natural-800">
                        {card.totalStakeholders}
                      </div>
                      <div className="text-xs text-natural-500 mt-1">受訪者總數</div>
                    </div>
                  </div>

                  {/* Last Interview Date */}
                  {card.lastInterviewDate ? (
                    <div className="flex items-center gap-2 text-sm text-natural-500 pt-2 border-t border-cream-100">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <span>最近訪談：{new Date(card.lastInterviewDate).toLocaleDateString('zh-TW')}</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-sm text-natural-400 pt-2 border-t border-cream-100">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <span>尚未開始訪談</span>
                    </div>
                  )}
                </div>

                {/* Action Buttons */}
                <div className="px-6 pb-6">
                  <div className="flex gap-3">
                    <button
                      onClick={() => navigate(`/projects/${card.project.id}`)}
                      className="flex-1 px-4 py-2.5 bg-sage-500 text-white rounded-lg hover:bg-sage-600 transition-colors font-medium text-sm shadow-sm"
                    >
                      管理專案
                    </button>
                    <button
                      onClick={() => navigate(`/projects/${card.project.id}/evidence-matrix`)}
                      className="px-4 py-2.5 bg-cream-50 text-natural-700 rounded-lg hover:bg-cream-100 transition-colors font-medium text-sm border border-cream-200"
                    >
                      證據矩陣
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteProject(card.project)}
                      disabled={deletingProjectId !== null}
                      className="px-4 py-2.5 bg-white text-red-500 rounded-lg hover:bg-red-50 hover:text-red-600 transition-colors text-sm border border-red-200 disabled:cursor-not-allowed disabled:opacity-50"
                      title={`刪除專案「${card.project.title}」`}
                      aria-label={`刪除專案「${card.project.title}」`}
                    >
                      {deletingProjectId === card.project.id ? (
                        <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                      ) : (
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
