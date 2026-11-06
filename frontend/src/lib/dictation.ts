// Диктовка в поле ввода: встроенное распознавание речи браузера (бесплатно, звук никуда не отправляем сами).
import { useEffect, useRef, useState } from 'react'

interface Recognition {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
  start: () => void
  stop: () => void
}

type RecognitionCtor = new () => Recognition

function ctor(): RecognitionCtor | null {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

/** supported — есть ли распознавание в браузере; toggle — начать/закончить; текст приходит в onText. */
export function useDictation(onText: (text: string) => void) {
  const [listening, setListening] = useState(false)
  const rec = useRef<Recognition | null>(null)
  const cb = useRef(onText)
  useEffect(() => {
    cb.current = onText
  }, [onText])
  useEffect(() => () => rec.current?.stop(), [])

  function toggle() {
    if (listening) {
      rec.current?.stop()
      return
    }
    const C = ctor()
    if (!C) return
    const r = new C()
    r.lang = 'ru-RU'
    r.interimResults = false
    r.continuous = false
    r.onresult = (e) => {
      const parts: string[] = []
      for (let i = 0; i < e.results.length; i++) parts.push(e.results[i][0].transcript)
      cb.current(parts.join(' '))
    }
    r.onend = () => setListening(false)
    r.onerror = () => setListening(false)
    rec.current = r
    setListening(true)
    r.start()
  }

  return { supported: ctor() !== null, listening, toggle }
}
