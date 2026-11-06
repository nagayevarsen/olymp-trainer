// Экран «Нет интернета»: показывается поверх приложения, пока нет связи с сервером,
// и сам исчезает, когда связь вернулась.

import { useCallback, useEffect, useRef, useState } from 'react'

const BASE = import.meta.env.VITE_API_URL ?? ''
const RETRY_MS = 5000

/** Есть ли связь с сервером. navigator.onLine бывает «true» при отсутствии интернета, поэтому проверяем запросом. */
async function serverReachable(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/api/health`, { cache: 'no-store' })
    return res.ok
  } catch {
    return false
  }
}

function useOnline(): { online: boolean; checking: boolean; retry: () => void } {
  const [online, setOnline] = useState(() => (typeof navigator === 'undefined' ? true : navigator.onLine))
  const [checking, setChecking] = useState(false)
  const busy = useRef(false)

  const check = useCallback(async () => {
    if (busy.current) return
    busy.current = true
    setChecking(true)
    const ok = navigator.onLine && (await serverReachable())
    setOnline(ok)
    setChecking(false)
    busy.current = false
  }, [])

  // При открытии сразу проверить связь: экран входа сам к серверу не обращается.
  useEffect(() => {
    void check()
  }, [check])

  useEffect(() => {
    const goOffline = () => setOnline(false)
    const maybeOffline = () => void check() // запрос к API не прошёл — проверить, это сеть или сервер
    window.addEventListener('offline', goOffline)
    window.addEventListener('online', maybeOffline)
    window.addEventListener('olymp:network-error', maybeOffline)
    return () => {
      window.removeEventListener('offline', goOffline)
      window.removeEventListener('online', maybeOffline)
      window.removeEventListener('olymp:network-error', maybeOffline)
    }
  }, [check])

  // Пока связи нет — тихо проверяем каждые несколько секунд.
  useEffect(() => {
    if (online) return
    const t = setInterval(() => void check(), RETRY_MS)
    return () => clearInterval(t)
  }, [online, check])

  return { online, checking, retry: () => void check() }
}

export function OfflineOverlay() {
  const { online, checking, retry } = useOnline()
  if (online) return null
  return (
    <div
      role="alertdialog"
      aria-live="assertive"
      aria-labelledby="offline-title"
      className="fixed inset-0 z-[100] flex items-center justify-center bg-white/90 px-4 backdrop-blur-sm dark:bg-black/90"
    >
      <div className="animate-fade-up flex max-w-sm flex-col items-center text-center">
        <svg
          viewBox="0 0 120 100"
          className="offline-float h-28 w-32 text-brand-500 dark:text-brand-400"
          aria-hidden="true"
          fill="none"
          stroke="currentColor"
          strokeWidth="8"
          strokeLinecap="round"
        >
          <path className="offline-wave" style={{ animationDelay: '0.6s' }} d="M10 38 a70 70 0 0 1 100 0" />
          <path className="offline-wave" style={{ animationDelay: '0.3s' }} d="M28 56 a45 45 0 0 1 64 0" />
          <path className="offline-wave" d="M46 74 a20 20 0 0 1 28 0" />
          <circle cx="60" cy="88" r="6" fill="currentColor" stroke="none" />
          <line
            x1="22"
            y1="12"
            x2="98"
            y2="92"
            className="text-slate-400 dark:text-slate-500"
            stroke="currentColor"
            strokeWidth="7"
          />
        </svg>
        <h1 id="offline-title" className="mt-6 text-2xl font-extrabold tracking-tight">
          Нет интернета
        </h1>
        <p className="mt-2 text-slate-600 dark:text-slate-400">
          Проверь Wi-Fi или мобильную сеть. Как только связь появится, всё продолжится с того же места.
        </p>
        <button onClick={retry} disabled={checking} className="btn-primary mt-6">
          {checking ? 'Проверяю…' : 'Попробовать снова'}
        </button>
      </div>
    </div>
  )
}
