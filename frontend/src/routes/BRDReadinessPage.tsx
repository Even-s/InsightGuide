import { useCallback, useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { generateReadinessReport, getReadinessReport, type BRDReadinessReport } from '@/api/projects'

export default function BRDReadinessPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [report, setReport] = useState<BRDReadinessReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)

  const loadReport = useCallback(async () => {
    if (!projectId) return
    try {
      setLoading(true)
      const data = await getReadinessReport(projectId)
      setReport(data)
    } catch {
      setReport(null)
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => { loadReport() }, [loadReport])

  const handleGenerate = async () => {
    if (!projectId) return
    try {
      setGenerating(true)
      const data = await generateReadinessReport(projectId)
      setReport(data)
    } catch (err) {
      console.error('Failed to generate report:', err)
    } finally {
      setGenerating(false)
    }
  }

  if (loading) {
    return <div className="max-w-4xl mx-auto px-6 py-8 text-natural-500">載入中...</div>
  }

  if (!report) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-8">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => navigate(`/projects/${projectId}`)} className="text-natural-400 hover:text-natural-600">&larr;</button>
          <h1 className="text-2xl font-bold text-natural-800">BRD 準備度報告</h1>
        </div>
        <p className="text-natural-500 mb-4">尚未產生準備度報告。</p>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-4 py-2 bg-sage-400 text-white rounded-lg hover:bg-sage-500 disabled:opacity-50"
        >
          {generating ? '評估中...' : '執行準備度檢查'}
        </button>
      </div>
    )
  }

  const scorePercent = Math.round((report.readinessScore || 0) * 100)
  const scoreColor = scorePercent >= 75 ? 'text-green-600' : scorePercent >= 45 ? 'text-amber-600' : 'text-red-600'
  const ringColor = scorePercent >= 75 ? 'stroke-green-500' : scorePercent >= 45 ? 'stroke-amber-500' : 'stroke-red-500'

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate(`/projects/${projectId}`)} className="text-natural-400 hover:text-natural-600">&larr;</button>
        <h1 className="text-2xl font-bold text-natural-800">BRD 準備度報告</h1>
      </div>

      {/* Score + Verdict */}
      <div className="flex items-center gap-8 mb-8 p-6 bg-white rounded-xl border border-cream-200">
        <div className="relative w-24 h-24">
          <svg className="w-24 h-24 transform -rotate-90" viewBox="0 0 36 36">
            <path
              className="stroke-cream-200"
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              fill="none"
              strokeWidth="3"
            />
            <path
              className={ringColor}
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              fill="none"
              strokeWidth="3"
              strokeDasharray={`${scorePercent}, 100`}
              strokeLinecap="round"
            />
          </svg>
          <div className={`absolute inset-0 flex items-center justify-center text-xl font-bold ${scoreColor}`}>
            {scorePercent}%
          </div>
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-lg font-semibold ${scoreColor}`}>
              {report.generationMode === 'full' ? '可生成完整 BRD' :
               report.generationMode === 'partial' ? '可生成部分草稿' :
               '尚未準備好'}
            </span>
          </div>
          <p className="text-natural-600 text-sm">{report.recommendation}</p>
          <div className="flex gap-4 mt-3 text-xs text-natural-400">
            <span>訪談 {report.totalMemos} 場</span>
            <span>受訪者 {report.totalStakeholdersInterviewed} 位</span>
            <span>候選需求 {report.totalEvidenceEntries} 條</span>
            <span>已驗證 {report.validatedRequirements} 條</span>
          </div>
        </div>
      </div>

      {/* Stakeholder Coverage */}
      {report.stakeholderCoverage && (
        <div className="mb-6 p-4 bg-white rounded-xl border border-cream-200">
          <h3 className="text-sm font-semibold text-natural-700 mb-2">角色覆蓋度</h3>
          <div className="flex items-center gap-4">
            <div className="text-lg font-bold text-sage-600">
              {report.stakeholderCoverage.required_roles_covered}/{report.stakeholderCoverage.required_roles_total}
            </div>
            <div className="flex-1 h-2 bg-cream-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-sage-400 rounded-full"
                style={{ width: `${report.stakeholderCoverage.coverage_percentage}%` }}
              />
            </div>
            <span className="text-xs text-natural-400">
              {Math.round(report.stakeholderCoverage.coverage_percentage)}%
            </span>
          </div>
          {report.stakeholderCoverage.missing_roles.length > 0 && (
            <div className="mt-2 text-xs text-amber-600">
              缺少：{report.stakeholderCoverage.missing_roles.join(', ')}
            </div>
          )}
        </div>
      )}

      {/* Ready Sections */}
      {report.readySections.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-green-700 mb-2">已具備足夠證據</h3>
          <div className="space-y-2">
            {report.readySections.map((s, i) => (
              <div key={i} className="flex items-center gap-3 p-3 bg-green-50 rounded-lg">
                <span className="text-green-500">✓</span>
                <span className="text-sm font-medium text-natural-700">{s.section}</span>
                <span className="text-xs text-natural-400 ml-auto">{s.evidence_count} 條證據</span>
                <span className="text-xs text-green-600">{s.source_roles.join(', ')}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Insufficient Sections */}
      {report.insufficientSections.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-red-700 mb-2">證據不足</h3>
          <div className="space-y-2">
            {report.insufficientSections.map((s, i) => (
              <div key={i} className="flex items-center gap-3 p-3 bg-red-50 rounded-lg">
                <span className="text-red-400">✕</span>
                <div className="flex-1">
                  <span className="text-sm font-medium text-natural-700">{s.section}</span>
                  <span className="text-xs text-natural-500 ml-2">{s.reason}</span>
                </div>
                {s.missing_roles.length > 0 && (
                  <span className="text-xs text-red-500">缺: {s.missing_roles.join(', ')}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Conflicts */}
      {report.unresolvedConflicts.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-amber-700 mb-2">未解決衝突</h3>
          <div className="space-y-2">
            {report.unresolvedConflicts.map((c, i) => (
              <div key={i} className="p-3 bg-amber-50 rounded-lg">
                <div className="text-sm text-natural-700">{c.topic}</div>
                <div className="text-xs text-amber-600 mt-0.5">
                  衝突方：{c.conflicting_parties.join(' vs ')}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Suggestions */}
      {report.suggestedNextInterviews.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-sage-700 mb-2">建議下一輪訪談</h3>
          <div className="space-y-2">
            {report.suggestedNextInterviews.map((s, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-sage-50 rounded-lg">
                <div>
                  <span className="text-sm font-medium text-sage-700">{s.target_role}</span>
                  <span className="text-xs text-sage-600 ml-2">{s.objective}</span>
                </div>
                <span className={`px-2 py-0.5 text-xs rounded ${
                  s.urgency === 'high' ? 'bg-red-100 text-red-600' : 'bg-amber-100 text-amber-600'
                }`}>
                  {s.urgency === 'high' ? '急' : '中'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="pt-6 border-t border-cream-200 flex gap-3">
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-4 py-2 text-sm border border-cream-300 text-natural-600 rounded-lg hover:bg-cream-50 disabled:opacity-50"
        >
          {generating ? '重新評估中...' : '重新評估'}
        </button>
        {report.isReady && (
          <button
            onClick={() => navigate(`/projects/${projectId}/evidence-matrix`)}
            className="px-4 py-2 text-sm bg-sage-400 text-white rounded-lg hover:bg-sage-500"
          >
            查看證據矩陣
          </button>
        )}
      </div>
    </div>
  )
}
