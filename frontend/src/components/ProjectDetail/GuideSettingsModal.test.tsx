import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { generateInterviewGuide, voiceToInterviewGuideDraft } from '@/api/projects'
import { GuideSettingsModal } from './GuideSettingsModal'

vi.mock('@/api/projects', () => ({
  generateInterviewGuide: vi.fn(),
  voiceToInterviewGuideDraft: vi.fn(),
}))

describe('GuideSettingsModal voice input', () => {
  afterEach(() => {
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('records spoken preferences, fills the guide draft, and waits for confirmation', async () => {
    vi.mocked(voiceToInterviewGuideDraft).mockResolvedValue({
      transcript: '訪談四十五分鐘，聚焦掛號尖峰和例外，不問系統架構，採探索型。',
      draft: {
        duration_minutes: 45,
        interview_purpose: '了解現有掛號流程',
        focus_topics: '掛號尖峰、例外處理',
        exclude_topics: '系統架構',
        interview_style: 'exploratory',
      },
    })
    const generatedGuide = {
      document_id: 'doc-1',
      prep_session_id: 'prep-1',
      themes: [],
      card_count: 0,
      status: 'ready',
    }
    vi.mocked(generateInterviewGuide).mockResolvedValue(generatedGuide)

    const stopTrack = vi.fn()
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] }),
      },
    })

    class MockMediaRecorder {
      static isTypeSupported = vi.fn(() => true)
      state = 'inactive'
      mimeType = 'audio/webm'
      ondataavailable: ((event: { data: Blob }) => void) | null = null
      onerror: (() => void) | null = null
      onstop: (() => void) | null = null

      start() {
        this.state = 'recording'
      }

      stop() {
        this.state = 'inactive'
        this.ondataavailable?.({ data: new Blob([new Uint8Array(1500)]) })
        this.onstop?.()
      }
    }
    vi.stubGlobal('MediaRecorder', MockMediaRecorder)

    const onGenerated = vi.fn()
    const onClose = vi.fn()
    render(
      <GuideSettingsModal
        profileId="profile-1"
        projectId="proj-1"
        onClose={onClose}
        onGenerated={onGenerated}
      />,
    )

    fireEvent.change(screen.getByLabelText('這次訪談目的'), {
      target: { value: '了解現有掛號流程' },
    })
    fireEvent.change(screen.getByLabelText('聚焦主題'), {
      target: { value: '每日作業' },
    })

    fireEvent.click(screen.getByRole('button', { name: '語音輸入大綱設定' }))
    fireEvent.click(await screen.findByRole('button', { name: '停止並填入大綱設定' }))

    await waitFor(() => {
      expect(voiceToInterviewGuideDraft).toHaveBeenCalledWith(
        'proj-1',
        'profile-1',
        expect.any(Blob),
        {
          duration_minutes: 30,
          interview_purpose: '了解現有掛號流程',
          focus_topics: '每日作業',
          exclude_topics: '',
          interview_style: '',
        },
      )
    })
    expect(screen.getByLabelText('預計訪談時長')).toHaveValue('45')
    expect(screen.getByLabelText('這次訪談目的')).toHaveValue('了解現有掛號流程')
    expect(screen.getByLabelText('聚焦主題')).toHaveValue('掛號尖峰、例外處理')
    expect(screen.getByLabelText('排除主題（不要問）')).toHaveValue('系統架構')
    expect(screen.getByRole('button', { name: /探索型/ })).toHaveClass('bg-sage-50')
    expect(screen.getByRole('status')).toHaveTextContent('已從語音更新設定')
    expect(stopTrack).toHaveBeenCalled()
    expect(generateInterviewGuide).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: '生成訪談大綱' }))
    await waitFor(() => expect(generateInterviewGuide).toHaveBeenCalledWith(
      'proj-1',
      'profile-1',
      {
        duration_minutes: 45,
        interview_purpose: '了解現有掛號流程',
        focus_topics: '掛號尖峰、例外處理',
        exclude_topics: '系統架構',
        interview_style: 'exploratory',
      },
    ))
    expect(onGenerated).toHaveBeenCalledWith('profile-1', generatedGuide)
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })
})
