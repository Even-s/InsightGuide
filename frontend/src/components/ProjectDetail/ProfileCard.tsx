import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { interviewAPI } from '@/api/interview'
import type { StakeholderProfile, InterviewGuide } from '@/api/projects'

interface ProfileCardProps {
  profile: StakeholderProfile
  projectId: string
  guide: InterviewGuide | null
  onDelete: (profileId: string) => void
  onShowGuideSettings: (profileId: string) => void
}

export function ProfileCard({ profile, projectId, guide, onDelete, onShowGuideSettings }: ProfileCardProps) {
  const navigate = useNavigate()
  const guideReady = guide && guide.card_count > 0
  const [latestRecordSessionId, setLatestRecordSessionId] = useState<string | null>(null)
  const [openingRecord, setOpeningRecord] = useState(false)
  const [recordError, setRecordError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    interviewAPI.listSessions({ projectId, stakeholderProfileId: profile.id, limit: 50 })
      .then(result => {
        if (cancelled) return
        setLatestRecordSessionId(findLatestRecordSessionId(result.sessions, profile.id))
      })
      .catch(() => {
        // Keep the card usable. A click will retry and show a visible error if needed.
      })

    return () => { cancelled = true }
  }, [profile.id, projectId])

  const openLatestInterviewRecord = async () => {
    if (openingRecord) return
    if (latestRecordSessionId) {
      navigate(`/sessions/${latestRecordSessionId}/insight-memo`)
      return
    }

    setOpeningRecord(true)
    setRecordError(null)

    try {
      const result = await interviewAPI.listSessions({
        projectId,
        stakeholderProfileId: profile.id,
        limit: 50,
      })
      const targetSessionId = findLatestRecordSessionId(result.sessions, profile.id)

      if (!targetSessionId) {
        setRecordError('找不到可開啟的訪談紀錄')
        return
      }

      setLatestRecordSessionId(targetSessionId)
      navigate(`/sessions/${targetSessionId}/insight-memo`)
    } catch {
      setRecordError('載入訪談紀錄失敗')
    } finally {
      setOpeningRecord(false)
    }
  }

  return (
    <div className="motion-surface-in p-3 bg-white rounded-xl border border-cream-200 hover:border-cream-300 shadow-natural transition-colors">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
            profile.status === 'interviewed' ? 'bg-green-50 text-green-700' :
            'bg-cream-100 text-natural-600'
          }`}>
            {profile.name.charAt(0)}
          </div>
          <div>
            <span className="text-sm font-medium text-natural-700">{profile.name}</span>
            {profile.roleTitle && (
              <span className="text-xs text-natural-400 ml-2">{profile.roleTitle}</span>
            )}
          </div>
          <span className={`px-1.5 py-0.5 text-xs rounded ${
            profile.status === 'interviewed' ? 'bg-green-50 text-green-700' :
            profile.status === 'unavailable' ? 'bg-red-50 text-red-600' :
            'bg-cream-100 text-natural-500'
          }`}>
            {profile.status === 'interviewed' ? '已訪' :
             profile.status === 'unavailable' ? '無法' : '待訪'}
          </span>
          {guideReady && (
            <span className="px-1.5 py-0.5 text-xs bg-blue-50 text-blue-600 rounded">
              {guide.card_count} 張卡片
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {guideReady ? (
            <button
              onClick={() => navigate(`/editor/${guide.document_id}`)}
              className="px-2.5 py-1 text-xs bg-sage-400 text-white rounded-lg hover:bg-sage-500"
            >
              編輯訪談大綱
            </button>
          ) : (
            <button
              onClick={() => onShowGuideSettings(profile.id)}
              className="px-2.5 py-1 text-xs bg-sage-50 text-sage-700 rounded-lg hover:bg-sage-100"
            >
              {guide ? '重新生成大綱' : '生成訪談大綱'}
            </button>
          )}
          {(latestRecordSessionId || profile.interviewCount > 0) && (
            <button
              type="button"
              onClick={openLatestInterviewRecord}
              disabled={openingRecord}
              className="rounded-lg border border-cream-300 bg-white px-2.5 py-1 text-xs font-medium text-natural-600 hover:border-sage-200 hover:bg-sage-50 hover:text-sage-600 disabled:cursor-wait disabled:opacity-50"
            >
              {openingRecord ? '載入中…' : '訪談紀錄'}
            </button>
          )}
          <button
            onClick={() => onDelete(profile.id)}
            className="p-1 text-natural-400 hover:text-red-400"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
      {profile.department && (
        <div className="text-xs text-natural-400 mt-1 ml-8">{profile.department}</div>
      )}
      {recordError && (
        <p className="mt-2 ml-8 text-xs text-red-500" role="alert">{recordError}</p>
      )}
    </div>
  )
}

function findLatestRecordSessionId(
  sessions: Awaited<ReturnType<typeof interviewAPI.listSessions>>['sessions'],
  profileId: string,
) {
  const profileSessions = sessions
    .filter(session => session.stakeholderProfileId === profileId)
    .sort((a, b) => {
      const aTime = new Date(a.endedAt || a.startedAt || a.createdAt || 0).getTime()
      const bTime = new Date(b.endedAt || b.startedAt || b.createdAt || 0).getTime()
      return bTime - aTime
    })

  return profileSessions.find(session => session.status === 'ended')?.id
    || profileSessions[0]?.id
    || null
}
