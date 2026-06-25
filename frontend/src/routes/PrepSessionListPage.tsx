/**
 * Admin Backend Page - System Management
 * For debugging and technical management of all sessions
 * Hierarchy: Project → Stakeholder (as deck) → Interview Sessions
 */

import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  listProjects,
  getStakeholderPlan,
  getInterviewGuide,
  deleteProject,
  type Project,
  type StakeholderPlan,
  type StakeholderProfile,
  type InterviewGuide,
} from '@/api/projects'
import { interviewAPI } from '@/api/interview'
import type { InterviewSession } from '@/types/interview'

interface SessionInfo {
  id: string
  status: string
  startedAt?: string
  endedAt?: string
  createdAt: string
  costUsd: number
  documentId?: string
  projectId?: string
  stakeholderProfileId?: string
}

interface StakeholderWithGuide {
  profile: StakeholderProfile
  guide: InterviewGuide | null
  sessions: SessionInfo[]
}

interface ProjectData {
  project: Project
  plan: StakeholderPlan | null
  stakeholders: StakeholderWithGuide[]
}

function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  )
}

function ChevronRightIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  )
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
  )
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  )
}

export default function PrepSessionListPage() {
  const navigate = useNavigate()
  const [projectsData, setProjectsData] = useState<ProjectData[]>([])
  const [unlinkedSessions, setUnlinkedSessions] = useState<SessionInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set())
  const [expandedStakeholders, setExpandedStakeholders] = useState<Set<string>>(new Set())
  const [lastRefreshTime, setLastRefreshTime] = useState<Date>(new Date())

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      const { projects } = await listProjects()

      const data: ProjectData[] = await Promise.all(
        projects.map(async (project) => {
          try {
            const plan = await getStakeholderPlan(project.id)

            const stakeholders: StakeholderWithGuide[] = await Promise.all(
              plan.profiles.map(async (profile) => {
                let guide: InterviewGuide | null = null
                try {
                  guide = await getInterviewGuide(project.id, profile.id)
                } catch { /* no guide yet */ }

                let sessions: SessionInfo[] = []
                try {
                  const res = await interviewAPI.listSessions({ projectId: project.id, limit: 50 })
                  sessions = res.sessions
                    .filter((s: InterviewSession) => s.stakeholderProfileId === profile.id || !s.stakeholderProfileId)
                    .map((s: InterviewSession) => ({
                      id: s.id,
                      status: s.status,
                      startedAt: s.startedAt,
                      endedAt: s.endedAt,
                      createdAt: s.createdAt,
                      costUsd: 0,
                      documentId: s.documentId,
                      projectId: s.projectId,
                      stakeholderProfileId: s.stakeholderProfileId,
                    }))
                } catch { /* no sessions */ }

                return { profile, guide, sessions }
              })
            )

            return { project, plan, stakeholders }
          } catch {
            return { project, plan: null, stakeholders: [] }
          }
        })
      )

      setProjectsData(data)

      // Load unlinked sessions (no projectId)
      try {
        const res = await interviewAPI.listSessions({ limit: 50 })
        const unlinked = res.sessions
          .filter((s: InterviewSession) => !s.projectId)
          .map((s: InterviewSession) => ({
            id: s.id,
            status: s.status,
            startedAt: s.startedAt,
            endedAt: s.endedAt,
            createdAt: s.createdAt,
            costUsd: 0,
            documentId: s.documentId,
            projectId: s.projectId,
            stakeholderProfileId: s.stakeholderProfileId,
          }))
        setUnlinkedSessions(unlinked)
      } catch { /* ignore */ }

      setLastRefreshTime(new Date())
    } catch (err) {
      console.error('Failed to load data:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const toggleProject = (id: string) => {
    setExpandedProjects(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleStakeholder = (id: string) => {
    setExpandedStakeholders(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const handleDeleteSession = async (sessionId: string) => {
    if (!confirm('確定要刪除此訪談 session？')) return
    try {
      await interviewAPI.deleteSession(sessionId)
      loadData()
    } catch (err) {
      console.error('Failed to delete:', err)
      alert('刪除失敗：' + (err instanceof Error ? err.message : 'Unknown error'))
    }
  }

  const handleForceEndSession = async (sessionId: string) => {
    if (!confirm('強制結束此 session？狀態將變為 ended。')) return
    try {
      await interviewAPI.forceEndSession(sessionId)
      loadData()
    } catch (err) {
      console.error('Failed to force end session:', err)
      alert('操作失敗：' + (err instanceof Error ? err.message : 'Unknown error'))
    }
  }

  const handleDeleteProject = async (projectId: string) => {
    if (!confirm('確定要刪除此專案？所有訪談記錄將一併刪除。')) return
    try {
      await deleteProject(projectId)
      loadData()
    } catch (err) {
      console.error('Failed to delete project:', err)
      alert('刪除專案失敗：' + (err instanceof Error ? err.message : 'Unknown error'))
    }
  }

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  }

  const formatDuration = (startedAt?: string, endedAt?: string) => {
    if (!startedAt || !endedAt) return '-'
    const seconds = Math.floor((new Date(endedAt).getTime() - new Date(startedAt).getTime()) / 1000)
    return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  }

  const sessionStatusColor: Record<string, string> = {
    idle: 'bg-cream-100 text-natural-600',
    interviewing: 'bg-green-50 text-green-700',
    paused: 'bg-amber-50 text-amber-700',
    ended: 'bg-blue-50 text-blue-600',
    failed: 'bg-red-50 text-red-600',
  }

  // Stats
  const totalProjects = projectsData.length
  const totalStakeholders = projectsData.reduce((s, p) => s + p.stakeholders.length, 0)
  const totalSessions = projectsData.reduce((s, p) => s + p.stakeholders.reduce((ss, st) => ss + st.sessions.length, 0), 0) + unlinkedSessions.length
  const completedSessions = projectsData.reduce((s, p) => s + p.stakeholders.reduce((ss, st) => ss + st.sessions.filter(se => se.status === 'ended').length, 0), 0) + unlinkedSessions.filter(s => s.status === 'ended').length
  const activeSessions = projectsData.reduce((s, p) => s + p.stakeholders.reduce((ss, st) => ss + st.sessions.filter(se => se.status === 'interviewing' || se.status === 'paused').length, 0), 0) + unlinkedSessions.filter(s => s.status === 'interviewing' || s.status === 'paused').length
  const errorSessions = projectsData.reduce((s, p) => s + p.stakeholders.reduce((ss, st) => ss + st.sessions.filter(se => se.status === 'failed').length, 0), 0) + unlinkedSessions.filter(s => s.status === 'failed').length

  if (loading) {
    return (
      <div className="min-h-screen bg-cream-100 flex items-center justify-center">
        <div className="text-natural-500">載入中...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-cream-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-2xl font-bold text-natural-800">系統管理後台</h1>
            <p className="text-natural-500 mt-1">管理者視角：所有專案、受訪者、訪談 Sessions 技術狀態</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-xs text-natural-400">最後更新</div>
              <div className="text-xs text-natural-600 font-mono">
                {lastRefreshTime.toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </div>
            </div>
            <button
              onClick={loadData}
              className="px-3 py-2 bg-natural-200 text-natural-700 rounded-lg hover:bg-natural-300 text-sm flex items-center gap-1"
              disabled={loading}
            >
              <RefreshIcon className="w-4 h-4" />
              刷新
            </button>
            <button
              onClick={() => navigate('/projects')}
              className="px-4 py-2 bg-sage-400 text-white rounded-lg hover:bg-sage-500 text-sm"
            >
              用戶視圖
            </button>
            <button
              onClick={() => navigate('/')}
              className="px-4 py-2 bg-natural-600 text-white rounded-lg hover:bg-natural-700 text-sm"
            >
              回首頁
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-6 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-cream-200 p-4">
            <div className="text-2xl font-bold text-natural-700">{totalProjects}</div>
            <div className="text-xs text-natural-500">專案</div>
          </div>
          <div className="bg-white rounded-xl border border-cream-200 p-4">
            <div className="text-2xl font-bold text-sage-600">{totalStakeholders}</div>
            <div className="text-xs text-natural-500">受訪者</div>
          </div>
          <div className="bg-white rounded-xl border border-cream-200 p-4">
            <div className="text-2xl font-bold text-emerald-600">{totalSessions}</div>
            <div className="text-xs text-natural-500">全部 Sessions</div>
          </div>
          <div className="bg-white rounded-xl border border-cream-200 p-4">
            <div className="text-2xl font-bold text-blue-600">{completedSessions}</div>
            <div className="text-xs text-natural-500">已完成</div>
          </div>
          <div className="bg-white rounded-xl border border-cream-200 p-4">
            <div className="text-2xl font-bold text-amber-600">{activeSessions}</div>
            <div className="text-xs text-natural-500">進行中</div>
          </div>
          <div className="bg-white rounded-xl border border-cream-200 p-4">
            <div className="text-2xl font-bold text-red-600">{errorSessions}</div>
            <div className="text-xs text-natural-500">錯誤</div>
          </div>
        </div>

        {/* Empty state */}
        {projectsData.length === 0 && (
          <div className="text-center py-12 bg-white rounded-xl border border-cream-200">
            <p className="text-natural-500 mb-3">尚無專案</p>
            <button onClick={() => navigate('/')} className="text-sage-600 hover:underline text-sm">
              建立第一個專案
            </button>
          </div>
        )}

        {/* Project hierarchy */}
        <div className="space-y-4">
          {projectsData.map(({ project, stakeholders }) => {
            const isProjectExpanded = expandedProjects.has(project.id)
            const projectSessions = stakeholders.reduce((s, st) => s + st.sessions.length, 0)
            const projectCompleted = stakeholders.reduce((s, st) => s + st.sessions.filter(se => se.status === 'ended').length, 0)

            return (
              <div key={project.id} className="bg-white rounded-xl border border-cream-200 overflow-hidden">
                {/* Project row */}
                <div
                  className="px-5 py-4 cursor-pointer hover:bg-cream-50 transition-colors flex items-center gap-3"
                  onClick={() => toggleProject(project.id)}
                >
                  {isProjectExpanded ? (
                    <ChevronDownIcon className="w-4 h-4 text-natural-400 flex-shrink-0" />
                  ) : (
                    <ChevronRightIcon className="w-4 h-4 text-natural-400 flex-shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <h3 className="text-base font-semibold text-natural-800 truncate">{project.title}</h3>
                      <span className="px-2 py-0.5 text-xs bg-sage-50 text-sage-600 rounded-full">
                        {stakeholders.length} 受訪者
                      </span>
                    </div>
                    {project.description && (
                      <p className="text-xs text-natural-400 mt-0.5 truncate">{project.description}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-4 text-xs text-natural-400 flex-shrink-0">
                    <span>{projectSessions} 訪談</span>
                    <span>{projectCompleted} 完成</span>
                    <button
                      onClick={e => { e.stopPropagation(); navigate(`/projects/${project.id}`) }}
                      className="px-2 py-1 text-sage-600 hover:bg-sage-50 rounded"
                    >
                      管理
                    </button>
                    <button
                      onClick={e => { e.stopPropagation(); handleDeleteProject(project.id) }}
                      className="px-2 py-1 text-red-500 hover:bg-red-50 rounded"
                      title="刪除專案"
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Expanded: Stakeholders */}
                {isProjectExpanded && (
                  <div className="border-t border-cream-200">
                    {stakeholders.length === 0 ? (
                      <div className="px-10 py-4 text-sm text-natural-400">
                        尚無受訪者。
                        <button onClick={() => navigate(`/projects/${project.id}`)} className="text-sage-600 hover:underline ml-1">
                          前往新增
                        </button>
                      </div>
                    ) : (
                      stakeholders.map(({ profile, guide, sessions }) => {
                        const isStakeholderExpanded = expandedStakeholders.has(profile.id)
                        const hasGuide = !!guide
                        const cardCount = guide?.card_count || 0

                        return (
                          <div key={profile.id} className="border-b border-cream-100 last:border-b-0">
                            {/* Stakeholder row */}
                            <div
                              className="px-10 py-3 cursor-pointer hover:bg-cream-50 transition-colors flex items-center gap-3"
                              onClick={() => toggleStakeholder(profile.id)}
                            >
                              {isStakeholderExpanded ? (
                                <ChevronDownIcon className="w-3.5 h-3.5 text-natural-400 flex-shrink-0" />
                              ) : (
                                <ChevronRightIcon className="w-3.5 h-3.5 text-natural-400 flex-shrink-0" />
                              )}
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <span className="text-sm font-medium text-natural-700">{profile.name}</span>
                                  {profile.roleTitle && (
                                    <span className="text-xs text-natural-400">{profile.roleTitle}</span>
                                  )}
                                  <span className={`px-1.5 py-0.5 text-xs rounded ${
                                    profile.status === 'interviewed' ? 'bg-green-50 text-green-700' :
                                    'bg-cream-100 text-natural-500'
                                  }`}>
                                    {profile.status === 'interviewed' ? '已訪' : '待訪'}
                                  </span>
                                  {hasGuide && (
                                    <span className="px-1.5 py-0.5 text-xs bg-blue-50 text-blue-600 rounded">
                                      {cardCount} 卡
                                    </span>
                                  )}
                                </div>
                              </div>
                              <div className="flex items-center gap-2 text-xs flex-shrink-0">
                                <span className="text-natural-400">{sessions.length} 次訪談</span>
                                {hasGuide ? (
                                  <>
                                    <button
                                      onClick={e => { e.stopPropagation(); navigate(`/editor/${guide!.document_id}`) }}
                                      className="px-2 py-0.5 text-sage-600 hover:bg-sage-50 rounded"
                                    >
                                      編輯大綱
                                    </button>
                                    <button
                                      onClick={e => {
                                        e.stopPropagation()
                                        navigate(`/interview/${guide!.document_id}?projectId=${project.id}&stakeholderId=${profile.id}`)
                                      }}
                                      className="px-2 py-0.5 bg-sage-400 text-white rounded hover:bg-sage-500"
                                    >
                                      訪談
                                    </button>
                                  </>
                                ) : (
                                  <span className="text-amber-500">未生成大綱</span>
                                )}
                              </div>
                            </div>

                            {/* Expanded: Sessions */}
                            {isStakeholderExpanded && (
                              <div className="px-16 pb-3">
                                {sessions.length === 0 ? (
                                  <div className="text-xs text-natural-400 py-2">尚無訪談紀錄</div>
                                ) : (
                                  <table className="w-full text-xs">
                                    <thead>
                                      <tr className="text-natural-400 border-b border-cream-200">
                                        <th className="text-left py-1.5 pr-3">Session ID (完整)</th>
                                        <th className="text-left py-1.5 pr-3">狀態</th>
                                        <th className="text-left py-1.5 pr-3">Document ID</th>
                                        <th className="text-left py-1.5 pr-3">開始</th>
                                        <th className="text-left py-1.5 pr-3">時長</th>
                                        <th className="text-left py-1.5 pr-3">花費</th>
                                        <th className="text-right py-1.5">操作</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {sessions.map(session => (
                                        <tr key={session.id} className="border-b border-cream-100">
                                          <td className="py-1.5 pr-3 font-mono text-natural-500 text-[10px]">
                                            {session.id}
                                          </td>
                                          <td className="py-1.5 pr-3">
                                            <span className={`px-1.5 py-0.5 rounded text-xs ${sessionStatusColor[session.status] || 'bg-cream-100 text-natural-600'}`}>
                                              {session.status}
                                            </span>
                                          </td>
                                          <td className="py-1.5 pr-3 font-mono text-natural-400 text-[10px]">
                                            {session.documentId ? session.documentId.slice(0, 12) + '...' : '-'}
                                          </td>
                                          <td className="py-1.5 pr-3 text-natural-500">{formatDate(session.startedAt)}</td>
                                          <td className="py-1.5 pr-3 text-natural-500">{formatDuration(session.startedAt, session.endedAt)}</td>
                                          <td className="py-1.5 pr-3 text-natural-500">${session.costUsd.toFixed(4)}</td>
                                          <td className="py-1.5 text-right">
                                            <div className="flex items-center justify-end gap-1">
                                              {(session.status === 'interviewing' || session.status === 'paused') && (
                                                <button
                                                  onClick={() => handleForceEndSession(session.id)}
                                                  className="px-1.5 py-0.5 text-amber-600 hover:bg-amber-50 rounded text-[10px]"
                                                  title="強制結束"
                                                >
                                                  強制結束
                                                </button>
                                              )}
                                              {session.status === 'ended' && (
                                                <button
                                                  onClick={() => navigate(`/sessions/${session.id}/insight-memo`)}
                                                  className="px-1.5 py-0.5 text-sage-600 hover:bg-sage-50 rounded"
                                                >
                                                  洞察
                                                </button>
                                              )}
                                              <button
                                                onClick={() => navigate(`/sessions/${session.id}/log`)}
                                                className="px-1.5 py-0.5 text-natural-400 hover:bg-cream-100 rounded"
                                              >
                                                Log
                                              </button>
                                              <button
                                                onClick={() => handleDeleteSession(session.id)}
                                                className="text-red-300 hover:text-red-500"
                                              >
                                                <TrashIcon className="w-3.5 h-3.5" />
                                              </button>
                                            </div>
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                )}
                              </div>
                            )}
                          </div>
                        )
                      })
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Unlinked Sessions (no project) */}
        {unlinkedSessions.length > 0 && (
          <div className="mt-6 bg-white rounded-xl border border-dashed border-cream-300 overflow-hidden">
            <div className="px-5 py-4">
              <h3 className="text-base font-semibold text-natural-500">未歸屬專案的訪談</h3>
              <p className="text-xs text-natural-400 mt-0.5">這些訪談未關聯到任何專案（技術除錯用）</p>
            </div>
            <div className="border-t border-cream-200 px-5 pb-4">
              <table className="w-full text-xs mt-2">
                <thead>
                  <tr className="text-natural-400 border-b border-cream-200">
                    <th className="text-left py-1.5 pr-3">Session ID (完整)</th>
                    <th className="text-left py-1.5 pr-3">狀態</th>
                    <th className="text-left py-1.5 pr-3">Document ID</th>
                    <th className="text-left py-1.5 pr-3">時間</th>
                    <th className="text-left py-1.5 pr-3">花費</th>
                    <th className="text-right py-1.5">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {unlinkedSessions.map(session => (
                    <tr key={session.id} className="border-b border-cream-100">
                      <td className="py-1.5 pr-3 font-mono text-natural-500 text-[10px]">
                        {session.id}
                      </td>
                      <td className="py-1.5 pr-3">
                        <span className={`px-1.5 py-0.5 rounded text-xs ${sessionStatusColor[session.status] || 'bg-cream-100 text-natural-600'}`}>
                          {session.status}
                        </span>
                      </td>
                      <td className="py-1.5 pr-3 font-mono text-natural-400 text-[10px]">
                        {session.documentId ? session.documentId.slice(0, 12) + '...' : '-'}
                      </td>
                      <td className="py-1.5 pr-3 text-natural-500">{formatDate(session.createdAt)}</td>
                      <td className="py-1.5 pr-3 text-natural-500">${session.costUsd.toFixed(4)}</td>
                      <td className="py-1.5 text-right">
                        <div className="flex items-center justify-end gap-1">
                          {(session.status === 'interviewing' || session.status === 'paused') && (
                            <button
                              onClick={() => handleForceEndSession(session.id)}
                              className="px-1.5 py-0.5 text-amber-600 hover:bg-amber-50 rounded text-[10px]"
                              title="強制結束"
                            >
                              強制結束
                            </button>
                          )}
                          {session.status === 'ended' && (
                            <button
                              onClick={() => navigate(`/sessions/${session.id}/insight-memo`)}
                              className="px-1.5 py-0.5 text-sage-600 hover:bg-sage-50 rounded"
                            >
                              洞察
                            </button>
                          )}
                          <button
                            onClick={() => navigate(`/sessions/${session.id}/log`)}
                            className="px-1.5 py-0.5 text-natural-400 hover:bg-cream-100 rounded"
                          >
                            Log
                          </button>
                          <button
                            onClick={() => handleDeleteSession(session.id)}
                            className="text-red-300 hover:text-red-500"
                          >
                            <TrashIcon className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
