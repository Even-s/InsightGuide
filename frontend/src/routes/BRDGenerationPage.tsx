/**
 * BRD Generation Page
 * Generate and view Business Requirements Document from completed interview
 */

import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8002'

interface BRDDraft {
  id: string
  interview_session_id: string
  status: 'generating' | 'completed' | 'failed' | 'exported'
  title?: string
  executive_summary?: string
  project_overview?: string
  business_objectives?: string[]
  success_criteria?: string[]
  stakeholders?: Array<{ role: string; name: string }>
  assumptions?: string[]
  constraints?: string[]
  risks?: Array<{ description: string; mitigation: string }>
  markdown_content?: string
  generated_at?: string
  generation_duration_seconds?: number
  error_message?: string
  requirements: Requirement[]
}

interface Requirement {
  id: string
  title: string
  description: string
  type: 'functional' | 'non_functional' | 'business' | 'user' | 'technical'
  priority: 'must_have' | 'should_have' | 'nice_to_have'
  user_story?: string
  acceptance_criteria?: string[]
}

export default function BRDGenerationPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()

  const [brd, setBrd] = useState<BRDDraft | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)

  const checkExistingBRD = useCallback(async () => {
    if (!sessionId) return

    try {
      const response = await axios.get(`${API_URL}/api/brd/session/${sessionId}`)
      setBrd(response.data)

      // If still generating, poll for updates
      if (response.data.status === 'generating') {
        setTimeout(checkExistingBRD, 2000)
      }
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.status === 404) {
        // No BRD exists yet
        setBrd(null)
      } else {
        console.error('Error checking BRD:', err)
      }
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  useEffect(() => {
    if (sessionId) {
      checkExistingBRD()
    }
  }, [sessionId, checkExistingBRD])

  const generateBRD = async () => {
    if (!sessionId) return

    setGenerating(true)
    setError(null)

    try {
      await axios.post(`${API_URL}/api/brd/generate`, {
        interview_session_id: sessionId
      })

      // Start polling for updates
      setTimeout(checkExistingBRD, 2000)
    } catch (err: unknown) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null
      setError(typeof detail === 'string' ? detail : 'Failed to generate BRD')
      setGenerating(false)
    }
  }

  const exportMarkdown = async () => {
    if (!brd) return

    try {
      const response = await axios.get(
        `${API_URL}/api/brd/${brd.id}/download/markdown`,
        { responseType: 'blob' }
      )

      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `${brd.title || 'BRD'}.md`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      console.error('Failed to export markdown:', err)
    }
  }

  const exportPDF = async () => {
    if (!brd) return

    try {
      const response = await axios.get(
        `${API_URL}/api/brd/${brd.id}/download/pdf`,
        { responseType: 'blob' }
      )

      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `${brd.title || 'BRD'}.pdf`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      console.error('Failed to export PDF:', err)
      setError('Failed to export PDF')
    }
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'must_have': return 'bg-red-100 text-red-800'
      case 'should_have': return 'bg-yellow-100 text-yellow-800'
      case 'nice_to_have': return 'bg-green-100 text-green-800'
      default: return 'bg-cream-200 text-natural-700'
    }
  }

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'functional': return '功能需求'
      case 'non_functional': return '非功能需求'
      case 'business': return '業務需求'
      case 'user': return '用戶需求'
      case 'technical': return '技術需求'
      default: return type
    }
  }

  const getPriorityLabel = (priority: string) => {
    switch (priority) {
      case 'must_have': return '必須有'
      case 'should_have': return '應該有'
      case 'nice_to_have': return '最好有'
      default: return priority
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
          <p className="mt-4 text-natural-600">載入中...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-cream-50 py-8">
      <div className="max-w-6xl mx-auto px-4">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => navigate(-1)}
            className="text-natural-600 hover:text-natural-800 mb-4 flex items-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            返回訪談報告
          </button>

          <h1 className="text-3xl font-bold text-natural-900">業務需求文件 (BRD)</h1>
          <p className="text-natural-600 mt-2">根據訪談內容自動生成完整的業務需求文件</p>
        </div>

        {error && (
          <div className="bg-red-50 rounded-xl p-4 border border-red-200 mb-6">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* No BRD exists */}
        {!brd && !generating && (
          <div className="bg-white rounded-xl shadow-sm p-8 text-center">
            <svg className="w-16 h-16 mx-auto text-natural-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="text-xl font-semibold text-natural-800 mb-2">尚未生成 BRD</h3>
            <p className="text-natural-600 mb-6">點擊下方按鈕，AI 將根據訪談內容生成完整的業務需求文件</p>
            <button
              onClick={generateBRD}
              className="bg-primary-600 text-white px-6 py-3 rounded-lg hover:bg-primary-700 transition-colors"
            >
              生成 BRD 文件
            </button>
          </div>
        )}

        {/* Generating */}
        {(generating || brd?.status === 'generating') && (
          <div className="bg-white rounded-xl shadow-sm p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
            <h3 className="text-xl font-semibold text-natural-800 mb-2">正在生成 BRD...</h3>
            <p className="text-natural-600">AI 正在分析訪談內容並生成需求文件，請稍候</p>
          </div>
        )}

        {/* BRD Complete */}
        {brd && brd.status === 'completed' && (
          <div className="space-y-6">
            {/* Actions */}
            <div className="bg-white rounded-xl shadow-sm p-4 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <span className="text-sm text-natural-600">
                  生成時間: {brd.generated_at ? new Date(brd.generated_at).toLocaleString('zh-TW') : '-'}
                </span>
                {brd.generation_duration_seconds && (
                  <span className="text-sm text-natural-600">
                    耗時: {brd.generation_duration_seconds} 秒
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={exportPDF}
                  className="bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition-colors flex items-center gap-2"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                  下載 PDF
                </button>
                <button
                  onClick={exportMarkdown}
                  className="bg-natural-100 text-natural-700 px-4 py-2 rounded-lg hover:bg-natural-200 transition-colors"
                >
                  下載 Markdown
                </button>
                <button
                  onClick={generateBRD}
                  className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition-colors"
                >
                  重新生成
                </button>
              </div>
            </div>

            {/* BRD Content */}
            <div className="bg-white rounded-xl shadow-sm p-8">
              {/* Title */}
              {brd.title && (
                <h2 className="text-2xl font-bold text-natural-900 mb-6">{brd.title}</h2>
              )}

              {/* Executive Summary */}
              {brd.executive_summary && (
                <section className="mb-8">
                  <h3 className="text-xl font-semibold text-natural-800 mb-3">執行摘要</h3>
                  <p className="text-natural-700 whitespace-pre-wrap">{brd.executive_summary}</p>
                </section>
              )}

              {/* Project Overview */}
              {brd.project_overview && (
                <section className="mb-8">
                  <h3 className="text-xl font-semibold text-natural-800 mb-3">專案概述</h3>
                  <p className="text-natural-700 whitespace-pre-wrap">{brd.project_overview}</p>
                </section>
              )}

              {/* Business Objectives */}
              {brd.business_objectives && brd.business_objectives.length > 0 && (
                <section className="mb-8">
                  <h3 className="text-xl font-semibold text-natural-800 mb-3">業務目標</h3>
                  <ul className="list-disc list-inside space-y-2">
                    {brd.business_objectives.map((obj, idx) => (
                      <li key={idx} className="text-natural-700">{obj}</li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Success Criteria */}
              {brd.success_criteria && brd.success_criteria.length > 0 && (
                <section className="mb-8">
                  <h3 className="text-xl font-semibold text-natural-800 mb-3">成功標準</h3>
                  <ul className="list-disc list-inside space-y-2">
                    {brd.success_criteria.map((criteria, idx) => (
                      <li key={idx} className="text-natural-700">{criteria}</li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Requirements */}
              {brd.requirements && brd.requirements.length > 0 && (
                <section className="mb-8">
                  <h3 className="text-xl font-semibold text-natural-800 mb-4">功能需求</h3>
                  <div className="space-y-4">
                    {brd.requirements.map((req) => (
                      <div key={req.id} className="border border-natural-200 rounded-lg p-4">
                        <div className="flex items-start justify-between mb-2">
                          <h4 className="font-semibold text-natural-800">{req.title}</h4>
                          <div className="flex gap-2">
                            <span className={`text-xs px-2 py-1 rounded ${getPriorityColor(req.priority)}`}>
                              {getPriorityLabel(req.priority)}
                            </span>
                            <span className="text-xs px-2 py-1 rounded bg-sage-100 text-sage-500">
                              {getTypeLabel(req.type)}
                            </span>
                          </div>
                        </div>
                        <p className="text-natural-600 text-sm mb-3">{req.description}</p>

                        {req.user_story && (
                          <div className="bg-cream-50 rounded p-3 mb-2">
                            <p className="text-sm font-medium text-natural-700 mb-1">用戶故事</p>
                            <p className="text-sm text-natural-600">{req.user_story}</p>
                          </div>
                        )}

                        {req.acceptance_criteria && req.acceptance_criteria.length > 0 && (
                          <div className="mt-2">
                            <p className="text-sm font-medium text-natural-700 mb-1">驗收標準</p>
                            <ul className="text-sm text-natural-600 space-y-1">
                              {req.acceptance_criteria.map((criteria, idx) => (
                                <li key={idx} className="flex items-start gap-2">
                                  <span className="text-primary-600 mt-0.5">•</span>
                                  <span>{criteria}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Assumptions */}
              {brd.assumptions && brd.assumptions.length > 0 && (
                <section className="mb-8">
                  <h3 className="text-xl font-semibold text-natural-800 mb-3">假設</h3>
                  <ul className="list-disc list-inside space-y-2">
                    {brd.assumptions.map((assumption, idx) => (
                      <li key={idx} className="text-natural-700">{assumption}</li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Constraints */}
              {brd.constraints && brd.constraints.length > 0 && (
                <section className="mb-8">
                  <h3 className="text-xl font-semibold text-natural-800 mb-3">限制條件</h3>
                  <ul className="list-disc list-inside space-y-2">
                    {brd.constraints.map((constraint, idx) => (
                      <li key={idx} className="text-natural-700">{constraint}</li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Risks */}
              {brd.risks && brd.risks.length > 0 && (
                <section>
                  <h3 className="text-xl font-semibold text-natural-800 mb-3">風險</h3>
                  <div className="space-y-3">
                    {brd.risks.map((risk, idx) => (
                      <div key={idx} className="border-l-4 border-orange-400 pl-4">
                        <p className="font-medium text-natural-800">{risk.description}</p>
                        {risk.mitigation && (
                          <p className="text-sm text-natural-600 mt-1">緩解措施: {risk.mitigation}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          </div>
        )}

        {/* Failed */}
        {brd && brd.status === 'failed' && (
          <div className="bg-white rounded-xl shadow-sm p-8 text-center">
            <svg className="w-16 h-16 mx-auto text-red-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 className="text-xl font-semibold text-natural-800 mb-2">生成失敗</h3>
            <p className="text-natural-600 mb-6">{brd.error_message || '發生未知錯誤'}</p>
            <button
              onClick={generateBRD}
              className="bg-primary-600 text-white px-6 py-3 rounded-lg hover:bg-primary-700 transition-colors"
            >
              重試
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
