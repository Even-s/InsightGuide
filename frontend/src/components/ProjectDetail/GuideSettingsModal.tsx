import { useState } from 'react'
import { generateInterviewGuide, type InterviewGuide, type InterviewGuideOptions } from '@/api/projects'

interface GuideSettingsModalProps {
  profileId: string
  projectId: string
  onClose: () => void
  onGenerated: (profileId: string, guide: InterviewGuide) => void
}

export function GuideSettingsModal({ profileId, projectId, onClose, onGenerated }: GuideSettingsModalProps) {
  const [guideOpts, setGuideOpts] = useState<InterviewGuideOptions>({ duration_minutes: 30 })
  const [generating, setGenerating] = useState(false)

  const handleGenerate = async () => {
    try {
      setGenerating(true)
      const cleanOpts: InterviewGuideOptions = { duration_minutes: guideOpts.duration_minutes }
      if (guideOpts.interview_purpose) cleanOpts.interview_purpose = guideOpts.interview_purpose
      if (guideOpts.focus_topics) cleanOpts.focus_topics = guideOpts.focus_topics
      if (guideOpts.exclude_topics) cleanOpts.exclude_topics = guideOpts.exclude_topics
      if (guideOpts.interview_style) cleanOpts.interview_style = guideOpts.interview_style
      const result = await generateInterviewGuide(projectId, profileId, cleanOpts)
      onGenerated(profileId, result)
      onClose()
    } catch (err) {
      console.error('Failed to generate guide:', err)
      alert('生成失敗，請稍後再試')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl p-6 w-full max-w-lg shadow-natural" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-natural-800 mb-1">訪談大綱設定</h3>
        <p className="text-sm text-natural-500 mb-4">調整後按「生成」，AI 會根據設定產生訪談問題卡片</p>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-natural-700 mb-1">預計訪談時長</label>
            <div className="flex gap-2">
              {[15, 30, 45, 60].map(min => (
                <button
                  key={min}
                  onClick={() => setGuideOpts(o => ({ ...o, duration_minutes: min }))}
                  className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                    guideOpts.duration_minutes === min
                      ? 'bg-sage-50 border-sage-300 text-sage-700'
                      : 'border-cream-200 text-natural-600 hover:bg-cream-50'
                  }`}
                >
                  {min} 分鐘
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-natural-700 mb-1">這次訪談目的</label>
            <input
              type="text"
              value={guideOpts.interview_purpose || ''}
              onChange={e => setGuideOpts(o => ({ ...o, interview_purpose: e.target.value }))}
              placeholder="例：了解現有銷售流程的痛點"
              className="w-full px-3 py-2 text-sm border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
            />
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {['初次探索', '深入追問', '驗證需求', '確認設計', '了解現況'].map(tag => (
                <button
                  key={tag}
                  onClick={() => setGuideOpts(o => ({ ...o, interview_purpose: tag }))}
                  className="px-2 py-0.5 text-xs bg-cream-100 text-natural-600 rounded hover:bg-sage-50 hover:text-sage-600"
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-natural-700 mb-1">聚焦主題</label>
            <input
              type="text"
              value={guideOpts.focus_topics || ''}
              onChange={e => setGuideOpts(o => ({ ...o, focus_topics: e.target.value }))}
              placeholder="例：庫存管理流程、客訴處理"
              className="w-full px-3 py-2 text-sm border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-natural-700 mb-1">排除主題（不要問）</label>
            <input
              type="text"
              value={guideOpts.exclude_topics || ''}
              onChange={e => setGuideOpts(o => ({ ...o, exclude_topics: e.target.value }))}
              placeholder="例：技術架構、資料庫設計"
              className="w-full px-3 py-2 text-sm border border-cream-300 rounded-lg focus:ring-2 focus:ring-sage-400"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-natural-700 mb-1">訪談風格</label>
            <div className="flex gap-2">
              {[
                { value: 'exploratory', label: '探索型', desc: '開放、廣泛' },
                { value: 'structured', label: '結構化', desc: '精確、逐項' },
                { value: 'validation', label: '驗證型', desc: '確認假設' },
              ].map(style => (
                <button
                  key={style.value}
                  onClick={() => setGuideOpts(o => ({ ...o, interview_style: style.value }))}
                  className={`flex-1 px-3 py-2 text-sm rounded-lg border transition-colors text-center ${
                    guideOpts.interview_style === style.value
                      ? 'bg-sage-50 border-sage-300 text-sage-700'
                      : 'border-cream-200 text-natural-600 hover:bg-cream-50'
                  }`}
                >
                  <div className="font-medium">{style.label}</div>
                  <div className="text-xs text-natural-400">{style.desc}</div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="px-4 py-2 bg-sage-400 text-white rounded-lg hover:bg-sage-500 text-sm font-medium disabled:opacity-50"
          >
            {generating ? '生成中...' : '生成訪談大綱'}
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-cream-100 text-natural-700 rounded-lg hover:bg-cream-200 text-sm"
          >
            取消
          </button>
        </div>
      </div>
    </div>
  )
}
