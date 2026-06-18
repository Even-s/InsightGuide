import { useEffect, useState } from 'react'
import apiClient from '@/api/client'

interface PromptVersion {
  id: string
  versionNumber: number
  status: string
  systemPrompt: string | null
  userPromptTemplate: string | null
  notes: string | null
  publishedAt: string | null
  createdAt: string | null
  updatedAt: string | null
}

interface PromptTemplate {
  id: string
  key: string
  name: string
  description: string | null
  category: string
  model: string | null
  riskLevel: string
  serviceFile: string | null
  serviceFunction: string | null
  inputVariables: string[] | null
  outputFormat: string | null
  activeVersion: PromptVersion | null
  versionCount: number
  createdAt: string | null
  updatedAt: string | null
}

const CATEGORY_LABELS: Record<string, string> = {
  document_analysis: '文件分析',
  interview_realtime: '即時訪談',
  brd_generation: 'BRD 生成',
  question_editing: '問題編輯',
  utilities: '工具',
}

const RISK_COLORS: Record<string, string> = {
  high: 'bg-red-50 text-red-700 border-red-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  low: 'bg-sage-50 text-sage-500 border-sage-200',
}

export default function PromptsPage() {
  const [prompts, setPrompts] = useState<PromptTemplate[]>([])
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [filterCategory, setFilterCategory] = useState<string>('all')
  const [versions, setVersions] = useState<PromptVersion[]>([])
  const [isEditing, setIsEditing] = useState(false)
  const [editSystemPrompt, setEditSystemPrompt] = useState('')
  const [editNotes, setEditNotes] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [previewVars, setPreviewVars] = useState<Record<string, string>>({})
  const [previewResult, setPreviewResult] = useState<{ systemPrompt?: string; userPrompt?: string; missingVariables?: string[] } | null>(null)
  const [diffMode, setDiffMode] = useState(false)
  const [diffLeft, setDiffLeft] = useState<string | null>(null)
  const [diffRight, setDiffRight] = useState<string | null>(null)
  const [diffData, setDiffData] = useState<{ left: PromptVersion | null; right: PromptVersion | null } | null>(null)
  const [auditLogs, setAuditLogs] = useState<Array<{ id: string; action: string; actor: string | null; versionId: string | null; createdAt: string | null }>>([])
  const [usageStats, setUsageStats] = useState<{ totalCalls: number; avgLatencyMs: number; totalTokens: number; errorCount: number } | null>(null)
  const [abTest, setAbTest] = useState<{
    id: string; name: string; status: string; variantAId: string; variantBId: string;
    trafficPercentB: number; startedAt: string | null; winner: string | null;
    stats: { a: { calls: number; avgLatencyMs: number; errorRate: number }; b: { calls: number; avgLatencyMs: number; errorRate: number } };
  } | null>(null)
  const [showAbCreate, setShowAbCreate] = useState(false)
  const [abName, setAbName] = useState('')
  const [abVariantA, setAbVariantA] = useState('')
  const [abVariantB, setAbVariantB] = useState('')
  const [abTraffic, setAbTraffic] = useState(50)
  const [pendingApprovals, setPendingApprovals] = useState<Array<{
    id: string; versionId: string; requester: string | null; status: string; requestedAt: string | null
  }>>([])
  const [reviewComment, setReviewComment] = useState('')
  const [showAssist, setShowAssist] = useState(false)
  const [assistGoal, setAssistGoal] = useState('')
  const [assistMode, setAssistMode] = useState<'generate' | 'improve'>('improve')
  const [assistLang, setAssistLang] = useState('auto')
  const [assistLoading, setAssistLoading] = useState(false)
  const [assistResult, setAssistResult] = useState<{ system_prompt?: string; user_prompt_template?: string | null; explanation?: string[] } | null>(null)
  const [driftResults, setDriftResults] = useState<Array<{ key: string; type: string; detail: string }> | null>(null)
  const [showDrift, setShowDrift] = useState(false)
  const [viewingVersionId, setViewingVersionId] = useState<string | null>(null)

  useEffect(() => {
    apiClient.get('/api/prompts/').then(r => {
      setPrompts(r.data)
      if (r.data.length > 0 && !selectedKey) {
        setSelectedKey(r.data[0].key)
      }
    }).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (selectedKey) {
      loadVersions(selectedKey)
      loadAuditAndUsage(selectedKey)
      setIsEditing(false)
      setViewingVersionId(null)
    }
  }, [selectedKey])

  const loadVersions = async (key: string) => {
    try {
      const response = await apiClient.get(`/api/prompts/${key}/versions`)
      setVersions(response.data)
    } catch (error) {
      console.error('Failed to load versions:', error)
    }
  }

  const loadAuditAndUsage = async (key: string) => {
    try {
      const [auditRes, usageRes, abRes, approvalsRes] = await Promise.all([
        apiClient.get(`/api/prompts/${key}/audit`),
        apiClient.get(`/api/prompts/${key}/usage`),
        apiClient.get(`/api/prompts/${key}/ab-test`),
        apiClient.get(`/api/prompts/${key}/approvals`),
      ])
      setAuditLogs(auditRes.data)
      setUsageStats(usageRes.data)
      setAbTest(abRes.data)
      setPendingApprovals(approvalsRes.data)
    } catch (error) {
      console.error('Failed to load audit/usage:', error)
    }
  }

  const handleCreateAbTest = async () => {
    if (!selectedKey || !abName || !abVariantA || !abVariantB) return
    setIsSaving(true)
    try {
      await apiClient.post(`/api/prompts/${selectedKey}/ab-test`, {
        name: abName,
        variant_a_id: abVariantA,
        variant_b_id: abVariantB,
        traffic_percent_b: abTraffic,
      })
      setShowAbCreate(false)
      setAbName('')
      await loadAuditAndUsage(selectedKey)
      alert('A/B 測試已建立')
    } catch (error: any) {
      alert('建立失敗: ' + (error.response?.data?.detail || '未知錯誤'))
    } finally {
      setIsSaving(false)
    }
  }

  const handleStopAbTest = async (winner: string | null) => {
    if (!selectedKey) return
    const label = winner ? `宣告 Variant ${winner.toUpperCase()} 為贏家並發布` : '結束測試（不宣告贏家）'
    if (!confirm(`確定要${label}嗎？`)) return
    setIsSaving(true)
    try {
      await apiClient.post(`/api/prompts/${selectedKey}/ab-test/stop`, { winner })
      await loadAuditAndUsage(selectedKey)
      await refreshPrompts()
      alert('A/B 測試已結束')
    } catch (error: any) {
      alert('操作失敗: ' + (error.response?.data?.detail || '未知錯誤'))
    } finally {
      setIsSaving(false)
    }
  }

  const refreshPrompts = async () => {
    const response = await apiClient.get('/api/prompts/')
    setPrompts(response.data)
  }

  const handleCreateVersion = () => {
    const selected = prompts.find(p => p.key === selectedKey)
    if (!selected) return

    setEditSystemPrompt(selected.activeVersion?.systemPrompt || '')
    setEditNotes('')
    setIsEditing(true)
  }

  const handleSaveDraft = async () => {
    if (!selectedKey) return
    setIsSaving(true)
    try {
      await apiClient.post(`/api/prompts/${selectedKey}/versions`, {
        system_prompt: editSystemPrompt || null,
        user_prompt_template: null,
        notes: editNotes || null,
      })
      await loadVersions(selectedKey)
      await refreshPrompts()
      setIsEditing(false)
      alert('草稿已儲存')
    } catch (error) {
      console.error('Failed to save draft:', error)
      alert('儲存失敗')
    } finally {
      setIsSaving(false)
    }
  }

  const handlePublish = async (versionId: string) => {
    if (!selectedKey) return
    const selected = prompts.find(p => p.key === selectedKey)
    if (!selected) return

    if (selected.riskLevel === 'high') {
      const confirmed = confirm(
        '⚠️ 此為高風險 Prompt，需要審核通過才能發布。\n\n確定要提交審核請求嗎？'
      )
      if (!confirmed) return

      setIsSaving(true)
      try {
        await apiClient.post(`/api/prompts/${selectedKey}/approvals`, {
          version_id: versionId,
        })
        await loadAuditAndUsage(selectedKey)
        alert('已提交審核請求，等待審核者批准後自動發布')
      } catch (error: any) {
        alert('提交失敗: ' + (error.response?.data?.detail || '未知錯誤'))
      } finally {
        setIsSaving(false)
      }
      return
    }

    setIsSaving(true)
    try {
      await apiClient.post(`/api/prompts/${selectedKey}/publish`, {
        version_id: versionId,
      })
      await loadVersions(selectedKey)
      await refreshPrompts()
      alert('版本已發布')
    } catch (error) {
      console.error('Failed to publish version:', error)
      alert('發布失敗')
    } finally {
      setIsSaving(false)
    }
  }

  const handleApprove = async (requestId: string) => {
    if (!selectedKey) return
    setIsSaving(true)
    try {
      await apiClient.post(`/api/prompts/${selectedKey}/approvals/${requestId}/approve`, {
        comment: reviewComment || null,
      })
      setReviewComment('')
      await loadAuditAndUsage(selectedKey)
      await loadVersions(selectedKey)
      await refreshPrompts()
      alert('已批准並自動發布')
    } catch (error: any) {
      alert('操作失敗: ' + (error.response?.data?.detail || '未知錯誤'))
    } finally {
      setIsSaving(false)
    }
  }

  const handleReject = async (requestId: string) => {
    if (!selectedKey) return
    if (!reviewComment) {
      alert('請填寫拒絕原因')
      return
    }
    setIsSaving(true)
    try {
      await apiClient.post(`/api/prompts/${selectedKey}/approvals/${requestId}/reject`, {
        comment: reviewComment,
      })
      setReviewComment('')
      await loadAuditAndUsage(selectedKey)
      alert('已拒絕')
    } catch (error: any) {
      alert('操作失敗: ' + (error.response?.data?.detail || '未知錯誤'))
    } finally {
      setIsSaving(false)
    }
  }

  const handlePreview = async () => {
    if (!selectedKey) return
    try {
      const response = await apiClient.post(`/api/prompts/${selectedKey}/preview`, {
        variables: previewVars,
      })
      setPreviewResult(response.data)
      setShowPreview(true)
    } catch (error) {
      console.error('Preview failed:', error)
      alert('預覽失敗')
    }
  }

  const handleDiff = async () => {
    if (!selectedKey || !diffLeft || !diffRight) return
    try {
      const response = await apiClient.get(`/api/prompts/${selectedKey}/diff`, {
        params: { v1: diffLeft, v2: diffRight },
      })
      setDiffData(response.data)
    } catch (error) {
      console.error('Diff failed:', error)
    }
  }

  const handleRollback = async () => {
    if (!selectedKey) return
    const confirmed = confirm('確定要回滾到上一個已發布的版本嗎？')
    if (!confirmed) return

    setIsSaving(true)
    try {
      await apiClient.post(`/api/prompts/${selectedKey}/rollback`)
      await loadVersions(selectedKey)
      await refreshPrompts()
      alert('已回滾')
    } catch (error) {
      console.error('Failed to rollback:', error)
      alert('回滾失敗：' + (error as any).response?.data?.detail || '未知錯誤')
    } finally {
      setIsSaving(false)
    }
  }

  const handleAssist = async () => {
    if (!selectedKey || !assistGoal.trim()) return
    setAssistLoading(true)
    setAssistResult(null)
    try {
      const response = await apiClient.post(`/api/prompts/${selectedKey}/assist`, {
        goal: assistGoal,
        mode: assistMode,
        current_system_prompt: assistMode === 'improve' ? editSystemPrompt : null,
        current_user_prompt: null,
        language: assistLang,
      })
      setAssistResult(response.data)
    } catch (error) {
      console.error('Assist failed:', error)
      alert('AI 建議生成失敗')
    } finally {
      setAssistLoading(false)
    }
  }

  const handleApplyAssist = () => {
    if (!assistResult) return
    if (assistResult.system_prompt) setEditSystemPrompt(assistResult.system_prompt)
    setShowAssist(false)
    setAssistResult(null)
  }

  const handleDetectDrift = async () => {
    try {
      const res = await apiClient.get('/api/prompts/drift')
      setDriftResults(res.data)
      setShowDrift(true)
    } catch (error) {
      console.error('Drift check failed:', error)
    }
  }

  const handleExport = async () => {
    try {
      const res = await apiClient.get('/api/prompts/export')
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `prompts-export-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Export failed:', error)
      alert('匯出失敗')
    }
  }

  const handleImport = async () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.json'
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (!file) return
      try {
        const text = await file.text()
        const data = JSON.parse(text)
        const res = await apiClient.post('/api/prompts/import', data)
        alert(`匯入完成：新增 ${res.data.created}，更新 ${res.data.updated}`)
        const refreshRes = await apiClient.get('/api/prompts/')
        setPrompts(refreshRes.data)
      } catch (error) {
        console.error('Import failed:', error)
        alert('匯入失敗')
      }
    }
    input.click()
  }

  const categories = [...new Set(prompts.map(p => p.category))]
  const filtered = filterCategory === 'all' ? prompts : prompts.filter(p => p.category === filterCategory)
  const selected = prompts.find(p => p.key === selectedKey)

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-cream-100">
        <div className="animate-spin h-8 w-8 rounded-full border-2 border-cream-300 border-t-sage-400" />
      </div>
    )
  }

  return (
    <div className="flex h-screen bg-cream-100">
      {/* Left: Categories */}
      <aside className="w-44 shrink-0 border-r border-cream-300 bg-cream-50 p-3">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-natural-400">分類</h2>
        <button
          onClick={() => setFilterCategory('all')}
          className={`mb-1 w-full rounded-lg px-3 py-2 text-left text-sm ${filterCategory === 'all' ? 'bg-sage-50 text-sage-500 font-medium' : 'text-natural-500 hover:bg-cream-200'}`}
        >
          全部 ({prompts.length})
        </button>
        {categories.map(cat => (
          <button
            key={cat}
            onClick={() => setFilterCategory(cat)}
            className={`mb-1 w-full rounded-lg px-3 py-2 text-left text-sm ${filterCategory === cat ? 'bg-sage-50 text-sage-500 font-medium' : 'text-natural-500 hover:bg-cream-200'}`}
          >
            {CATEGORY_LABELS[cat] || cat} ({prompts.filter(p => p.category === cat).length})
          </button>
        ))}
      </aside>

      {/* Middle: Prompt list */}
      <div className="w-72 shrink-0 border-r border-cream-300 overflow-y-auto">
        <div className="p-3">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-sm font-semibold text-natural-700">Prompt 管理中心</h1>
            <div className="flex gap-1">
              <button onClick={handleDetectDrift} title="偵測漂移" className="rounded-lg p-1.5 text-natural-400 hover:bg-cream-200 hover:text-natural-600 transition-colors text-xs">⚠</button>
              <button onClick={handleExport} title="匯出" className="rounded-lg p-1.5 text-natural-400 hover:bg-cream-200 hover:text-natural-600 transition-colors text-xs">↓</button>
              <button onClick={handleImport} title="匯入" className="rounded-lg p-1.5 text-natural-400 hover:bg-cream-200 hover:text-natural-600 transition-colors text-xs">↑</button>
            </div>
          </div>

          {showDrift && driftResults && (
            <div className="mb-3 rounded-xl border border-amber-200 bg-amber-50 p-2">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-amber-700">Registry 健康檢查</span>
                <button onClick={() => setShowDrift(false)} className="text-xs text-natural-400 hover:text-natural-600">✕</button>
              </div>
              {driftResults.length === 0 ? (
                <p className="text-xs text-sage-600">一切正常，所有 Prompt 皆有已發布版本</p>
              ) : (
                <div className="space-y-1">
                  {driftResults.map(d => (
                    <div key={d.key} className="text-xs text-amber-700">
                      <span className="font-mono">{d.key}</span>: {d.detail}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          <div className="space-y-1">
            {filtered.map(p => (
              <button
                key={p.key}
                onClick={() => setSelectedKey(p.key)}
                className={`w-full rounded-xl px-3 py-2.5 text-left transition-colors ${selectedKey === p.key ? 'bg-white border border-sage-300 shadow-sm' : 'hover:bg-cream-200'}`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-natural-700 truncate">{p.name}</span>
                  <span className={`ml-2 shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-medium ${RISK_COLORS[p.riskLevel] || RISK_COLORS.medium}`}>
                    {p.riskLevel}
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-natural-400 truncate">{p.key}</p>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Right: Detail */}
      <main className="flex-1 overflow-y-auto p-6">
        {selected ? (
          <div className="mx-auto max-w-3xl space-y-5">
            {/* Header */}
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <h2 className="text-xl font-semibold text-natural-700">{selected.name}</h2>
                  <span className={`rounded border px-2 py-0.5 text-xs font-medium ${RISK_COLORS[selected.riskLevel] || RISK_COLORS.medium}`}>
                    {selected.riskLevel} risk
                  </span>
                </div>
                <div className="flex gap-2">
                  {!isEditing && (
                    <>
                      <button
                        onClick={handleCreateVersion}
                        className="rounded-xl bg-sage-500 px-4 py-2 text-sm font-medium text-white hover:bg-sage-600 transition-colors"
                      >
                        新增版本
                      </button>
                      <button
                        onClick={handleRollback}
                        disabled={isSaving}
                        className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-700 hover:bg-amber-100 transition-colors disabled:opacity-50"
                      >
                        回滾
                      </button>
                    </>
                  )}
                </div>
              </div>
              <p className="mt-1 text-sm text-natural-400">{selected.description}</p>
            </div>

            {/* Metadata */}
            <div className="grid grid-cols-2 gap-3">
              <MetaItem label="Key" value={selected.key} mono />
              <MetaItem label="Category" value={CATEGORY_LABELS[selected.category] || selected.category} />
              <MetaItem label="Model" value={selected.model || '—'} mono />
              <MetaItem label="Active Version" value={selected.activeVersion ? `v${selected.activeVersion.versionNumber}` : '—'} />
              <MetaItem label="Service" value={selected.serviceFile || '—'} mono />
              <MetaItem label="Function" value={selected.serviceFunction || '—'} mono />
            </div>

            {/* Usage Stats */}
            {usageStats && usageStats.totalCalls > 0 && (
              <div className="grid grid-cols-4 gap-2">
                <div className="rounded-xl bg-white border border-cream-300 px-3 py-2 text-center">
                  <dt className="text-[10px] text-natural-400">總呼叫</dt>
                  <dd className="text-lg font-semibold text-natural-700">{usageStats.totalCalls}</dd>
                </div>
                <div className="rounded-xl bg-white border border-cream-300 px-3 py-2 text-center">
                  <dt className="text-[10px] text-natural-400">平均延遲</dt>
                  <dd className="text-lg font-semibold text-natural-700">{usageStats.avgLatencyMs}ms</dd>
                </div>
                <div className="rounded-xl bg-white border border-cream-300 px-3 py-2 text-center">
                  <dt className="text-[10px] text-natural-400">總 Token</dt>
                  <dd className="text-lg font-semibold text-natural-700">{usageStats.totalTokens.toLocaleString()}</dd>
                </div>
                <div className="rounded-xl bg-white border border-cream-300 px-3 py-2 text-center">
                  <dt className="text-[10px] text-natural-400">錯誤</dt>
                  <dd className={`text-lg font-semibold ${usageStats.errorCount > 0 ? 'text-red-600' : 'text-natural-700'}`}>{usageStats.errorCount}</dd>
                </div>
              </div>
            )}

            {/* Variables */}
            {selected.inputVariables && selected.inputVariables.length > 0 && (
              <section className="rounded-2xl border border-cream-300 bg-white p-4">
                <h3 className="text-sm font-semibold text-natural-600 mb-2">Input Variables</h3>
                <div className="flex flex-wrap gap-1.5">
                  {selected.inputVariables.map(v => (
                    <span key={v} className="rounded-lg bg-cream-200 px-2.5 py-1 text-xs font-mono text-natural-600">{`{${v}}`}</span>
                  ))}
                </div>
              </section>
            )}

            {/* Output Format */}
            {selected.outputFormat && (
              <section className="rounded-2xl border border-cream-300 bg-white p-4">
                <h3 className="text-sm font-semibold text-natural-600 mb-2">Output Format</h3>
                <p className="text-sm text-natural-500 font-mono">{selected.outputFormat}</p>
              </section>
            )}

            {/* Pending Approvals */}
            {!isEditing && pendingApprovals.length > 0 && (
              <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                <h3 className="text-sm font-semibold text-amber-700 mb-3">待審核 ({pendingApprovals.length})</h3>
                <div className="space-y-3">
                  {pendingApprovals.map(a => {
                    const ver = versions.find(v => v.id === a.versionId)
                    return (
                      <div key={a.id} className="rounded-xl border border-amber-200 bg-white p-3">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-mono font-medium text-natural-700">
                              v{ver?.versionNumber || '?'}
                            </span>
                            <span className="rounded bg-amber-100 border border-amber-200 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                              待審核
                            </span>
                          </div>
                          <span className="text-xs text-natural-400">
                            {a.requestedAt ? new Date(a.requestedAt).toLocaleString('zh-TW') : ''}
                          </span>
                        </div>
                        {a.requester && <p className="text-xs text-natural-500 mb-2">提交者: {a.requester}</p>}
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={reviewComment}
                            onChange={(e) => setReviewComment(e.target.value)}
                            className="flex-1 rounded-lg border border-cream-300 bg-cream-50 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-sage-400"
                            placeholder="審核備註（拒絕時必填）"
                          />
                          <button
                            onClick={() => handleApprove(a.id)}
                            disabled={isSaving}
                            className="rounded-lg bg-sage-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-sage-600 disabled:opacity-50"
                          >
                            批准
                          </button>
                          <button
                            onClick={() => handleReject(a.id)}
                            disabled={isSaving}
                            className="rounded-lg bg-red-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-600 disabled:opacity-50"
                          >
                            拒絕
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </section>
            )}

            {/* A/B Testing */}
            {!isEditing && (
              <section className="rounded-2xl border border-cream-300 bg-white p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-natural-600">A/B 測試</h3>
                  {!abTest && !showAbCreate && versions.length >= 2 && (
                    <button
                      onClick={() => setShowAbCreate(true)}
                      className="rounded-lg border border-sage-300 bg-sage-50 px-3 py-1.5 text-xs font-medium text-sage-600 hover:bg-sage-100 transition-colors"
                    >
                      建立測試
                    </button>
                  )}
                </div>

                {abTest && (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-sage-50 border border-sage-200 px-2 py-0.5 text-xs font-medium text-sage-600">進行中</span>
                      <span className="text-sm font-medium text-natural-700">{abTest.name}</span>
                      <span className="text-xs text-natural-400 ml-auto">B 流量: {abTest.trafficPercentB}%</span>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-xl border border-cream-200 p-3">
                        <p className="text-xs font-medium text-natural-500 mb-2">Variant A ({100 - abTest.trafficPercentB}%)</p>
                        <div className="space-y-1 text-xs text-natural-600">
                          <p>呼叫: <span className="font-mono font-medium">{abTest.stats.a.calls}</span></p>
                          <p>平均延遲: <span className="font-mono font-medium">{abTest.stats.a.avgLatencyMs}ms</span></p>
                          <p>錯誤率: <span className={`font-mono font-medium ${abTest.stats.a.errorRate > 5 ? 'text-red-600' : ''}`}>{abTest.stats.a.errorRate}%</span></p>
                        </div>
                      </div>
                      <div className="rounded-xl border border-cream-200 p-3">
                        <p className="text-xs font-medium text-natural-500 mb-2">Variant B ({abTest.trafficPercentB}%)</p>
                        <div className="space-y-1 text-xs text-natural-600">
                          <p>呼叫: <span className="font-mono font-medium">{abTest.stats.b.calls}</span></p>
                          <p>平均延遲: <span className="font-mono font-medium">{abTest.stats.b.avgLatencyMs}ms</span></p>
                          <p>錯誤率: <span className={`font-mono font-medium ${abTest.stats.b.errorRate > 5 ? 'text-red-600' : ''}`}>{abTest.stats.b.errorRate}%</span></p>
                        </div>
                      </div>
                    </div>

                    <div className="flex gap-2 pt-1">
                      <button onClick={() => handleStopAbTest('a')} disabled={isSaving} className="rounded-lg bg-sage-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-sage-600 disabled:opacity-50">A 贏</button>
                      <button onClick={() => handleStopAbTest('b')} disabled={isSaving} className="rounded-lg bg-sage-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-sage-600 disabled:opacity-50">B 贏</button>
                      <button onClick={() => handleStopAbTest(null)} disabled={isSaving} className="rounded-lg border border-cream-300 px-3 py-1.5 text-xs font-medium text-natural-500 hover:bg-cream-100 disabled:opacity-50">結束（無贏家）</button>
                    </div>
                  </div>
                )}

                {showAbCreate && (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs font-medium text-natural-500 mb-1">測試名稱</label>
                      <input
                        type="text"
                        value={abName}
                        onChange={(e) => setAbName(e.target.value)}
                        className="w-full rounded-lg border border-cream-300 bg-cream-50 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-sage-400"
                        placeholder="例：改善 system prompt 語氣"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs font-medium text-natural-500 mb-1">Variant A</label>
                        <select value={abVariantA} onChange={(e) => setAbVariantA(e.target.value)} className="w-full rounded-lg border border-cream-300 bg-white px-2 py-1.5 text-xs">
                          <option value="">選擇版本</option>
                          {versions.map(v => <option key={v.id} value={v.id}>v{v.versionNumber} ({v.status})</option>)}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-natural-500 mb-1">Variant B</label>
                        <select value={abVariantB} onChange={(e) => setAbVariantB(e.target.value)} className="w-full rounded-lg border border-cream-300 bg-white px-2 py-1.5 text-xs">
                          <option value="">選擇版本</option>
                          {versions.map(v => <option key={v.id} value={v.id}>v{v.versionNumber} ({v.status})</option>)}
                        </select>
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-natural-500 mb-1">B 流量比例: {abTraffic}%</label>
                      <input type="range" min={10} max={90} step={10} value={abTraffic} onChange={(e) => setAbTraffic(Number(e.target.value))} className="w-full" />
                    </div>
                    <div className="flex gap-2">
                      <button onClick={handleCreateAbTest} disabled={isSaving || !abName || !abVariantA || !abVariantB} className="rounded-xl bg-sage-500 px-4 py-2 text-sm font-medium text-white hover:bg-sage-600 disabled:opacity-50">建立測試</button>
                      <button onClick={() => setShowAbCreate(false)} className="rounded-xl border border-cream-300 px-4 py-2 text-sm font-medium text-natural-600 hover:bg-cream-100">取消</button>
                    </div>
                  </div>
                )}

                {!abTest && !showAbCreate && versions.length < 2 && (
                  <p className="text-xs text-natural-400">需要至少兩個版本才能建立 A/B 測試</p>
                )}
              </section>
            )}

            {/* Editor or Display */}
            {isEditing ? (
              <section className="rounded-2xl border border-sage-300 bg-white p-4 shadow-natural">
                <h3 className="text-sm font-semibold text-natural-600 mb-3">編輯新版本</h3>

                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-natural-500 mb-1">System Prompt</label>
                    <textarea
                      value={editSystemPrompt}
                      onChange={(e) => setEditSystemPrompt(e.target.value)}
                      className="w-full h-48 px-3 py-2 text-sm font-mono bg-cream-50 border border-cream-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-sage-400 resize-y"
                      placeholder="輸入 system prompt..."
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-natural-500 mb-1">備註 (可選)</label>
                    <input
                      type="text"
                      value={editNotes}
                      onChange={(e) => setEditNotes(e.target.value)}
                      className="w-full px-3 py-2 text-sm bg-cream-50 border border-cream-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-sage-400"
                      placeholder="此版本的變更說明..."
                    />
                  </div>

                  <div className="flex gap-2 pt-2">
                    <button
                      onClick={handleSaveDraft}
                      disabled={isSaving}
                      className="rounded-xl bg-sage-500 px-4 py-2 text-sm font-medium text-white hover:bg-sage-600 transition-colors disabled:opacity-50"
                    >
                      {isSaving ? '儲存中...' : '儲存草稿'}
                    </button>
                    <button
                      onClick={() => setShowAssist(!showAssist)}
                      className={`rounded-xl px-4 py-2 text-sm font-medium transition-colors ${showAssist ? 'bg-amber-500 text-white' : 'border border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100'}`}
                    >
                      AI 助手
                    </button>
                    <button
                      onClick={() => setIsEditing(false)}
                      disabled={isSaving}
                      className="rounded-xl border border-cream-300 bg-white px-4 py-2 text-sm font-medium text-natural-600 hover:bg-cream-100 transition-colors"
                    >
                      取消
                    </button>
                  </div>

                  {/* AI Assist Panel */}
                  {showAssist && (
                    <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50/50 p-4 space-y-3">
                      <h4 className="text-sm font-semibold text-amber-800">Prompt 撰寫助手</h4>

                      <div>
                        <label className="block text-xs font-medium text-natural-500 mb-1">你想達成什麼目標？</label>
                        <input
                          type="text"
                          value={assistGoal}
                          onChange={(e) => setAssistGoal(e.target.value)}
                          className="w-full rounded-lg border border-amber-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
                          placeholder="例：讓 AI 更精確判斷回答是否涵蓋所有必要資訊點"
                        />
                      </div>

                      <div className="flex gap-4">
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-natural-500">模式:</span>
                          <button
                            onClick={() => setAssistMode('improve')}
                            className={`rounded-lg px-2.5 py-1 text-xs font-medium ${assistMode === 'improve' ? 'bg-amber-500 text-white' : 'border border-amber-200 text-amber-700'}`}
                          >
                            改善現有
                          </button>
                          <button
                            onClick={() => setAssistMode('generate')}
                            className={`rounded-lg px-2.5 py-1 text-xs font-medium ${assistMode === 'generate' ? 'bg-amber-500 text-white' : 'border border-amber-200 text-amber-700'}`}
                          >
                            從零生成
                          </button>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-natural-500">語言:</span>
                          <select
                            value={assistLang}
                            onChange={(e) => setAssistLang(e.target.value)}
                            className="rounded-lg border border-amber-200 bg-white px-2 py-1 text-xs"
                          >
                            <option value="auto">自動</option>
                            <option value="zh">繁體中文</option>
                            <option value="en">English</option>
                          </select>
                        </div>
                      </div>

                      <button
                        onClick={handleAssist}
                        disabled={assistLoading || !assistGoal.trim()}
                        className="rounded-xl bg-amber-500 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50 transition-colors"
                      >
                        {assistLoading ? '生成中...' : '✨ 生成建議'}
                      </button>

                      {assistResult && (
                        <div className="space-y-3 pt-2 border-t border-amber-200">
                          {assistResult.system_prompt && (
                            <div>
                              <p className="text-xs font-medium text-natural-500 mb-1">建議 System Prompt</p>
                              <pre className="whitespace-pre-wrap text-xs font-mono bg-white rounded-xl p-3 max-h-40 overflow-y-auto border border-amber-100">
                                {assistResult.system_prompt}
                              </pre>
                            </div>
                          )}
                          {assistResult.explanation && assistResult.explanation.length > 0 && (
                            <div>
                              <p className="text-xs font-medium text-natural-500 mb-1">改善說明</p>
                              <ul className="list-disc list-inside text-xs text-natural-600 space-y-0.5">
                                {assistResult.explanation.map((e, i) => <li key={i}>{e}</li>)}
                              </ul>
                            </div>
                          )}
                          <div className="flex gap-2">
                            <button
                              onClick={handleApplyAssist}
                              className="rounded-lg bg-sage-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-sage-600"
                            >
                              套用到編輯器
                            </button>
                            <button
                              onClick={handleAssist}
                              disabled={assistLoading}
                              className="rounded-lg border border-amber-200 px-3 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-100"
                            >
                              重新生成
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </section>
            ) : (
              <>
                {/* Version Switcher */}
                {versions.length > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-natural-400">查看版本:</span>
                    <div className="flex gap-1 flex-wrap">
                      <button
                        onClick={() => setViewingVersionId(null)}
                        className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${!viewingVersionId ? 'bg-sage-500 text-white' : 'border border-cream-300 text-natural-500 hover:bg-cream-100'}`}
                      >
                        目前發布
                      </button>
                      {versions.filter(v => v.id !== selected.activeVersion?.id).map(v => (
                        <button
                          key={v.id}
                          onClick={() => setViewingVersionId(v.id)}
                          className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${viewingVersionId === v.id ? 'bg-sage-500 text-white' : 'border border-cream-300 text-natural-500 hover:bg-cream-100'}`}
                        >
                          v{v.versionNumber}
                          <span className={`ml-1 text-[10px] ${v.status === 'draft' ? 'text-amber-500' : v.status === 'archived' ? 'text-natural-400' : ''}`}>
                            {v.status === 'draft' ? '草稿' : v.status === 'archived' ? '封存' : ''}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Restore button for archived version */}
                {(() => {
                  const viewing = viewingVersionId ? versions.find(v => v.id === viewingVersionId) : null
                  return viewing && viewing.status === 'archived' ? (
                    <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2">
                      <span className="text-xs text-amber-700 flex-1">正在查看 v{viewing.versionNumber}（已封存）</span>
                      <button
                        onClick={handleRollback}
                        disabled={isSaving}
                        className="rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-600 disabled:opacity-50"
                      >
                        恢復此版本
                      </button>
                    </div>
                  ) : null
                })()}

                {/* System Prompt */}
                {(() => {
                  const viewing = viewingVersionId ? versions.find(v => v.id === viewingVersionId) : selected.activeVersion
                  return viewing?.systemPrompt ? (
                    <section className="rounded-2xl border border-cream-300 bg-white p-4">
                      <h3 className="text-sm font-semibold text-natural-600 mb-2">
                        System Prompt
                        {viewingVersionId && <span className="ml-2 text-xs font-normal text-amber-600">(v{viewing.versionNumber} - {viewing.status === 'draft' ? '草稿' : viewing.status === 'archived' ? '封存' : '已發布'})</span>}
                      </h3>
                      <pre className="whitespace-pre-wrap text-sm leading-relaxed text-natural-600 font-mono bg-cream-100 rounded-xl p-4 max-h-80 overflow-y-auto">
                        {viewing.systemPrompt}
                      </pre>
                    </section>
                  ) : null
                })()}

              </>
            )}

            {/* Version History */}
            {!isEditing && versions.length > 0 && (
              <section className="rounded-2xl border border-cream-300 bg-white p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-natural-600">版本歷史</h3>
                  {versions.length >= 2 && (
                    <button
                      onClick={() => setDiffMode(!diffMode)}
                      className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${diffMode ? 'bg-sage-500 text-white' : 'border border-cream-300 text-natural-500 hover:bg-cream-100'}`}
                    >
                      {diffMode ? '退出比較' : '版本比較'}
                    </button>
                  )}
                </div>

                {diffMode && (
                  <div className="mb-3 flex items-center gap-2 p-3 rounded-xl bg-cream-50 border border-cream-200">
                    <select
                      value={diffLeft || ''}
                      onChange={(e) => setDiffLeft(e.target.value || null)}
                      className="flex-1 rounded-lg border border-cream-300 bg-white px-2 py-1.5 text-xs"
                    >
                      <option value="">選擇左側版本</option>
                      {versions.map(v => <option key={v.id} value={v.id}>v{v.versionNumber} ({v.status})</option>)}
                    </select>
                    <span className="text-xs text-natural-400">vs</span>
                    <select
                      value={diffRight || ''}
                      onChange={(e) => setDiffRight(e.target.value || null)}
                      className="flex-1 rounded-lg border border-cream-300 bg-white px-2 py-1.5 text-xs"
                    >
                      <option value="">選擇右側版本</option>
                      {versions.map(v => <option key={v.id} value={v.id}>v{v.versionNumber} ({v.status})</option>)}
                    </select>
                    <button
                      onClick={handleDiff}
                      disabled={!diffLeft || !diffRight || diffLeft === diffRight}
                      className="rounded-lg bg-sage-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-sage-600 disabled:opacity-50"
                    >
                      比較
                    </button>
                  </div>
                )}

                {diffMode && diffData && (
                  <div className="mb-3 grid grid-cols-2 gap-3">
                    <div>
                      <p className="text-xs font-medium text-natural-500 mb-1">v{diffData.left?.versionNumber} — {diffData.left?.status}</p>
                      <pre className="whitespace-pre-wrap text-xs font-mono bg-red-50 rounded-xl p-3 max-h-48 overflow-y-auto border border-red-100">
                        {diffData.left?.systemPrompt || '(empty)'}
                      </pre>
                    </div>
                    <div>
                      <p className="text-xs font-medium text-natural-500 mb-1">v{diffData.right?.versionNumber} — {diffData.right?.status}</p>
                      <pre className="whitespace-pre-wrap text-xs font-mono bg-green-50 rounded-xl p-3 max-h-48 overflow-y-auto border border-green-100">
                        {diffData.right?.systemPrompt || '(empty)'}
                      </pre>
                    </div>
                  </div>
                )}

                <div className="space-y-2">
                  {versions.map((v) => (
                    <div
                      key={v.id}
                      className="flex items-center justify-between p-3 rounded-xl border border-cream-200 hover:bg-cream-50 transition-colors"
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono font-medium text-natural-700">v{v.versionNumber}</span>
                          <span className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${
                            v.status === 'published' ? 'bg-sage-50 text-sage-600 border-sage-200' :
                            v.status === 'draft' ? 'bg-amber-50 text-amber-600 border-amber-200' :
                            'bg-natural-50 text-natural-400 border-natural-200'
                          }`}>
                            {v.status === 'published' ? '已發布' : v.status === 'draft' ? '草稿' : '已封存'}
                          </span>
                          {v.publishedAt && (
                            <span className="text-xs text-natural-400">
                              {new Date(v.publishedAt).toLocaleString('zh-TW')}
                            </span>
                          )}
                        </div>
                        {v.notes && (
                          <p className="mt-1 text-xs text-natural-500">{v.notes}</p>
                        )}
                      </div>
                      {v.status === 'draft' && (
                        <button
                          onClick={() => handlePublish(v.id)}
                          disabled={isSaving}
                          className="ml-3 rounded-lg bg-sage-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-sage-600 transition-colors disabled:opacity-50"
                        >
                          {selected.riskLevel === 'high' ? '提交審核' : '發布'}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Prompt Preview */}
            {!isEditing && selected.inputVariables && selected.inputVariables.length > 0 && (
              <section className="rounded-2xl border border-cream-300 bg-white p-4">
                <h3 className="text-sm font-semibold text-natural-600 mb-3">預覽測試</h3>
                <div className="grid grid-cols-2 gap-2 mb-3">
                  {selected.inputVariables.map(v => (
                    <div key={v}>
                      <label className="block text-[10px] font-medium text-natural-400 mb-0.5">{v}</label>
                      <input
                        type="text"
                        value={previewVars[v] || ''}
                        onChange={(e) => setPreviewVars(prev => ({ ...prev, [v]: e.target.value }))}
                        className="w-full rounded-lg border border-cream-300 bg-cream-50 px-2 py-1.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-sage-400"
                        placeholder={`{${v}}`}
                      />
                    </div>
                  ))}
                </div>
                <button
                  onClick={handlePreview}
                  className="rounded-xl bg-sage-500 px-4 py-2 text-sm font-medium text-white hover:bg-sage-600 transition-colors"
                >
                  模板預覽
                </button>

                {showPreview && previewResult && (
                  <div className="mt-3 space-y-2">
                    {previewResult.missingVariables && (
                      <p className="text-xs text-amber-600">缺少變數: {previewResult.missingVariables.join(', ')}</p>
                    )}
                    {previewResult.systemPrompt && (
                      <div>
                        <p className="text-[10px] font-medium text-natural-400 mb-0.5">System Prompt (rendered)</p>
                        <pre className="whitespace-pre-wrap text-xs font-mono bg-sage-50 rounded-xl p-3 max-h-40 overflow-y-auto border border-sage-100">
                          {previewResult.systemPrompt}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </section>
            )}

            {/* Audit Log */}
            {!isEditing && auditLogs.length > 0 && (
              <section className="rounded-2xl border border-cream-300 bg-white p-4">
                <h3 className="text-sm font-semibold text-natural-600 mb-3">操作紀錄</h3>
                <div className="space-y-1.5 max-h-48 overflow-y-auto">
                  {auditLogs.map(log => (
                    <div key={log.id} className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-cream-50 text-xs">
                      <div className="flex items-center gap-2">
                        <span className={`rounded px-1.5 py-0.5 font-medium ${
                          log.action === 'published' ? 'bg-sage-50 text-sage-600' :
                          log.action === 'archived' ? 'bg-natural-50 text-natural-400' :
                          log.action === 'rolled_back' ? 'bg-amber-50 text-amber-600' :
                          'bg-cream-200 text-natural-500'
                        }`}>
                          {log.action === 'published' ? '發布' : log.action === 'archived' ? '封存' : log.action === 'rolled_back' ? '回滾' : '建立草稿'}
                        </span>
                        {log.actor && <span className="text-natural-400">{log.actor}</span>}
                      </div>
                      <span className="text-natural-400">
                        {log.createdAt ? new Date(log.createdAt).toLocaleString('zh-TW') : ''}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-natural-400">
            選擇一個 Prompt 查看詳情
          </div>
        )}
      </main>
    </div>
  )
}

function MetaItem({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-xl bg-white border border-cream-300 px-3 py-2">
      <dt className="text-xs text-natural-400">{label}</dt>
      <dd className={`mt-0.5 text-sm text-natural-700 truncate ${mono ? 'font-mono' : ''}`}>{value}</dd>
    </div>
  )
}
