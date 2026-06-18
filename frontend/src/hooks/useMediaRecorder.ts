import { useCallback, useRef, useState } from 'react'

interface UseMediaRecorderOptions {
  mimeType?: string
}

export function useMediaRecorder({ mimeType }: UseMediaRecorderOptions = {}) {
  const [isRecording, setIsRecording] = useState(false)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const preferredMime = mimeType || (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ? 'audio/webm;codecs=opus'
    : 'audio/webm')

  const flushBlob = useCallback(() => {
    if (chunksRef.current.length === 0) return null

    const blob = new Blob(chunksRef.current, { type: preferredMime })
    chunksRef.current = []
    return blob
  }, [preferredMime])

  const start = useCallback((stream: MediaStream) => {
    if (recorderRef.current && recorderRef.current.state !== 'inactive') return

    const recorder = new MediaRecorder(stream, { mimeType: preferredMime })

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        chunksRef.current.push(e.data)
      }
    }

    recorder.onstop = () => {
      setIsRecording(false)
      recorderRef.current = null
    }

    recorderRef.current = recorder
    recorder.start(5000)
    setIsRecording(true)
  }, [preferredMime])

  const stopAsync = useCallback((): Promise<Blob | null> => {
    const recorder = recorderRef.current
    if (!recorder || recorder.state === 'inactive') {
      recorderRef.current = null
      setIsRecording(false)
      return Promise.resolve(flushBlob())
    }

    return new Promise<Blob | null>((resolve) => {
      recorder.onstop = () => {
        setIsRecording(false)
        recorderRef.current = null
        resolve(flushBlob())
      }
      recorder.requestData()
      recorder.stop()
    })
  }, [flushBlob])

  return { start, stop: stopAsync, isRecording: isRecording }
}
