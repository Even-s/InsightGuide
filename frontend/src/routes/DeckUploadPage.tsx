/**
 * Deck Upload Page - Milestone 1
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { documentsAPI } from '@/api/documents'
import { useDocumentStore } from '@/stores/documentStore'

export default function DeckUploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const navigate = useNavigate()
  const { setCurrentDocument, setError } = useDocumentStore()

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
    }
  }

  const handleUpload = async () => {
    if (!file) return

    setUploading(true)
    setError(null)

    try {
      // Upload the document
      const document = await documentsAPI.uploadDocument(file)
      setCurrentDocument(document)

      // Navigate to editor - prep session is auto-created by backend
      navigate(`/editor/${document.id}`)
    } catch (error: unknown) {
      setError(error instanceof Error ? error.message : 'Failed to upload document')
      alert(`❌ 上傳失敗: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-cream-100">
      <nav className="mx-auto flex w-full max-w-7xl flex-none items-center justify-between px-8 py-5">
        <h1 className="text-2xl font-medium leading-relaxed tracking-wide text-natural-700">InsightGuide</h1>
        <button
          onClick={() => navigate('/prep-sessions')}
          className="rounded-lg px-4 py-2 text-sm leading-relaxed tracking-wide text-sage-600 underline transition-colors hover:bg-cream-50 hover:text-sage-700"
        >
          文件管理
        </button>
      </nav>

      <main className="mx-auto grid w-full max-w-2xl flex-1 grid-rows-[auto_auto_1fr] px-8 pb-12 pt-12">
        <div className="text-center">
          <h2 className="text-3xl font-semibold leading-tight text-natural-800">
            InsightGuide - AI 需求訪談助手
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-base leading-loose text-natural-600">
            從需求文件分析、訪談問題準備到即時評估，InsightGuide 協助你把每個關鍵需求問清楚。
          </p>
        </div>

        <div className="flex items-center justify-center py-14">
          <div className="mx-auto flex max-w-xl flex-col gap-3 text-sm text-natural-600 sm:flex-row sm:items-center sm:justify-center sm:gap-0">
            <span className="font-medium text-natural-700">上傳文件</span>
            <span className="hidden h-px w-12 bg-cream-300 sm:mx-4 sm:block" />
            <span className="font-medium text-natural-700">整理問題</span>
            <span className="hidden h-px w-12 bg-cream-300 sm:mx-4 sm:block" />
            <span className="font-medium text-natural-700">追蹤充分度</span>
          </div>
        </div>

        <div className="flex items-center justify-center">
          <div className="w-full max-w-xl rounded-lg border border-cream-300 bg-white p-8 shadow-natural">
            <div className="space-y-6">
              <div>
                <label className="mb-3 block text-base font-medium leading-relaxed tracking-wide text-natural-700">
                  選擇需求文件
                </label>
                <div className="rounded-xl border-2 border-dashed border-cream-300 bg-cream-50 p-6 transition-all hover:border-sage-300 hover:bg-sage-50">
                  <input
                    type="file"
                    accept=".pdf,.docx,.doc,.md,.txt"
                    onChange={handleFileChange}
                    className="block w-full text-sm text-natural-600
                      file:mr-4 file:py-3 file:px-6
                      file:rounded-xl file:border-0
                      file:text-sm file:font-medium file:tracking-wide
                      file:bg-sage-400 file:text-white
                      hover:file:bg-sage-500 file:shadow-natural
                      file:transition-colors cursor-pointer"
                  />
                  <p className="mt-4 text-center text-xs leading-relaxed tracking-wide text-natural-500">
                    支援格式：PDF、Word (.docx, .doc)、Markdown (.md)、Text (.txt)<br/>
                    檔案大小上限：50MB
                  </p>
                </div>
              </div>

              {file && (
                <div className="bg-sage-50 rounded-xl p-6 border border-sage-200 shadow-natural">
                  <div className="flex items-center gap-3 mb-2">
                    <svg className="w-6 h-6 text-sage-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-natural-700 leading-relaxed">
                        {file.name}
                      </p>
                      <p className="text-xs text-natural-600 leading-relaxed tracking-wide">
                        {(file.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                  </div>
                </div>
              )}

              <button
                onClick={handleUpload}
                disabled={!file || uploading}
                className="w-full bg-sage-400 text-white py-4 px-6 rounded-xl font-medium tracking-wide shadow-natural text-base leading-relaxed
                  hover:bg-sage-500 disabled:bg-cream-300 disabled:text-natural-400 disabled:cursor-not-allowed
                  transition-all transform hover:scale-[1.02] disabled:hover:scale-100"
              >
                {uploading ? '上傳中...' : '上傳並開始分析'}
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
