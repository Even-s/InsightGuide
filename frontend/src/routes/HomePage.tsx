import { useNavigate } from 'react-router-dom'

export default function HomePage() {
  const navigate = useNavigate()

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

        <section className="mt-12 grid w-full gap-5 md:grid-cols-2" aria-label="專案入口">
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
