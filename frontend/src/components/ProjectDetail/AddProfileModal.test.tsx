import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createStakeholder, voiceToStakeholderProfileDraft } from '@/api/projects'
import { AddProfileModal } from './AddProfileModal'

vi.mock('@/api/projects', () => ({
  createStakeholder: vi.fn(),
  voiceToStakeholderProfileDraft: vi.fn(),
}))

describe('AddProfileModal voice input', () => {
  afterEach(() => {
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('records, fills every participant field, and keeps creation confirmable', async () => {
    vi.mocked(voiceToStakeholderProfileDraft).mockResolvedValue({
      transcript: '王小明是門診櫃台組長，熟悉掛號流程，但不熟系統架構。',
      draft: {
        name: '王小明',
        role_title: '門診櫃台組長',
        department: '門診行政部',
        stakeholder_type: 'operations',
        expertise_tags: ['掛號流程', '尖峰人流處理'],
        knowledge_boundaries: ['系統架構'],
      },
    })
    vi.mocked(createStakeholder).mockResolvedValue({} as never)

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

    const onAdd = vi.fn()
    render(
      <AddProfileModal
        slotId="slot-ops"
        projectId="proj-1"
        onClose={vi.fn()}
        onAdd={onAdd}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '語音輸入' }))
    fireEvent.click(await screen.findByRole('button', { name: '停止並填入' }))

    await waitFor(() => {
      expect(voiceToStakeholderProfileDraft).toHaveBeenCalledWith(
        'proj-1',
        'slot-ops',
        expect.any(Blob),
      )
    })
    expect(screen.getByLabelText(/姓名/)).toHaveValue('王小明')
    expect(screen.getByLabelText('職稱')).toHaveValue('門診櫃台組長')
    expect(screen.getByLabelText('部門')).toHaveValue('門診行政部')
    expect(screen.getByLabelText('角色類型')).toHaveValue('operations')
    expect(screen.getByLabelText(/專長領域/)).toHaveValue('掛號流程, 尖峰人流處理')
    expect(screen.getByLabelText(/不熟悉領域/)).toHaveValue('系統架構')
    expect(stopTrack).toHaveBeenCalled()
    expect(screen.getByRole('status')).toHaveTextContent('已從語音填入')

    fireEvent.click(screen.getByRole('button', { name: '新增' }))
    await waitFor(() => expect(createStakeholder).toHaveBeenCalledWith('proj-1', {
      slot_id: 'slot-ops',
      name: '王小明',
      role_title: '門診櫃台組長',
      department: '門診行政部',
      stakeholder_type: 'operations',
      expertise_tags: ['掛號流程', '尖峰人流處理'],
      knowledge_boundaries: ['系統架構'],
    }))
    await waitFor(() => expect(onAdd).toHaveBeenCalled())
  })
})
