import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '@/api/client'
import { listProjects, getStakeholderPlan, type Project, type StakeholderPlan } from '@/api/projects'

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
          <button
            onClick={() => navigate('/')}
            className="px-5 py-2.5 bg-white border border-cream-200 text-natural-700 rounded-lg hover:bg-cream-50 transition-colors shadow-sm"
          >
            回首頁
          </button>
        </div>

        {/* Project Cards Grid */}
        {projectCards.length === 0 ? (
          <div className="text-center py-20 bg-white rounded-2xl border border-cream-200 shadow-sm">
            <div className="mb-6">
              <svg className="w-20 h-20 mx-auto text-natural-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <p className="text-lg text-natural-600 mb-6">尚無專案，前往首頁建立第一個專案</p>
            <button
              onClick={() => navigate('/')}
              className="px-6 py-3 bg-sage-500 text-white rounded-lg hover:bg-sage-600 transition-colors shadow-sm"
            >
              建立專案
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {projectCards.map((card) => (
              <div
                key={card.project.id}
                className="bg-white rounded-2xl border border-cream-200 shadow-sm hover:shadow-md transition-all overflow-hidden"
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
                      開始訪談
                    </button>
                    <button
                      onClick={() => navigate(`/projects/${card.project.id}/evidence-matrix`)}
                      className="px-4 py-2.5 bg-cream-50 text-natural-700 rounded-lg hover:bg-cream-100 transition-colors font-medium text-sm border border-cream-200"
                    >
                      查看報告
                    </button>
                    <button
                      onClick={() => navigate(`/projects/${card.project.id}`)}
                      className="px-4 py-2.5 bg-white text-natural-600 rounded-lg hover:bg-cream-50 transition-colors text-sm border border-cream-200"
                      title="管理專案"
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
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
