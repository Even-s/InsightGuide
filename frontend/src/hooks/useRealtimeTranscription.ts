import { useCallback, useEffect, useRef, useState } from 'react'
import { realtimeAPI } from '@/api/realtime'
import {
  getAudioConstraints,
  useAudioDiagnostics,
  type AudioProcessingProfile,
} from '@/hooks/useAudioDiagnostics'

const OPENAI_REALTIME_WEBRTC_URL = 'https://api.openai.com/v1/realtime/calls'

type RealtimeTranscriptionStatus = 'idle' | 'connecting' | 'connected' | 'error'

interface RealtimeEvent {
  type?: string
  item_id?: string
  event_id?: string
  delta?: string
  transcript?: string
  error?: {
    message?: string
    code?: string
  }
}

interface TranscriptCompletedPayload {
  transcript: string
  itemId?: string
  eventId?: string
  startedAt?: string
  endedAt?: string
}

interface UseRealtimeTranscriptionOptions {
  onTranscriptDelta?: (delta: string, itemId?: string) => void
  onTranscriptCompleted?: (payload: TranscriptCompletedPayload) => void
  onSpeechStarted?: () => void
  onMediaStreamReady?: (stream: MediaStream) => void
  diagnosticsEnabled?: boolean
  audioProcessingProfile?: AudioProcessingProfile
}

function getErrorMessage(error: unknown) {
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof error.response === 'object' &&
    error.response !== null &&
    'data' in error.response
  ) {
    const data = error.response.data
    if (typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string') {
      return data.detail
    }
    if (typeof data === 'string' && data.trim()) return data
  }
  if (error instanceof Error) return error.message
  return 'Realtime transcription failed'
}

function waitForIceGatheringComplete(peerConnection: RTCPeerConnection, timeoutMs = 3000) {
  if (peerConnection.iceGatheringState === 'complete') return Promise.resolve()

  return new Promise<void>((resolve) => {
    const timeout = window.setTimeout(() => {
      peerConnection.removeEventListener('icegatheringstatechange', handleStateChange)
      resolve()
    }, timeoutMs)

    function handleStateChange() {
      if (peerConnection.iceGatheringState !== 'complete') return
      window.clearTimeout(timeout)
      peerConnection.removeEventListener('icegatheringstatechange', handleStateChange)
      resolve()
    }

    peerConnection.addEventListener('icegatheringstatechange', handleStateChange)
  })
}

export function useRealtimeTranscription({
  onTranscriptDelta,
  onTranscriptCompleted,
  onSpeechStarted,
  onMediaStreamReady,
  diagnosticsEnabled = false,
  audioProcessingProfile = 'standard',
}: UseRealtimeTranscriptionOptions = {}) {
  const [status, _setStatus] = useState<RealtimeTranscriptionStatus>('idle')
  const statusRef = useRef<RealtimeTranscriptionStatus>('idle')
  const setStatus = (s: RealtimeTranscriptionStatus) => { statusRef.current = s; _setStatus(s) }
  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const peerConnectionRef = useRef<RTCPeerConnection | null>(null)
  const dataChannelRef = useRef<RTCDataChannel | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const startTokenRef = useRef(0)
  const deltaBufferRef = useRef('')
  const deltaItemIdRef = useRef<string | undefined>()
  const speechStartedAtRef = useRef<string | undefined>()
  const firstDeltaAtRef = useRef<string | undefined>()
  const deltaFlushTimeoutRef = useRef<number | null>(null)
  const lastCompletedTextRef = useRef('')
  const callbacksRef = useRef({
    onTranscriptDelta,
    onTranscriptCompleted,
    onSpeechStarted,
    onMediaStreamReady,
  })
  const {
    snapshot: audioDiagnostics,
    observeStream: observeDiagnosticStream,
    observePeerConnection: observeDiagnosticPeerConnection,
    recordRealtimeEvent: recordDiagnosticEvent,
    updateConnectionState: updateDiagnosticConnectionState,
    reset: resetAudioDiagnostics,
  } = useAudioDiagnostics(diagnosticsEnabled, audioProcessingProfile)

  useEffect(() => {
    callbacksRef.current = {
      onTranscriptDelta,
      onTranscriptCompleted,
      onSpeechStarted,
      onMediaStreamReady,
    }
  }, [onMediaStreamReady, onSpeechStarted, onTranscriptCompleted, onTranscriptDelta])

  const cleanupConnection = useCallback(() => {
    observeDiagnosticPeerConnection(null)
    observeDiagnosticStream(null)
    dataChannelRef.current?.close()
    dataChannelRef.current = null

    peerConnectionRef.current?.getSenders().forEach((sender) => {
      sender.track?.stop()
    })
    peerConnectionRef.current?.close()
    peerConnectionRef.current = null

    mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
    mediaStreamRef.current = null

    if (deltaFlushTimeoutRef.current) {
      clearTimeout(deltaFlushTimeoutRef.current)
      deltaFlushTimeoutRef.current = null
    }
    deltaBufferRef.current = ''
    deltaItemIdRef.current = undefined
    speechStartedAtRef.current = undefined
    firstDeltaAtRef.current = undefined

    setIsRecording(false)
    setIsTranscribing(false)
  }, [observeDiagnosticPeerConnection, observeDiagnosticStream])

  const emitCompletedTranscript = useCallback((transcript: string, itemId?: string, eventId?: string) => {
    const text = transcript.trim()
    if (!text || text === lastCompletedTextRef.current) return

    const startedAt = speechStartedAtRef.current ?? firstDeltaAtRef.current
    const endedAt = new Date().toISOString()
    lastCompletedTextRef.current = text
    speechStartedAtRef.current = undefined
    firstDeltaAtRef.current = undefined
    setIsTranscribing(false)
    callbacksRef.current.onTranscriptCompleted?.({
      transcript: text,
      itemId,
      eventId,
      startedAt,
      endedAt,
    })
  }, [])

  const flushDeltaBuffer = useCallback(() => {
    if (deltaFlushTimeoutRef.current) {
      clearTimeout(deltaFlushTimeoutRef.current)
      deltaFlushTimeoutRef.current = null
    }

    const text = deltaBufferRef.current.trim()
    const itemId = deltaItemIdRef.current
    deltaBufferRef.current = ''
    deltaItemIdRef.current = undefined

    emitCompletedTranscript(text, itemId)
  }, [emitCompletedTranscript])

  const scheduleDeltaFlush = useCallback((buffer: string) => {
    if (deltaFlushTimeoutRef.current) {
      clearTimeout(deltaFlushTimeoutRef.current)
    }

    const trimmed = buffer.trim()
    const looksComplete = /[。！？!?]\s*$/.test(trimmed)
    const delayMs = looksComplete ? 800 : 2500

    deltaFlushTimeoutRef.current = window.setTimeout(() => {
      flushDeltaBuffer()
    }, delayMs)
  }, [flushDeltaBuffer])

  const handleRealtimeEvent = useCallback((message: RealtimeEvent) => {
    switch (message.type) {
      case 'input_audio_buffer.speech_started':
        recordDiagnosticEvent('speech_started')
        setIsTranscribing(false)
        if (deltaBufferRef.current.trim()) {
          flushDeltaBuffer()
        }
        speechStartedAtRef.current = new Date().toISOString()
        firstDeltaAtRef.current = undefined
        callbacksRef.current.onSpeechStarted?.()
        break

      case 'input_audio_buffer.speech_stopped':
        recordDiagnosticEvent('speech_stopped')
        setIsTranscribing(true)
        if (deltaBufferRef.current.trim()) {
          flushDeltaBuffer()
        }
        break

      case 'conversation.item.input_audio_transcription.delta':
        if (message.delta) {
          recordDiagnosticEvent('transcript_delta')
          firstDeltaAtRef.current = firstDeltaAtRef.current ?? new Date().toISOString()
          deltaBufferRef.current += message.delta
          deltaItemIdRef.current = message.item_id ?? deltaItemIdRef.current
          setIsTranscribing(true)
          callbacksRef.current.onTranscriptDelta?.(message.delta, message.item_id)
          scheduleDeltaFlush(deltaBufferRef.current)
        }
        break

      case 'conversation.item.input_audio_transcription.completed':
        if (deltaFlushTimeoutRef.current) {
          clearTimeout(deltaFlushTimeoutRef.current)
          deltaFlushTimeoutRef.current = null
        }
        deltaBufferRef.current = ''
        deltaItemIdRef.current = undefined

        if (message.transcript?.trim()) {
          recordDiagnosticEvent('transcript_completed', message.transcript.trim())
          emitCompletedTranscript(message.transcript, message.item_id, message.event_id)
        }
        break

      case 'conversation.item.input_audio_transcription.failed': {
        recordDiagnosticEvent('transcript_failed', message.error?.message)
        setIsTranscribing(false)
        const realtimeError = new Error(message.error?.message ?? 'Realtime transcription failed')
        setError(realtimeError)
        setStatus('error')
        break
      }

      case 'error': {
        recordDiagnosticEvent('realtime_error', message.error?.message)
        const realtimeError = new Error(message.error?.message ?? 'Realtime API error')
        setError(realtimeError)
        setStatus('error')
        break
      }

      default:
        break
    }
  }, [emitCompletedTranscript, flushDeltaBuffer, recordDiagnosticEvent, scheduleDeltaFlush])

  const startTranscription = useCallback(async () => {
    if (peerConnectionRef.current) return
    if (statusRef.current === 'connecting') return
    if (!navigator.mediaDevices?.getUserMedia) {
      setError(new Error('此瀏覽器不支援麥克風錄音'))
      setStatus('error')
      return
    }

    const startToken = startTokenRef.current + 1
    startTokenRef.current = startToken

    try {
      setError(null)
      setStatus('connecting')
      setIsTranscribing(false)

      const session = await realtimeAPI.createTranscriptionSession()
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: getAudioConstraints(audioProcessingProfile),
      })

      if (startTokenRef.current !== startToken) {
        mediaStream.getTracks().forEach((track) => track.stop())
        return
      }

      callbacksRef.current.onMediaStreamReady?.(mediaStream)
      observeDiagnosticStream(mediaStream)

      const peerConnection = new RTCPeerConnection()
      const dataChannel = peerConnection.createDataChannel('oai-events')

      mediaStream.getTracks().forEach((track) => {
        peerConnection.addTrack(track, mediaStream)
      })

      dataChannel.onopen = () => {
        setStatus('connected')
        setIsRecording(true)
      }

      dataChannel.onmessage = (event) => {
        try {
          handleRealtimeEvent(JSON.parse(event.data) as RealtimeEvent)
        } catch (parseError) {
          console.warn('Unable to parse Realtime event', parseError)
        }
      }

      dataChannel.onerror = () => {
        setError(new Error('Realtime transcription data channel failed'))
        setStatus('error')
      }

      peerConnection.onconnectionstatechange = () => {
        updateDiagnosticConnectionState(peerConnection.connectionState)
        if (peerConnection.connectionState === 'connected') {
          setStatus('connected')
          setIsRecording(true)
        }

        if (['failed', 'disconnected', 'closed'].includes(peerConnection.connectionState)) {
          if (peerConnectionRef.current === peerConnection) {
            setIsRecording(false)
            setStatus('error')
            setError(new Error('即時轉錄連線中斷，請重新開始'))
            // Clean up so startTranscription can be called again
            peerConnectionRef.current = null
            dataChannelRef.current = null
            mediaStreamRef.current?.getTracks().forEach(t => t.stop())
            mediaStreamRef.current = null
          }
        }
      }

      peerConnectionRef.current = peerConnection
      dataChannelRef.current = dataChannel
      mediaStreamRef.current = mediaStream
      observeDiagnosticPeerConnection(peerConnection)

      const offer = await peerConnection.createOffer()
      await peerConnection.setLocalDescription(offer)
      await waitForIceGatheringComplete(peerConnection)

      const sdpResponse = await fetch(OPENAI_REALTIME_WEBRTC_URL, {
        method: 'POST',
        body: peerConnection.localDescription?.sdp ?? offer.sdp,
        headers: {
          Authorization: `Bearer ${session.token}`,
          'Content-Type': 'application/sdp',
        },
      })

      if (!sdpResponse.ok) {
        const detail = await sdpResponse.text()
        throw new Error(`OpenAI Realtime SDP exchange failed: ${detail || sdpResponse.statusText}`)
      }

      await peerConnection.setRemoteDescription({
        type: 'answer',
        sdp: await sdpResponse.text(),
      })
    } catch (err) {
      cleanupConnection()
      setError(new Error(getErrorMessage(err)))
      setStatus('error')
    }
  }, [
    audioProcessingProfile,
    cleanupConnection,
    handleRealtimeEvent,
    observeDiagnosticPeerConnection,
    observeDiagnosticStream,
    updateDiagnosticConnectionState,
  ])

  const stopTranscription = useCallback(() => {
    startTokenRef.current += 1
    if (deltaBufferRef.current.trim()) {
      flushDeltaBuffer()
    }
    cleanupConnection()
    setStatus('idle')
  }, [cleanupConnection, flushDeltaBuffer])

  useEffect(() => {
    return () => {
      startTokenRef.current += 1
      cleanupConnection()
    }
  }, [cleanupConnection])

  return {
    status,
    isRecording,
    isTranscribing,
    error,
    diagnostics: audioDiagnostics,
    resetDiagnostics: resetAudioDiagnostics,
    startTranscription,
    stopTranscription,
    mediaStream: mediaStreamRef.current,
  }
}
