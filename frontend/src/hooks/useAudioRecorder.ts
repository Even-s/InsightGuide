/**
 * BACKUP/FALLBACK Audio Recorder Hook
 *
 * NOTE: This is a BACKUP implementation using MediaRecorder API (HTTP upload).
 * It is NOT used in the main presenter mode flow.
 *
 * The MAIN audio system for Presenter Mode uses:
 * - useRealtimeTranscription hook (WebRTC)
 * - OpenAI Realtime Transcription API
 * - Direct audio streaming to OpenAI
 *
 * This hook can serve as:
 * - Fallback if WebRTC is not supported
 * - Alternative for saving audio files
 * - Development/testing purposes
 */

import { useState, useRef, useCallback, useEffect } from 'react';

interface UseAudioRecorderOptions {
  chunkDuration?: number;
  onChunkReady?: (blob: Blob) => void | Promise<void>;
  onSpeechDetected?: () => void;
}

/**
 * Hook for recording audio using MediaRecorder API.
 *
 * ⚠️ BACKUP ONLY - Main presenter mode uses useRealtimeTranscription (WebRTC)
 */
export function useAudioRecorder({
  chunkDuration = 3000, // Reduced from 5000ms to 3000ms for faster response
  onChunkReady,
  onSpeechDetected
}: UseAudioRecorderOptions = {}) {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [permissionGranted, setPermissionGranted] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const onChunkReadyRef = useRef(onChunkReady);
  const onSpeechDetectedRef = useRef(onSpeechDetected);
  const chunkTimerRef = useRef<number | null>(null);
  const shouldContinueRef = useRef(false);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);

  useEffect(() => {
    onChunkReadyRef.current = onChunkReady;
    onSpeechDetectedRef.current = onSpeechDetected;
  }, [onChunkReady, onSpeechDetected]);

  function getSupportedMimeType() {
    const candidates = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
    ];

    return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate));
  }

  const monitorAudioLevel = useCallback(() => {
    if (!analyserRef.current || !shouldContinueRef.current) return;

    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
    let speechDetectedCount = 0;
    const requiredDetections = 3; // Need 3 consecutive detections to confirm speech

    const checkLevel = () => {
      if (!analyserRef.current || !shouldContinueRef.current) return;

      analyserRef.current.getByteFrequencyData(dataArray);
      const average = dataArray.reduce((sum, value) => sum + value, 0) / dataArray.length;

      // Higher threshold to avoid false positives from background noise
      if (average > 50) {
        speechDetectedCount++;
        if (speechDetectedCount >= requiredDetections) {
          onSpeechDetectedRef.current?.();
          speechDetectedCount = 0; // Reset counter
        }
      } else {
        speechDetectedCount = 0; // Reset if volume drops
      }

      if (shouldContinueRef.current) {
        requestAnimationFrame(checkLevel);
      }
    };

    checkLevel();
  }, []);

  const requestPermission = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000
        }
      });

      streamRef.current = stream;

      // Set up audio analysis for speech detection
      try {
        const audioContext = new AudioContext();
        const analyser = audioContext.createAnalyser();
        const source = audioContext.createMediaStreamSource(stream);

        analyser.fftSize = 256;
        source.connect(analyser);

        audioContextRef.current = audioContext;
        analyserRef.current = analyser;

        // Start monitoring audio level
        monitorAudioLevel();
      } catch (analyserErr) {
        console.warn('Audio analysis setup failed:', analyserErr);
      }

      setPermissionGranted(true);
      setError(null);
      return true;
    } catch (err) {
      setError(err as Error);
      setPermissionGranted(false);
      return false;
    }
  }, [monitorAudioLevel]);

  const startRecorderSegment = useCallback(() => {
    if (!streamRef.current || !shouldContinueRef.current) return;
    
    try {
      const mimeType = getSupportedMimeType();
      const mediaRecorder = new MediaRecorder(
        streamRef.current!,
        mimeType ? { mimeType } : undefined
      );

      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 1024) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        if (audioChunksRef.current.length > 0) {
          const type = mediaRecorder.mimeType || mimeType || 'audio/webm';
          const audioBlob = new Blob(audioChunksRef.current, { type });
          void onChunkReadyRef.current?.(audioBlob);
          audioChunksRef.current = [];
        }

        if (shouldContinueRef.current) {
          window.setTimeout(startRecorderSegment, 100);
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();

      chunkTimerRef.current = window.setTimeout(() => {
        if (mediaRecorder.state === 'recording') {
          mediaRecorder.stop();
        }
      }, chunkDuration);

    } catch (err) {
      setError(err as Error);
      shouldContinueRef.current = false;
      setIsRecording(false);
    }
  }, [chunkDuration]);

  const startRecording = useCallback(async () => {
    if (shouldContinueRef.current) return;

    if (!streamRef.current) {
      const granted = await requestPermission();
      if (!granted) return;
    }

    try {
      shouldContinueRef.current = true;
      setIsRecording(true);
      startRecorderSegment();

    } catch (err) {
      setError(err as Error);
      shouldContinueRef.current = false;
      setIsRecording(false);
    }
  }, [requestPermission, startRecorderSegment]);

  const stopRecording = useCallback(() => {
    shouldContinueRef.current = false;

    if (chunkTimerRef.current) {
      window.clearTimeout(chunkTimerRef.current);
      chunkTimerRef.current = null;
    }

    if (mediaRecorderRef.current) {
      if (mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.requestData();
        mediaRecorderRef.current.stop();
      }

      mediaRecorderRef.current = null;
    }

    setIsRecording(false);
  }, []);

  useEffect(() => {
    return () => {
      stopRecording();
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, [stopRecording]);

  return {
    isRecording,
    permissionGranted,
    error,
    startRecording,
    stopRecording,
    requestPermission
  };
}
