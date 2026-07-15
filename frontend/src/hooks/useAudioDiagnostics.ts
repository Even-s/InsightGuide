import { useCallback, useEffect, useRef, useState } from 'react'

export type AudioProcessingProfile = 'standard' | 'raw'

export interface FrequencyLevels {
  low: number
  mid: number
  high: number
}

export interface AudioTrackSettingsSnapshot {
  deviceLabel: string
  sampleRate?: number
  sampleSize?: number
  channelCount?: number
  echoCancellation?: boolean
  noiseSuppression?: boolean
  autoGainControl?: boolean
}

export interface AudioDiagnosticEvent {
  id: number
  time: string
  type: string
  detail?: string
}

export interface AudioDiagnosticsSnapshot {
  active: boolean
  profile: AudioProcessingProfile
  trackSettings: AudioTrackSettingsSnapshot | null
  frequencyLevels: FrequencyLevels | null
  connectionState: RTCPeerConnectionState | 'idle'
  codec: string | null
  bytesSent: number
  speechStartedCount: number
  speechStoppedCount: number
  transcriptDeltaCount: number
  transcriptCompletedCount: number
  lastCompletedTranscript: string
  events: AudioDiagnosticEvent[]
  analyserError: string | null
}

const initialSnapshot = (profile: AudioProcessingProfile): AudioDiagnosticsSnapshot => ({
  active: false,
  profile,
  trackSettings: null,
  frequencyLevels: null,
  connectionState: 'idle',
  codec: null,
  bytesSent: 0,
  speechStartedCount: 0,
  speechStoppedCount: 0,
  transcriptDeltaCount: 0,
  transcriptCompletedCount: 0,
  lastCompletedTranscript: '',
  events: [],
  analyserError: null,
})

export function getAudioConstraints(profile: AudioProcessingProfile): MediaTrackConstraints {
  if (profile === 'raw') {
    return {
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false,
      channelCount: 1,
      sampleRate: 48000,
    }
  }

  return {
    echoCancellation: true,
    noiseSuppression: false,
    autoGainControl: true,
  }
}

function summarizeTrack(track: MediaStreamTrack): AudioTrackSettingsSnapshot {
  const settings = track.getSettings()
  return {
    deviceLabel: track.label || '瀏覽器未提供裝置名稱',
    sampleRate: settings.sampleRate,
    sampleSize: settings.sampleSize,
    channelCount: settings.channelCount,
    echoCancellation: settings.echoCancellation,
    noiseSuppression: settings.noiseSuppression,
    autoGainControl: settings.autoGainControl,
  }
}

function calculateBandLevel(
  values: Uint8Array,
  sampleRate: number,
  fftSize: number,
  minFrequency: number,
  maxFrequency: number,
) {
  const binWidth = sampleRate / fftSize
  const start = Math.max(0, Math.floor(minFrequency / binWidth))
  const end = Math.min(values.length - 1, Math.ceil(maxFrequency / binWidth))
  if (end < start) return 0

  let sumSquares = 0
  let count = 0
  for (let index = start; index <= end; index += 1) {
    const normalized = values[index] / 255
    sumSquares += normalized * normalized
    count += 1
  }

  return count > 0 ? Math.round(Math.sqrt(sumSquares / count) * 100) : 0
}

export function useAudioDiagnostics(
  enabled: boolean,
  profile: AudioProcessingProfile,
) {
  const [snapshot, setSnapshot] = useState<AudioDiagnosticsSnapshot>(() => initialSnapshot(profile))
  const streamRef = useRef<MediaStream | null>(null)
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const animationFrameRef = useRef<number | null>(null)
  const statsIntervalRef = useRef<number | null>(null)
  const lastFrequencyUpdateRef = useRef(0)
  const eventIdRef = useRef(0)
  const enabledRef = useRef(enabled)
  const profileRef = useRef(profile)

  useEffect(() => {
    enabledRef.current = enabled
    profileRef.current = profile
  }, [enabled, profile])

  const appendEvent = useCallback((type: string, detail?: string) => {
    if (!enabledRef.current) return
    eventIdRef.current += 1
    const nextEvent: AudioDiagnosticEvent = {
      id: eventIdRef.current,
      time: new Date().toLocaleTimeString('zh-TW', { hour12: false }),
      type,
      detail,
    }
    setSnapshot(previous => ({
      ...previous,
      events: [...previous.events, nextEvent].slice(-12),
    }))
  }, [])

  const stopAnalyser = useCallback(() => {
    if (animationFrameRef.current !== null) {
      window.cancelAnimationFrame(animationFrameRef.current)
      animationFrameRef.current = null
    }
    sourceNodeRef.current?.disconnect()
    analyserRef.current?.disconnect()
    sourceNodeRef.current = null
    analyserRef.current = null
    if (audioContextRef.current) {
      void audioContextRef.current.close()
      audioContextRef.current = null
    }
  }, [])

  const startAnalyser = useCallback((stream: MediaStream) => {
    stopAnalyser()
    const track = stream.getAudioTracks()[0]
    if (!track) {
      setSnapshot(previous => ({ ...previous, analyserError: '找不到麥克風音訊軌' }))
      return
    }

    try {
      const context = new AudioContext()
      const source = context.createMediaStreamSource(new MediaStream([track]))
      const analyser = context.createAnalyser()
      analyser.fftSize = 2048
      analyser.smoothingTimeConstant = 0.72
      source.connect(analyser)

      audioContextRef.current = context
      sourceNodeRef.current = source
      analyserRef.current = analyser

      const values = new Uint8Array(analyser.frequencyBinCount)
      const sample = (timestamp: number) => {
        if (!enabledRef.current || analyserRef.current !== analyser) return
        if (timestamp - lastFrequencyUpdateRef.current >= 250) {
          analyser.getByteFrequencyData(values)
          setSnapshot(previous => ({
            ...previous,
            active: track.readyState === 'live',
            trackSettings: summarizeTrack(track),
            frequencyLevels: {
              low: calculateBandLevel(values, context.sampleRate, analyser.fftSize, 80, 300),
              mid: calculateBandLevel(values, context.sampleRate, analyser.fftSize, 300, 2000),
              high: calculateBandLevel(values, context.sampleRate, analyser.fftSize, 2000, 8000),
            },
            analyserError: null,
          }))
          lastFrequencyUpdateRef.current = timestamp
        }
        animationFrameRef.current = window.requestAnimationFrame(sample)
      }
      animationFrameRef.current = window.requestAnimationFrame(sample)
    } catch (error) {
      const message = error instanceof Error ? error.message : '無法啟動頻譜分析'
      setSnapshot(previous => ({ ...previous, analyserError: message }))
    }
  }, [stopAnalyser])

  const stopStats = useCallback(() => {
    if (statsIntervalRef.current !== null) {
      window.clearInterval(statsIntervalRef.current)
      statsIntervalRef.current = null
    }
  }, [])

  const collectPeerStats = useCallback(async () => {
    const peerConnection = peerConnectionRef.current
    if (!peerConnection || !enabledRef.current) return

    try {
      const reports = await peerConnection.getStats()
      let codec: string | null = null
      let bytesSent = 0
      reports.forEach(report => {
        if (report.type !== 'outbound-rtp' || (report.kind !== 'audio' && report.mediaType !== 'audio')) return
        bytesSent = typeof report.bytesSent === 'number' ? report.bytesSent : bytesSent
        const codecReport = report.codecId ? reports.get(report.codecId) : undefined
        if (codecReport?.mimeType) {
          codec = `${codecReport.mimeType}${codecReport.clockRate ? ` · ${codecReport.clockRate} Hz` : ''}`
        }
      })
      setSnapshot(previous => ({
        ...previous,
        connectionState: peerConnection.connectionState,
        codec,
        bytesSent,
      }))
    } catch {
      // A connection can disappear while getStats is resolving; the next state event is enough.
    }
  }, [])

  const startStats = useCallback(() => {
    stopStats()
    void collectPeerStats()
    statsIntervalRef.current = window.setInterval(() => {
      void collectPeerStats()
    }, 1000)
  }, [collectPeerStats, stopStats])

  useEffect(() => {
    if (!enabled) {
      stopAnalyser()
      stopStats()
      setSnapshot(previous => ({
        ...previous,
        active: false,
        profile,
        frequencyLevels: null,
      }))
      return
    }

    setSnapshot(previous => ({ ...previous, profile }))
    if (streamRef.current) startAnalyser(streamRef.current)
    if (peerConnectionRef.current) startStats()
  }, [enabled, profile, startAnalyser, startStats, stopAnalyser, stopStats])

  useEffect(() => () => {
    stopAnalyser()
    stopStats()
  }, [stopAnalyser, stopStats])

  const observeStream = useCallback((stream: MediaStream | null) => {
    streamRef.current = stream
    if (!stream) {
      stopAnalyser()
      setSnapshot(previous => ({ ...previous, active: false, frequencyLevels: null }))
      return
    }

    const track = stream.getAudioTracks()[0]
    if (enabledRef.current && track) {
      setSnapshot(previous => ({
        ...previous,
        active: track.readyState === 'live',
        profile: profileRef.current,
        trackSettings: summarizeTrack(track),
      }))
      appendEvent('麥克風已連接', track.label || undefined)
      startAnalyser(stream)
    }
  }, [appendEvent, startAnalyser, stopAnalyser])

  const observePeerConnection = useCallback((peerConnection: RTCPeerConnection | null) => {
    peerConnectionRef.current = peerConnection
    if (!peerConnection) {
      stopStats()
      setSnapshot(previous => ({ ...previous, connectionState: 'idle' }))
      return
    }

    if (enabledRef.current) {
      setSnapshot(previous => ({ ...previous, connectionState: peerConnection.connectionState }))
      startStats()
    }
  }, [startStats, stopStats])

  const recordRealtimeEvent = useCallback((type: string, detail?: string) => {
    if (!enabledRef.current) return

    setSnapshot(previous => {
      const next = { ...previous }
      if (type === 'speech_started') next.speechStartedCount += 1
      if (type === 'speech_stopped') next.speechStoppedCount += 1
      if (type === 'transcript_delta') next.transcriptDeltaCount += 1
      if (type === 'transcript_completed') {
        next.transcriptCompletedCount += 1
        next.lastCompletedTranscript = detail ?? ''
      }
      return next
    })

    if (type !== 'transcript_delta') {
      appendEvent(type, detail?.slice(0, 80))
    }
  }, [appendEvent])

  const updateConnectionState = useCallback((connectionState: RTCPeerConnectionState | 'idle') => {
    if (!enabledRef.current) return
    setSnapshot(previous => ({ ...previous, connectionState }))
  }, [])

  const reset = useCallback(() => {
    const trackSettings = streamRef.current?.getAudioTracks()[0]
      ? summarizeTrack(streamRef.current.getAudioTracks()[0])
      : null
    setSnapshot({
      ...initialSnapshot(profileRef.current),
      active: Boolean(streamRef.current?.active),
      trackSettings,
      connectionState: peerConnectionRef.current?.connectionState ?? 'idle',
    })
  }, [])

  return {
    snapshot,
    observeStream,
    observePeerConnection,
    recordRealtimeEvent,
    updateConnectionState,
    reset,
  }
}
