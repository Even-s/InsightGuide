import { useCallback, useEffect, useRef, useState } from 'react'

export function useAnimatedExit(onExit: () => void, duration = 180) {
  const [isExiting, setIsExiting] = useState(false)
  const defaultExitRef = useRef(onExit)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    defaultExitRef.current = onExit
  }, [onExit])

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current)
  }, [])

  const exit = useCallback((afterExit?: () => void) => {
    if (timerRef.current || isExiting) return
    setIsExiting(true)
    const reduceMotion = typeof window !== 'undefined'
      && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    timerRef.current = setTimeout(() => {
      timerRef.current = null
      const callback = afterExit ?? defaultExitRef.current
      callback()
    }, reduceMotion ? 0 : duration)
  }, [duration, isExiting])

  return { isExiting, exit }
}
