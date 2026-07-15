import { describe, expect, it } from 'vitest'
import { getAudioConstraints } from './useAudioDiagnostics'

describe('getAudioConstraints', () => {
  it('keeps the current processing in the standard profile', () => {
    expect(getAudioConstraints('standard')).toEqual({
      echoCancellation: true,
      noiseSuppression: false,
      autoGainControl: true,
    })
  })

  it('disables browser processing in the raw A/B profile', () => {
    expect(getAudioConstraints('raw')).toEqual({
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false,
      channelCount: 1,
      sampleRate: 48000,
    })
  })
})
