import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { generateInterviewGuide, type StakeholderPlan, type InterviewGuide } from '@/api/projects'

interface StartInterviewModalProps {
  plan: StakeholderPlan
  projectId: string
  guideStatuses: Record<string, InterviewGuide | null>
  onClose: () => void
  onGuideGenerated: (profileId: string, guide: InterviewGuide) => void
}

export function StartInterviewModal({ plan, projectId, guideStatuses, onClose, onGuideGenerated }: StartInterviewModalProps) {
  const navigate = useNavigate()
  const [loadingPreps, setLoadingPreps] = useState(false)

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-natural" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-natural-800 mb-2">開始新訪談</h3>
        <p className="text-sm text-natural-500 mb-4">選擇受訪者後開始訪談。若尚未產生訪談大綱，將先自動產生。</p>

        {plan.profiles.filter(p => p.status !== 'unavailable').length === 0 ? (
          <div className="text-sm text-natural-500 py-4 text-center">
            尚無可用受訪者，請先新增受訪者。
          </div>
        ) : (
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {plan.profiles.filter(p => p.status !== 'unavailable').map(profile => {
              const guide = guideStatuses[profile.id]
              return (
                <button
                  key={profile.id}
                  onClick={async () => {
                    try {
                      setLoadingPreps(true)
                      let finalGuide = guide
                      if (!finalGuide) {
                        finalGuide = await generateInterviewGuide(projectId, profile.id)
                        onGuideGenerated(profile.id, finalGuide)
                      }
                      onClose()
                      navigate(`/interview/${finalGuide.document_id}?projectId=${projectId}&stakeholderId=${profile.id}`)
                    } catch (err) {
                      console.error('Failed to start interview:', err)
                      alert('訪談大綱產生失敗，請稍後再試')
                    } finally {
                      setLoadingPreps(false)
                    }
                  }}
                  disabled={loadingPreps}
                  className="w-full p-3 text-left bg-cream-50 rounded-xl hover:bg-sage-50 hover:border-sage-200 border border-cream-200 transition-colors disabled:opacity-50"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-sm font-medium text-natural-700">{profile.name}</span>
                      {profile.roleTitle && (
                        <span className="text-xs text-natural-400 ml-2">{profile.roleTitle}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`px-1.5 py-0.5 text-xs rounded ${
                        profile.status === 'interviewed' ? 'bg-green-50 text-green-700' : 'bg-cream-100 text-natural-600'
                      }`}>
                        {profile.status === 'interviewed' ? '已訪' : '待訪'}
                      </span>
                      {guide && (
                        <span className="px-1.5 py-0.5 text-xs bg-blue-50 text-blue-700 rounded">
                          {guide.card_count} 卡
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-xs text-natural-400 mt-0.5">
                    {profile.stakeholderType} {profile.department ? `· ${profile.department}` : ''}
                    {!guide && <span className="text-amber-500 ml-2">(將自動產生大綱)</span>}
                  </div>
                </button>
              )
            })}
          </div>
        )}
        <div className="flex gap-3 mt-4">
          <button
            onClick={onClose}
            className="px-3 py-2 text-sm text-natural-500 bg-cream-100 rounded-lg hover:bg-cream-200 ml-auto"
          >
            取消
          </button>
        </div>
      </div>
    </div>
  )
}
