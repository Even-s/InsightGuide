import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  createDemoSession,
  listDemoTemplates,
  type DemoTemplate,
} from '@/api/demoSessions'

export default function HomePage() {
  const navigate = useNavigate()
  const [templates, setTemplates] = useState<DemoTemplate[]>([])
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(true)
  const [creatingTemplateId, setCreatingTemplateId] = useState<string | null>(null)
  const [demoError, setDemoError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    listDemoTemplates()
      .then((items) => {
        if (active) setTemplates(items)
      })
      .catch(() => {
        if (active) setDemoError('目前無法載入 Demo 模板，請稍後再試。')
      })
      .finally(() => {
        if (active) setIsLoadingTemplates(false)
      })
    return () => {
      active = false
    }
  }, [])

  async function startDemo(template: DemoTemplate) {
    setCreatingTemplateId(template.id)
    setDemoError(null)
    try {
      const result = await createDemoSession(template.id)
      navigate(result.interviewPath)
    } catch {
      setDemoError('Demo 建立失敗，請再試一次。')
      setCreatingTemplateId(null)
    }
  }

  return (
    <div className="min-h-screen overflow-hidden bg-cream-100">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6 sm:px-8">
        <div className="text-xl font-medium tracking-wide text-natural-700 sm:text-2xl">
          InsightGuide
        </div>
        <div className="rounded-full border border-cream-300 bg-white/70 px-3 py-1 text-xs text-natural-500">
          需求訪談規劃助手
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-5xl flex-col items-center px-6 pb-16 pt-12 sm:px-8 sm:pt-20">
        <section className="max-w-2xl text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-sage-400 text-white shadow-natural">
            <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 4v-4z" />
            </svg>
          </div>
          <h1 className="text-3xl font-semibold leading-tight text-natural-800 sm:text-4xl">
            從訪談開始，釐清真正需求
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-base leading-7 text-natural-500">
            建立訪談計劃、管理受訪角色，將每次對話整理成可追溯的需求證據。
          </p>
        </section>

        <section className="mt-12 w-full rounded-3xl border border-sage-200 bg-white/80 p-6 shadow-natural sm:p-8" aria-labelledby="quick-demo-title">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <div className="inline-flex rounded-full bg-sage-100 px-3 py-1 text-xs font-medium text-sage-700">
                不用先建立專案
              </div>
              <h2 id="quick-demo-title" className="mt-3 text-2xl font-semibold text-natural-800">
                快速 Demo 訪談
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-natural-500">
                選一個公版情境，系統會準備獨立的暫存專案與訪談問題，直接進入完整訪談介面。
              </p>
            </div>
            <span className="text-xs text-natural-400">Demo 資料 24 小時後清理</span>
          </div>

          {isLoadingTemplates ? (
            <div className="mt-6 rounded-xl bg-cream-100 px-4 py-5 text-center text-sm text-natural-500" role="status">
              載入 Demo 模板中...
            </div>
          ) : (
            <div className="mt-6 grid gap-3 md:grid-cols-3">
              {templates.map((template) => {
                const isCreating = creatingTemplateId === template.id
                return (
                  <button
                    key={template.id}
                    type="button"
                    onClick={() => startDemo(template)}
                    disabled={creatingTemplateId !== null}
                    aria-label={`使用${template.title}開始 Demo`}
                    className="group rounded-2xl border border-cream-300 bg-cream-50 p-5 text-left transition hover:-translate-y-0.5 hover:border-sage-300 hover:bg-sage-50 disabled:cursor-wait disabled:opacity-60"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="font-semibold text-natural-800">{template.title}</h3>
                      <svg className="h-4 w-4 shrink-0 text-sage-500 transition-transform group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                    <p className="mt-2 min-h-12 text-sm leading-6 text-natural-500">{template.description}</p>
                    <div className="mt-4 flex items-center gap-3 text-xs text-natural-400">
                      <span>約 {template.estimatedMinutes} 分鐘</span>
                      <span>{template.questionCount} 個問題</span>
                    </div>
                    <span className="mt-4 inline-flex text-sm font-medium text-sage-600">
                      {isCreating ? '正在準備訪談...' : '立即開始'}
                    </span>
                  </button>
                )
              })}
            </div>
          )}
          {demoError && <p className="mt-4 text-sm text-red-600" role="alert">{demoError}</p>}
        </section>

        <section className="mt-6 grid w-full gap-5 md:grid-cols-2" aria-label="專案入口">
          <button
            type="button"
            onClick={() => navigate('/projects/new')}
            aria-label="新建專案"
            className="group relative overflow-hidden rounded-2xl border border-sage-200 bg-sage-50/70 p-7 text-left shadow-natural transition-all hover:-translate-y-0.5 hover:border-sage-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-sage-300 focus:ring-offset-2 focus:ring-offset-cream-100"
          >
            <div className="absolute -right-10 -top-10 h-32 w-32 rounded-full bg-sage-100/70" aria-hidden="true" />
            <div className="relative">
              <div className="flex items-start justify-between gap-4">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-sage-400 text-white">
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v14m7-7H5" />
                  </svg>
                </div>
                <svg className="h-5 w-5 text-sage-400 transition-transform group-hover:translate-x-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </div>
              <h2 className="mt-7 text-xl font-semibold text-natural-800">新建專案</h2>
              <p className="mt-2 text-sm leading-6 text-natural-500">
                輸入或口述專案背景，由 AI 協助規劃受訪角色、訪談目的與關鍵問題。
              </p>
              <span className="mt-6 inline-flex items-center text-sm font-medium text-sage-600">
                開始建立
              </span>
            </div>
          </button>

          <button
            type="button"
            onClick={() => navigate('/projects')}
            aria-label="管理專案"
            className="group rounded-2xl border border-cream-300 bg-white p-7 text-left shadow-natural transition-all hover:-translate-y-0.5 hover:border-sage-200 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-sage-300 focus:ring-offset-2 focus:ring-offset-cream-100"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-cream-300 bg-cream-100 text-natural-600">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 6.5A2.5 2.5 0 016.5 4h3l2 2h6A2.5 2.5 0 0120 8.5v9a2.5 2.5 0 01-2.5 2h-11A2.5 2.5 0 014 17V6.5z" />
                </svg>
              </div>
              <svg className="h-5 w-5 text-natural-400 transition-transform group-hover:translate-x-1 group-hover:text-sage-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
            <h2 className="mt-7 text-xl font-semibold text-natural-800">管理專案</h2>
            <p className="mt-2 text-sm leading-6 text-natural-500">
              查看所有專案的訪談進度、受訪角色與分析結果，繼續尚未完成的工作。
            </p>
            <span className="mt-6 inline-flex items-center text-sm font-medium text-natural-600 group-hover:text-sage-600">
              查看專案
            </span>
          </button>
        </section>

        <div className="mt-10 flex flex-wrap justify-center gap-x-6 gap-y-2 text-xs text-natural-400">
          <span>規劃訪談角色</span>
          <span aria-hidden="true">·</span>
          <span>整理訪談洞察</span>
          <span aria-hidden="true">·</span>
          <span>建立需求證據</span>
        </div>
      </main>
    </div>
  )
}
