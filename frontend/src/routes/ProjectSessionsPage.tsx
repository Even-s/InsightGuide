import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '@/api/client'
import { listProjects, getStakeholderPlan, type Project, type StakeholderPlan } from '@/api/projects'

interface SessionInfo {
  id: string
  status: string
  stakeholderName?: string
  stakeholderRole?: string
  startedAt?: string
  endedAt?: string
  createdAt: string
  hasMemo: boolean
}

interface ProjectWithSessions {
  project: Project
  plan: StakeholderPlan | null
  sessions: SessionInfo[]
  loading: boolean
}

export default function ProjectSessionsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<ProjectWithSessions[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set())

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      const { projects } = await listProjects()

      const items: ProjectWithSessions[] = projects.map(p => ({
        project: p,
        plan: null,
        sessions: [],
        loading: false,
      }))

      setData(items)

      // Load details for each project in parallel
      const updated = await Promise.all(
        items.map(async (item) => {
          try {
            const [planRes, sessionsRes] = await Promise.all([
              getStakeholderPlan(item.project.id),
              apiClient.get('/api/interview-sessions/', {
                params: { limit: 100, projectId: item.project.id }
              }).then(r => r.data.sessions || []).catch(() => []),
            ])

            const projectSessions: SessionInfo[] = sessionsRes.map((s: any) => ({
              id: s.id,
              status: s.status,
              stakeholderName: s.stakeholderName,
              stakeholderRole: s.stakeholderRole,
              startedAt: s.startedAt,
              endedAt: s.endedAt,
              createdAt: s.createdAt,
              hasMemo: false,
            }))

            return { ...item, plan: planRes, sessions: projectSessions }
          } catch {
            return item
          }
        })
      )

      setData(updated)
    } catch (err) {
      console.error('Failed to load data:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const toggleProject = (projectId: string) => {
    setExpandedProjects(prev => {
      const next = new Set(prev)
      if (next.has(projectId)) {
        next.delete(projectId)
      } else {
        next.add(projectId)
      }
      return next
    })
  }

  const handleDeleteSession = async (sessionId: string) => {
    if (!confirm('確定要刪除此訪談 session？')) return
    try {
      await apiClient.delete(`/api/interview-sessions/${sessionId}`)
      setData(prev => prev.map(item => ({
        ...item,
        sessions: item.sessions.filter(s => s.id !== sessionId),
      })))
    } catch (err) {
      console.error('Failed to delete session:', err)
    }
  }

  const statusConfig: Record<string, { label: string; color: string }> = {
    idle: { label: '待機', color: 'bg-cream-100 text-natural-600' },
    preparing: { label: '準備中', color: 'bg-blue-100 text-blue-600' },
    ready: { label: '就緒', color: 'bg-blue-100 text-blue-700' },
    interviewing: { label: '訪談中', color: 'bg-green-100 text-green-700' },
    paused: { label: '暫停', color: 'bg-yellow-100 text-yellow-700' },
    ended: { label: '已結束', color: 'bg-cream-100 text-natural-500' },
    failed: { label: '失敗', color: 'bg-red-100 text-red-600' },
  }

  const projectStatusConfig: Record<string, { label: string; color: string }> = {
    active: { label: '進行中', color: 'bg-blue-100 text-blue-700' },
    planning: { label: '規劃中', color: 'bg-cream-100 text-natural-700' },
    interviewing: { label: '訪談中', color: 'bg-green-100 text-green-700' },
    ready_for_brd: { label: '可生成 BRD', color: 'bg-emerald-100 text-emerald-700' },
    completed: { label: '已完成', color: 'bg-purple-100 text-purple-700' },
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-cream-100 flex items-center justify-center">
        <div className="text-natural-500">載入中...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-cream-100">
      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-2xl font-bold text-natural-800">專案與訪談管理</h1>
            <p className="text-natural-500 mt-1">管理所有專案及其訪談 sessions</p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => navigate('/projects')}
              className="px-4 py-2 text-sm bg-sage-400 text-white rounded-lg hover:bg-sage-500"
            >
              + 建立專案
            </button>
          </div>
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="p-4 bg-white rounded-xl border border-cream-200 shadow-natural">
            <div className="text-2xl font-bold text-natural-700">{data.length}</div>
            <div className="text-xs text-natural-500">專案數</div>
          </div>
          <div className="p-4 bg-white rounded-xl border border-cream-200 shadow-natural">
            <div className="text-2xl font-bold text-sage-600">
              {data.reduce((sum, d) => sum + (d.plan?.profiles.length || 0), 0)}
            </div>
            <div className="text-xs text-natural-500">受訪者數</div>
          </div>
          <div className="p-4 bg-white rounded-xl border border-cream-200 shadow-natural">
            <div className="text-2xl font-bold text-emerald-600">
              {data.reduce((sum, d) => sum + d.sessions.length, 0)}
            </div>
            <div className="text-xs text-natural-500">訪談 Sessions</div>
          </div>
          <div className="p-4 bg-white rounded-xl border border-cream-200 shadow-natural">
            <div className="text-2xl font-bold text-amber-600">
              {data.reduce((sum, d) => sum + d.sessions.filter(s => s.status === 'ended').length, 0)}
            </div>
            <div className="text-xs text-natural-500">已完成訪談</div>
          </div>
        </div>

        {/* Project List */}
        {data.length === 0 ? (
          <div className="text-center py-12 text-natural-500">
            <p>尚無專案</p>
            <button
              onClick={() => navigate('/projects')}
              className="mt-3 px-4 py-2 bg-sage-400 text-white rounded-lg hover:bg-sage-500 text-sm"
            >
              建立第一個專案
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {data.map(({ project, plan, sessions }) => {
              const isExpanded = expandedProjects.has(project.id)
              const pStatus = projectStatusConfig[project.status] || projectStatusConfig.active
              const completedSessions = sessions.filter(s => s.status === 'ended').length
              const planProgress = plan?.summary.progress_percentage || 0

              return (
                <div key={project.id} className="bg-white rounded-xl border border-cream-200 shadow-natural overflow-hidden">
                  {/* Project Header */}
                  <div
                    className="p-5 cursor-pointer hover:bg-cream-50 transition-colors"
                    onClick={() => toggleProject(project.id)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <svg
                          className={`w-4 h-4 text-natural-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                          fill="none" viewBox="0 0 24 24" stroke="currentColor"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                        <h3 className="text-lg font-semibold text-natural-800">{project.title}</h3>
                        <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${pStatus.color}`}>
                          {pStatus.label}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-natural-400">
                        <span>受訪者 {plan?.profiles.length || 0}</span>
                        <span>訪談 {sessions.length} ({completedSessions} 完成)</span>
                        <span>進度 {Math.round(planProgress)}%</span>
                        <button
                          onClick={e => { e.stopPropagation(); navigate(`/projects/${project.id}`) }}
                          className="px-2 py-1 text-sage-600 hover:bg-sage-50 rounded"
                        >
                          管理
                        </button>
                      </div>
                    </div>
                    {project.description && (
                      <p className="text-sm text-natural-500 mt-1 ml-7">{project.description}</p>
                    )}
                    {/* Progress bar */}
                    <div className="mt-2 ml-7 h-1.5 bg-cream-100 rounded-full overflow-hidden max-w-xs">
                      <div
                        className="h-full bg-sage-400 rounded-full transition-all"
                        style={{ width: `${planProgress}%` }}
                      />
                    </div>
                  </div>

                  {/* Expanded: Sessions + Stakeholders */}
                  {isExpanded && (
                    <div className="border-t border-cream-200 px-5 pb-5">
                      {/* Stakeholder overview */}
                      {plan && plan.profiles.length > 0 && (
                        <div className="mt-4 mb-4">
                          <div className="text-xs font-medium text-natural-500 mb-2 uppercase tracking-wider">受訪者</div>
                          <div className="flex flex-wrap gap-2">
                            {plan.profiles.map(p => (
                              <span
                                key={p.id}
                                className={`px-2.5 py-1 text-xs rounded-full border ${
                                  p.status === 'interviewed'
                                    ? 'bg-green-50 border-green-200 text-green-700'
                                    : 'bg-cream-50 border-cream-200 text-natural-600'
                                }`}
                              >
                                {p.name}
                                <span className="text-natural-400 ml-1">
                                  {p.status === 'interviewed' ? '✓' : '○'}
                                </span>
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Sessions table */}
                      <div className="text-xs font-medium text-natural-500 mb-2 uppercase tracking-wider">訪談 Sessions</div>
                      {sessions.length === 0 ? (
                        <div className="text-sm text-natural-400 py-3">
                          尚無訪談 session。
                          <button
                            onClick={() => navigate(`/projects/${project.id}`)}
                            className="text-sage-600 hover:underline ml-1"
                          >
                            前往開始訪談
                          </button>
                        </div>
                      ) : (
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="border-b border-cream-200">
                                <th className="text-left py-2 pr-3 text-natural-500 font-medium">Session ID</th>
                                <th className="text-left py-2 pr-3 text-natural-500 font-medium">狀態</th>
                                <th className="text-left py-2 pr-3 text-natural-500 font-medium">建立時間</th>
                                <th className="text-right py-2 text-natural-500 font-medium">操作</th>
                              </tr>
                            </thead>
                            <tbody>
                              {sessions.map(session => {
                                const sConfig = statusConfig[session.status] || statusConfig.idle
                                return (
                                  <tr key={session.id} className="border-b border-cream-50 hover:bg-cream-50">
                                    <td className="py-2.5 pr-3">
                                      <span className="font-mono text-xs text-natural-600">
                                        {session.id.replace('session_', '').slice(0, 8)}
                                      </span>
                                    </td>
                                    <td className="py-2.5 pr-3">
                                      <span className={`px-2 py-0.5 text-xs rounded-full ${sConfig.color}`}>
                                        {sConfig.label}
                                      </span>
                                    </td>
                                    <td className="py-2.5 pr-3 text-xs text-natural-400">
                                      {new Date(session.createdAt).toLocaleString('zh-TW')}
                                    </td>
                                    <td className="py-2.5 text-right">
                                      <div className="flex items-center justify-end gap-2">
                                        {session.status === 'ended' && (
                                          <button
                                            onClick={() => navigate(`/sessions/${session.id}/insight-memo`)}
                                            className="px-2 py-0.5 text-xs text-sage-600 hover:bg-sage-50 rounded"
                                          >
                                            洞察
                                          </button>
                                        )}
                                        <button
                                          onClick={() => navigate(`/sessions/${session.id}/log`)}
                                          className="px-2 py-0.5 text-xs text-natural-500 hover:bg-cream-100 rounded"
                                        >
                                          Log
                                        </button>
                                        <button
                                          onClick={() => handleDeleteSession(session.id)}
                                          className="px-2 py-0.5 text-xs text-red-400 hover:bg-red-50 rounded"
                                        >
                                          刪除
                                        </button>
                                      </div>
                                    </td>
                                  </tr>
                                )
                              })}
                            </tbody>
                          </table>
                        </div>
                      )}

                      {/* Quick actions */}
                      <div className="flex gap-2 mt-4 pt-3 border-t border-cream-200">
                        <button
                          onClick={() => navigate(`/projects/${project.id}`)}
                          className="px-3 py-1.5 text-xs bg-sage-50 text-sage-700 rounded-lg hover:bg-sage-100"
                        >
                          專案詳情
                        </button>
                        <button
                          onClick={() => navigate(`/projects/${project.id}/evidence-matrix`)}
                          className="px-3 py-1.5 text-xs bg-cream-50 text-natural-600 rounded-lg hover:bg-cream-100"
                        >
                          證據矩陣
                        </button>
                        <button
                          onClick={() => navigate(`/projects/${project.id}/readiness`)}
                          className="px-3 py-1.5 text-xs bg-cream-50 text-natural-600 rounded-lg hover:bg-cream-100"
                        >
                          BRD 準備度
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
