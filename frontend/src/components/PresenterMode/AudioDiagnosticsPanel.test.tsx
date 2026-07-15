import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { AudioDiagnosticsSnapshot } from '@/hooks/useAudioDiagnostics'
import AudioDiagnosticsPanel from './AudioDiagnosticsPanel'

const diagnostics: AudioDiagnosticsSnapshot = {
  active: true,
  profile: 'standard',
  trackSettings: {
    deviceLabel: 'MacBook Pro 麥克風',
    sampleRate: 48000,
    channelCount: 1,
    echoCancellation: true,
    noiseSuppression: false,
    autoGainControl: true,
  },
  frequencyLevels: { low: 42, mid: 35, high: 18 },
  connectionState: 'connected',
  codec: 'audio/opus · 48000 Hz',
  bytesSent: 2048,
  speechStartedCount: 2,
  speechStoppedCount: 2,
  transcriptDeltaCount: 8,
  transcriptCompletedCount: 1,
  lastCompletedTranscript: '這是一段測試辨識內容',
  events: [],
  analyserError: null,
}

describe('AudioDiagnosticsPanel', () => {
  it('shows actual track settings and frequency bands when expanded', () => {
    render(
      <AudioDiagnosticsPanel
        enabled
        profile="standard"
        diagnostics={diagnostics}
        profileLocked={false}
        onEnabledChange={vi.fn()}
        onProfileChange={vi.fn()}
        onReset={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '音訊診斷' }))

    expect(screen.getByText('MacBook Pro 麥克風')).toBeInTheDocument()
    expect(screen.getByText('48000 Hz')).toBeInTheDocument()
    expect(screen.getByText('低頻')).toBeInTheDocument()
    expect(screen.getByText('中頻')).toBeInTheDocument()
    expect(screen.getByText('高頻')).toBeInTheDocument()
    expect(screen.getByText('這是一段測試辨識內容')).toBeInTheDocument()
  })

  it('switches to the raw profile only when the connection is unlocked', () => {
    const onProfileChange = vi.fn()
    const { rerender } = render(
      <AudioDiagnosticsPanel
        enabled
        profile="standard"
        diagnostics={diagnostics}
        profileLocked
        onEnabledChange={vi.fn()}
        onProfileChange={onProfileChange}
        onReset={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: '音訊診斷' }))

    expect(screen.getByRole('button', { name: '原始音訊' })).toBeDisabled()

    rerender(
      <AudioDiagnosticsPanel
        enabled
        profile="standard"
        diagnostics={diagnostics}
        profileLocked={false}
        onEnabledChange={vi.fn()}
        onProfileChange={onProfileChange}
        onReset={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: '原始音訊' }))

    expect(onProfileChange).toHaveBeenCalledWith('raw')
  })
})
