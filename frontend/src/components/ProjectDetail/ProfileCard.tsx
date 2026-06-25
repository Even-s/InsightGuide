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

  return (
    <div className="p-3 bg-white rounded-xl border border-cream-200 hover:border-cream-300 shadow-natural transition-colors">
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
            <>
              <button
                onClick={() => navigate(`/editor/${guide.document_id}`)}
                className="px-2.5 py-1 text-xs bg-sage-400 text-white rounded-lg hover:bg-sage-500"
              >
                編輯訪談大綱
              </button>
              {profile.interviewCount > 0 && (
                <button
                  onClick={() => {
                    interviewAPI.listSessions({ projectId, limit: 50 })
                      .then(res => {
                        const profileSession = res.sessions.find(s => s.stakeholderProfileId === profile.id)
                        if (profileSession) navigate(`/sessions/${profileSession.id}/insight-memo`)
                      })
                  }}
                  className="px-2 py-1 text-xs text-natural-600 hover:bg-cream-100 rounded"
                >
                  訪談紀錄
                </button>
              )}
            </>
          ) : (
            <button
              onClick={() => onShowGuideSettings(profile.id)}
              className="px-2.5 py-1 text-xs bg-sage-50 text-sage-700 rounded-lg hover:bg-sage-100"
            >
              {guide ? '重新生成大綱' : '生成訪談大綱'}
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
    </div>
  )
}
