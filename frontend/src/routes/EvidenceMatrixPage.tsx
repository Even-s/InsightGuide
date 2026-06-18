import { useCallback, useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getEvidenceMatrix,
  refreshEvidenceMatrix,
  updateEvidenceMatrixEntry,
  type EvidenceMatrixResponse,
} from '@/api/projects'

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; color: string }> = {
    validated: { label: '已驗證', color: 'bg-green-100 text-green-700' },
    conflicted: { label: '有衝突', color: 'bg-red-100 text-red-700' },
    needs_more_evidence: { label: '待補證', color: 'bg-amber-100 text-amber-700' },
    candidate: { label: '候選', color: 'bg-cream-100 text-natural-600' },
    rejected: { label: '已排除', color: 'bg-cream-100 text-natural-400 line-through' },
  }
  const info = map[status] || { label: status, color: 'bg-cream-100 text-natural-600' }
  return (
    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${info.color}`}>
      {info.label}
    </span>
  )
}

function AgreementBadge({ level }: { level?: string }) {
  if (!level) return null
  const map: Record<string, { label: string; color: string }> = {
    unanimous: { label: '一致', color: 'text-green-600' },
    majority: { label: '多數', color: 'text-blue-600' },
    single_source: { label: '單一來源', color: 'text-natural-400' },
    conflicted: { label: '衝突', color: 'text-red-600' },
  }
  const info = map[level] || { label: level, color: 'text-natural-500' }
  return <span className={`text-xs ${info.color}`}>{info.label}</span>
}

export default function EvidenceMatrixPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<EvidenceMatrixResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [expandedEntry, setExpandedEntry] = useState<string | null>(null)
  const [filterStatus, setFilterStatus] = useState<string>('all')

  const loadMatrix = useCallback(async () => {
    if (!projectId) return
    try {
      setLoading(true)
      const result = await getEvidenceMatrix(projectId)
      setData(result)
    } catch (err) {
      console.error('Failed to load matrix:', err)
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => { loadMatrix() }, [loadMatrix])

  const handleRefresh = async () => {
    if (!projectId) return
    try {
      setRefreshing(true)
      const result = await refreshEvidenceMatrix(projectId)
      setData(result)
    } catch (err) {
      console.error('Failed to refresh:', err)
    } finally {
      setRefreshing(false)
    }
  }

  const handleReject = async (entryId: string) => {
    try {
      await updateEvidenceMatrixEntry(entryId, { validation_status: 'rejected' })
      loadMatrix()
    } catch (err) {
      console.error('Failed to update entry:', err)
    }
  }

  if (loading) {
    return <div className="max-w-6xl mx-auto px-6 py-8 text-natural-500">載入中...</div>
  }

  const entries = data?.entries || []
  const summary = data?.summary
  const filteredEntries = filterStatus === 'all'
    ? entries
    : entries.filter(e => e.validationStatus === filterStatus)

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(`/projects/${projectId}`)} className="text-natural-400 hover:text-natural-600">&larr;</button>
          <h1 className="text-2xl font-bold text-natural-800">需求證據矩陣</h1>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="px-4 py-2 bg-sage-400 text-white rounded-lg hover:bg-sage-500 disabled:opacity-50 text-sm"
        >
          {refreshing ? '刷新中...' : '刷新矩陣'}
        </button>
      </div>

      {/* Summary */}
      {summary && summary.total_candidates > 0 && (
        <div className="grid grid-cols-5 gap-3 mb-6">
          <div className="p-3 bg-white rounded-xl border border-cream-200 text-center">
            <div className="text-xl font-bold text-natural-700">{summary.total_candidates}</div>
            <div className="text-xs text-natural-500">候選需求</div>
          </div>
          <div className="p-3 bg-white rounded-xl border border-cream-200 text-center">
            <div className="text-xl font-bold text-green-600">{summary.validated}</div>
            <div className="text-xs text-natural-500">已驗證</div>
          </div>
          <div className="p-3 bg-white rounded-xl border border-cream-200 text-center">
            <div className="text-xl font-bold text-amber-600">{summary.needs_more_evidence}</div>
            <div className="text-xs text-natural-500">待補證</div>
          </div>
          <div className="p-3 bg-white rounded-xl border border-cream-200 text-center">
            <div className="text-xl font-bold text-red-600">{summary.conflicted}</div>
            <div className="text-xs text-natural-500">有衝突</div>
          </div>
          <div className="p-3 bg-white rounded-xl border border-cream-200 text-center">
            <div className="text-xl font-bold text-sage-600">{summary.memo_count}</div>
            <div className="text-xs text-natural-500">訪談來源</div>
          </div>
        </div>
      )}

      {/* Roles info */}
      {summary && summary.roles_missing.length > 0 && (
        <div className="mb-6 p-3 bg-amber-50 border border-amber-200 rounded-lg">
          <span className="text-sm text-amber-800 font-medium">缺少角色驗證：</span>
          <span className="text-sm text-amber-700 ml-2">{summary.roles_missing.join(', ')}</span>
        </div>
      )}

      {/* Filter */}
      <div className="flex gap-2 mb-4">
        {['all', 'validated', 'needs_more_evidence', 'conflicted', 'candidate'].map(s => (
          <button
            key={s}
            onClick={() => setFilterStatus(s)}
            className={`px-3 py-1 text-xs rounded-full border transition-colors ${
              filterStatus === s
                ? 'bg-sage-50 border-sage-200 text-sage-700'
                : 'bg-white border-cream-200 text-natural-600 hover:bg-cream-50'
            }`}
          >
            {s === 'all' ? '全部' : s === 'validated' ? '已驗證' : s === 'needs_more_evidence' ? '待補證' : s === 'conflicted' ? '有衝突' : '候選'}
          </button>
        ))}
      </div>

      {/* Entries */}
      {filteredEntries.length === 0 ? (
        <div className="text-center py-12 text-natural-500">
          {entries.length === 0 ? '尚無資料。請先完成訪談並產生洞察紀錄，再刷新矩陣。' : '此篩選條件下無結果。'}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredEntries.map(entry => (
            <div
              key={entry.id}
              className="p-4 bg-white rounded-xl border border-cream-200 hover:border-cream-300 transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <StatusBadge status={entry.validationStatus} />
                    <AgreementBadge level={entry.stakeholderAgreementLevel} />
                    {entry.category && (
                      <span className="text-xs text-natural-400">{entry.category}</span>
                    )}
                    <span className="text-xs text-natural-400 ml-auto">
                      提及 {entry.mentionCount} 次
                    </span>
                  </div>
                  <div className="text-sm font-medium text-natural-700">{entry.requirementCandidate}</div>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {entry.sourceRoles.map((role, i) => (
                      <span key={i} className="px-1.5 py-0.5 text-xs bg-blue-50 text-blue-600 rounded">
                        {role}
                      </span>
                    ))}
                    {entry.missingValidationFrom.map((role, i) => (
                      <span key={i} className="px-1.5 py-0.5 text-xs bg-red-50 text-red-500 rounded border border-dashed border-red-200">
                        缺 {role}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-1 ml-3">
                  <button
                    onClick={() => setExpandedEntry(expandedEntry === entry.id ? null : entry.id)}
                    className="px-2 py-1 text-xs text-natural-500 hover:bg-cream-100 rounded"
                  >
                    {expandedEntry === entry.id ? '收起' : '展開'}
                  </button>
                  {entry.validationStatus !== 'rejected' && (
                    <button
                      onClick={() => handleReject(entry.id)}
                      className="px-2 py-1 text-xs text-red-400 hover:bg-red-50 rounded"
                    >
                      排除
                    </button>
                  )}
                </div>
              </div>

              {/* Expanded evidence */}
              {expandedEntry === entry.id && (
                <div className="mt-3 pt-3 border-t border-cream-200 space-y-2">
                  {entry.supportingEvidence.map((ev, i) => (
                    <div key={i} className="text-xs p-2 bg-cream-50 rounded">
                      <span className="font-medium text-natural-700">{ev.stakeholder_name}</span>
                      <span className="text-natural-400 ml-1">({ev.stakeholder_role})</span>
                      {ev.evidence_quote && (
                        <p className="text-natural-500 mt-0.5 italic">"{ev.evidence_quote}"</p>
                      )}
                    </div>
                  ))}
                  {entry.conflicts.length > 0 && (
                    <div className="text-xs p-2 bg-red-50 rounded">
                      <div className="font-medium text-red-700 mb-1">衝突：</div>
                      {entry.conflicts.map((c, i) => (
                        <div key={i} className="text-red-600">{c.description}</div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
