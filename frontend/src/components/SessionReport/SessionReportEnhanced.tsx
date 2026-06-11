import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { QuestionCard } from '@/types/questionCard'

interface CardState {
  id: string
  sessionId: string
  topicCardId: string
  status: QuestionCard['status']
  confidence?: number | null
  coveredAt?: string | null
  evidenceTranscript?: string | null
  evidence?: Record<string, unknown> | null
  createdAt: string
  updatedAt: string
  questionCard: QuestionCard
}
import Button from '@/components/common/Button'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import { apiClient } from '@/api/client'

interface SessionReportEnhancedProps {
  sessionId: string
  cardStates?: CardState[]  // Made optional since we fetch data from API
  onBackToEditor: () => void
  onRestart: () => void
}

interface ReportData {
  session_id: string
  generated_at: string
  session_info: {
    status: string
    started_at: string | null
    ended_at: string | null
    duration_seconds: number | null
  }
  coverage_stats: {
    total_cards: number
    covered: number
    probably_covered: number
    at_risk: number
    skipped: number
    pending: number
    coverage_percentage: number
    must_coverage_percentage: number
    should_coverage_percentage: number
  }
  timeline: Array<{
    timestamp: string
    type: string
    description: string
    [key: string]: unknown
  }>
  topic_analysis: Array<{
    card_id: string
    title: string
    description: string
    importance: string
    status: string
    confidence: number
    slide_page: number
    success: boolean
  }>
  performance_metrics: {
    total_duration_seconds: number
    total_utterances: number
    total_characters?: number
    characters_per_minute?: number
    avg_utterance_characters?: number
    total_words: number
    words_per_minute: number
    avg_utterance_length: number
    slides_visited: number
  }
  slide_timing: Array<{
    slide_id: string
    slide_page: number | null
    slide_title: string | null
    duration_seconds: number
    utterance_count: number
  }>
  insights: {
    strengths: Array<{ category: string; description: string }>
    areas_for_improvement: Array<{ category: string; description: string }>
    recommendations: Array<{ category: string; priority: string; recommendation: string }>
  }
}

interface ReportExportResponse {
  session_id: string
  format: 'json' | 'pdf'
  content_type: string
  file_name: string
  object_key: string
  file_url: string
  download_url: string
  generated_at: string
}

const COLORS = {
  covered: '#10b981',
  probably_covered: '#fbbf24',
  at_risk: '#ef4444',
  skipped: '#94a3b8',
  pending: '#d1d5db',
}

export default function SessionReportEnhanced({
  sessionId,
  onBackToEditor,
  onRestart,
}: SessionReportEnhancedProps) {
  const navigate = useNavigate()
  const [reportData, setReportData] = useState<ReportData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)
  const [exportingFormat, setExportingFormat] = useState<'json' | 'pdf' | null>(null)

  const fetchReportData = useCallback(async () => {
    try {
      setLoading(true)
      const response = await apiClient.get<ReportData>(`/api/interview-sessions/${sessionId}/report`)
      setReportData(response.data)
    } catch (err) {
      console.error('Error fetching report:', err)
      setError('無法載入報告資料')
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  useEffect(() => {
    fetchReportData()
  }, [fetchReportData])

  const exportReport = async (format: 'json' | 'pdf') => {
    try {
      setExportError(null)
      setExportingFormat(format)
      const response = await apiClient.post<ReportExportResponse>(
        `/api/interview-sessions/${sessionId}/report/export/${format}`
      )
      const link = document.createElement('a')
      link.href = response.data.download_url
      link.download = response.data.file_name
      link.target = '_blank'
      link.rel = 'noopener noreferrer'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    } catch (err) {
      console.error(`Error exporting ${format} report:`, err)
      setExportError(`無法匯出 ${format.toUpperCase()} 報告`)
    } finally {
      setExportingFormat(null)
    }
  }

  if (loading) {
    return (
      <main className="flex min-h-0 flex-1 items-center justify-center bg-cream-100">
        <div className="text-center">
          <LoadingSpinner label="正在產生完整簡報報告..." />
        </div>
      </main>
    )
  }

  if (error || !reportData) {
    return (
      <main className="flex min-h-0 flex-1 items-center justify-center bg-cream-100">
        <div className="text-center">
          <p className="text-red-600">{error || '無法載入報告'}</p>
          <Button onClick={onBackToEditor} className="mt-4">返回編輯模式</Button>
        </div>
      </main>
    )
  }

  const { coverage_stats, performance_metrics, insights, topic_analysis, slide_timing } = reportData

  // Prepare chart data
  const coverageChartData = [
    { name: '已涵蓋', value: coverage_stats.covered, color: COLORS.covered },
    { name: '可能已涵蓋', value: coverage_stats.probably_covered, color: COLORS.probably_covered },
    { name: '有漏講風險', value: coverage_stats.at_risk, color: COLORS.at_risk },
    { name: '已跳過', value: coverage_stats.skipped, color: COLORS.skipped },
    { name: '待涵蓋', value: coverage_stats.pending, color: COLORS.pending },
  ].filter(item => item.value > 0)

  const importanceData = [
    { name: '必講', covered: coverage_stats.must_coverage_percentage },
    { name: '應講', covered: coverage_stats.should_coverage_percentage },
  ]

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '未記錄'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <main className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-cream-100 p-6">
      <div className="mx-auto w-full max-w-6xl">
        {/* Header */}
        <div className="mb-6 rounded-xl border border-cream-300 bg-cream-50 p-6 shadow-natural">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium tracking-wide text-sage-600">演講已完成</p>
              <h1 className="mt-1 text-3xl font-medium tracking-wide text-natural-700">
                簡報表現報告
              </h1>
              <p className="mt-2 text-sm text-natural-600">
                總時長：{formatDuration(reportData.session_info.duration_seconds)} ・ {performance_metrics.total_utterances} 段轉錄
              </p>
            </div>
            <div className="text-right">
              <p className="text-4xl font-bold text-sage-600">
                {Math.round(coverage_stats.coverage_percentage)}%
              </p>
              <p className="text-sm text-natural-600">涵蓋率</p>
            </div>
          </div>
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => exportReport('json')}
              loading={exportingFormat === 'json'}
            >
              匯出 JSON
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => exportReport('pdf')}
              loading={exportingFormat === 'pdf'}
            >
              匯出 PDF
            </Button>
            {exportError && (
              <p className="text-sm text-red-600">{exportError}</p>
            )}
          </div>
        </div>

        {/* Key Metrics */}
        <div className="mb-6 grid gap-4 md:grid-cols-4">
          <MetricCard label="主題總數" value={coverage_stats.total_cards} />
          <MetricCard label="已涵蓋" value={coverage_stats.covered} color="green" />
          <MetricCard label="有風險" value={coverage_stats.at_risk} color="red" />
          <MetricCard
            label="每分鐘中文字"
            value={Math.round(performance_metrics.characters_per_minute ?? performance_metrics.words_per_minute)}
          />
        </div>

        {/* Charts Row */}
        <div className="mb-6 grid gap-6 lg:grid-cols-2">
          {/* Coverage Pie Chart */}
          <div className="rounded-xl border border-cream-300 bg-white p-6 shadow-natural">
            <h2 className="mb-4 text-lg font-medium text-natural-700">涵蓋狀態分布</h2>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={coverageChartData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {coverageChartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Importance Bar Chart */}
          <div className="rounded-xl border border-cream-300 bg-white p-6 shadow-natural">
            <h2 className="mb-4 text-lg font-medium text-natural-700">重要性涵蓋率</h2>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={importanceData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis domain={[0, 100]} />
                <Tooltip formatter={(value) => `${value}%`} />
                <Legend />
                <Bar dataKey="covered" fill="#10b981" name="涵蓋率" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Insights Section */}
        {insights && (
          <div className="mb-6 rounded-xl border border-cream-300 bg-white p-6 shadow-natural">
            <h2 className="mb-4 text-lg font-medium text-natural-700">洞察與建議</h2>

            {insights.strengths.length > 0 && (
              <div className="mb-4">
                <h3 className="mb-2 text-sm font-medium text-sage-600">表現亮點</h3>
                <ul className="space-y-2">
                  {insights.strengths.map((strength, idx) => (
                    <li key={idx} className="rounded-lg bg-sage-50 p-3 text-sm text-sage-700">
                      {translateInsightText(strength.description)}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {insights.areas_for_improvement.length > 0 && (
              <div className="mb-4">
                <h3 className="mb-2 text-sm font-medium text-wood-600">可改進項目</h3>
                <ul className="space-y-2">
                  {insights.areas_for_improvement.map((area, idx) => (
                    <li key={idx} className="rounded-lg bg-wood-50 p-3 text-sm text-wood-700">
                      {translateInsightText(area.description)}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {insights.recommendations.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-medium text-sage-500">後續練習建議</h3>
                <ul className="space-y-2">
                  {insights.recommendations.map((rec, idx) => (
                    <li key={idx} className="rounded-lg bg-sage-50 p-3 text-sm">
                      <span className="font-medium text-sage-500">{translatePriority(rec.priority)}：</span>{' '}
                      <span className="text-sage-500">{translateInsightText(rec.recommendation)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Topic Analysis */}
        <div className="mb-6 rounded-xl border border-cream-300 bg-white p-6 shadow-natural">
          <h2 className="mb-4 text-lg font-medium text-natural-700">逐主題分析</h2>
          <div className="space-y-2">
            {topic_analysis.map((topic) => (
              <div
                key={topic.card_id}
                className={`rounded-lg border p-3 ${
                  topic.success
                    ? 'border-sage-200 bg-sage-50'
                    : topic.status === 'at_risk'
                    ? 'border-wood-200 bg-wood-50'
                    : 'border-cream-200 bg-cream-50'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <p className="font-medium text-natural-700">
                      {topic.success ? '✓' : topic.status === 'at_risk' ? '⚠️' : '○'} {topic.title}
                    </p>
                    <p className="mt-1 text-xs text-natural-600">{topic.description}</p>
                    <div className="mt-2 flex gap-3 text-xs">
                      <span className="text-natural-500">第 {topic.slide_page} 頁</span>
                      <span className="text-natural-500">
                        {translateImportance(topic.importance)}
                      </span>
                      <span className="text-natural-500">
                        信心分數：{Math.round(topic.confidence * 100)}%
                      </span>
                      <span className="text-natural-500">
                        狀態：{translateStatus(topic.status)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Slide Timing */}
        {slide_timing.length > 0 && (
          <div className="mb-6 rounded-xl border border-cream-300 bg-white p-6 shadow-natural">
            <h2 className="mb-4 text-lg font-medium text-natural-700">各頁停留時間</h2>
            <div className="space-y-2">
              {slide_timing.map((slide) => (
                <div key={slide.slide_id} className="flex items-center justify-between rounded-lg bg-cream-50 p-3">
                  <div>
                    <p className="text-sm font-medium text-natural-700">
                      第 {slide.slide_page} 頁 {slide.slide_title && `- ${slide.slide_title}`}
                    </p>
                    <p className="text-xs text-natural-600">{slide.utterance_count} 段轉錄</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium text-natural-700">
                      {formatDuration(slide.duration_seconds)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-between items-center pb-6">
          <Button
            onClick={() => navigate(`/interview/${sessionId}/brd`)}
            className="bg-primary-600 text-white hover:bg-primary-700"
          >
            <svg className="w-5 h-5 mr-2 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            生成 BRD 文件
          </Button>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={onBackToEditor}>
              返回編輯模式
            </Button>
            <Button onClick={onRestart}>開始新的演講</Button>
          </div>
        </div>
      </div>
    </main>
  )
}

function MetricCard({
  label,
  value,
  color,
}: {
  label: string
  value: number | string
  color?: 'green' | 'red'
}) {
  return (
    <div className="rounded-xl border border-cream-300 bg-white p-4 shadow-natural">
      <p className="text-xs font-medium tracking-wide text-natural-500">{label}</p>
      <p
        className={`mt-1 text-2xl font-medium ${
          color === 'green'
            ? 'text-sage-600'
            : color === 'red'
            ? 'text-wood-600'
            : 'text-natural-700'
        }`}
      >
        {value}
      </p>
    </div>
  )
}

function translateImportance(importance: string) {
  const labels: Record<string, string> = {
    must: '必講',
    should: '應講',
    optional: '選講',
  }

  return labels[importance] ?? importance
}

function translatePriority(priority: string) {
  const labels: Record<string, string> = {
    high: '高優先',
    medium: '中優先',
    low: '低優先',
  }

  return labels[priority.toLowerCase()] ?? priority
}

function translateStatus(status: string) {
  const labels: Record<string, string> = {
    pending: '待涵蓋',
    listening: '比對中',
    probably_covered: '可能已涵蓋',
    covered: '已涵蓋',
    at_risk: '有漏講風險',
    skipped: '已跳過',
    manually_checked: '手動確認',
    disabled: '停用',
  }

  return labels[status] ?? status
}

function translateInsightText(text: string) {
  const exactTranslations: Record<string, string> = {
    "All critical 'must' topics were successfully covered": '所有必講主題都已成功涵蓋',
    "Focus on covering all 'must' topics - they are essential to your presentation": '請優先練習所有必講主題，這些是簡報的核心內容',
    'Review uncovered topics and ensure all \'must\' items are included in next presentation': '請回顧未涵蓋的主題，並確認下次簡報包含所有必講項目',
    'Practice time management to ensure all important topics get adequate coverage': '請加強時間分配，確保重要主題都有足夠篇幅',
    'Try slowing down to 220-320 Chinese chars/min for better audience comprehension': '可嘗試調整到每分鐘 220-320 個中文字，讓聽眾更容易理解',
    'Consider picking up the pace slightly to maintain audience interest': '可稍微加快語速，維持聽眾注意力',
  }

  if (exactTranslations[text]) return exactTranslations[text]

  return text
    .replace(/Excellent coverage at ([\d.]+)% - all key topics addressed/g, '涵蓋率達 $1%，所有關鍵主題都有講到')
    .replace(/Good coverage at ([\d.]+)% - most topics covered/g, '涵蓋率達 $1%，大多數主題都有涵蓋')
    .replace(/Coverage at ([\d.]+)% - several topics not addressed/g, '涵蓋率為 $1%，仍有幾個主題尚未講到')
    .replace(/Only ([\d.]+)% of critical 'must' topics were covered/g, '必講主題只涵蓋了 $1%')
    .replace(/Good speaking pace at ([\d.]+) Chinese chars\/min - clear and understandable/g, '語速為每分鐘 $1 個中文字，節奏清楚且容易理解')
    .replace(/Speaking pace at ([\d.]+) Chinese chars\/min is fast - audience may struggle to follow/g, '語速為每分鐘 $1 個中文字，偏快，聽眾可能較難跟上')
    .replace(/Speaking pace at ([\d.]+) Chinese chars\/min is slow - may lose audience engagement/g, '語速為每分鐘 $1 個中文字，偏慢，可能影響聽眾投入度')
    .replace(/Good speaking pace at ([\d.]+) words\/min - clear and understandable/g, '語速為每分鐘 $1 字，節奏清楚且容易理解')
    .replace(/Speaking pace at ([\d.]+) words\/min is fast - audience may struggle to follow/g, '語速為每分鐘 $1 字，偏快，聽眾可能較難跟上')
    .replace(/Speaking pace at ([\d.]+) words\/min is slow - may lose audience engagement/g, '語速為每分鐘 $1 字，偏慢，可能影響聽眾投入度')
    .replace(/([\d.]+) important topics were flagged as 'at risk' due to timing/g, '有 $1 個重要主題因時間分配被標示為有漏講風險')
}
