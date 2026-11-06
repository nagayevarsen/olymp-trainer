import { Suspense, useEffect, useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { holidayOn } from '../lib/calendar'
import { formatLeft, getRun, msLeft, onRunChange, type OlympiadRun } from '../olympiadRun'
import { usePrefs } from '../prefs'
import { SettingsDialog } from './SettingsDialog'
import { Sidebar } from './Sidebar'

const DECOR = ['π', '∑', '∫', '√', '∞', 'Δ', 'θ', '≈', 'λ', 'Ω', '∂', 'φ']

/** Пока загружается код страницы — спокойная заглушка вместо пустого экрана. */
function PageLoading() {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Загрузка">
      <div className="h-8 w-1/3 animate-pulse rounded-xl bg-slate-200 dark:bg-slate-800" />
      <div className="h-32 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-900" />
    </div>
  )
}

/** Оболочка: сворачиваемая левая панель + основная область (чат или раздел). */
export function Layout({ onLogout }: { onLogout: () => void }) {
  const { prefs, setPref } = usePrefs()
  const [settings, setSettings] = useState(false)
  const [drawer, setDrawer] = useState(false)
  const location = useLocation()
  const holiday = prefs.holidays ? holidayOn() : null

  useEffect(() => setDrawer(false), [location.pathname, location.search])

  const sidebar = (
    <Sidebar
      onSettings={() => setSettings(true)}
      onCollapse={() => (drawer ? setDrawer(false) : setPref('sidebarOpen', false))}
    />
  )

  return (
    <div className="flex h-dvh overflow-hidden">
      {/* компьютер: панель слева, сворачивается стрелкой */}
      {prefs.sidebarOpen ? (
        <aside className="hidden w-72 shrink-0 border-r border-slate-200 bg-white/70 lg:block dark:border-slate-800 dark:bg-slate-900/40">
          {sidebar}
        </aside>
      ) : (
        <button
          onClick={() => setPref('sidebarOpen', true)}
          className="hidden w-9 shrink-0 items-start justify-center border-r border-slate-200 pt-4 text-slate-500 hover:text-slate-900 lg:flex dark:border-slate-800 dark:hover:text-white"
          title="Открыть панель"
          aria-label="Открыть панель"
        >
          »
        </button>
      )}

      {/* телефон и планшет: панель выезжает по кнопке ☰ */}
      {drawer && (
        <div className="fixed inset-0 z-40 lg:hidden" onClick={() => setDrawer(false)}>
          <div className="absolute inset-0 bg-black/40" />
          <aside
            className="absolute inset-y-0 left-0 w-80 max-w-[85vw] bg-white shadow-xl dark:bg-slate-900"
            onClick={(e) => e.stopPropagation()}
          >
            {sidebar}
          </aside>
        </div>
      )}

      <div className="relative flex min-w-0 flex-1 flex-col overflow-y-auto">
        {prefs.decor && (
          <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-0 overflow-hidden select-none">
            {DECOR.map((ch, i) => (
              <span
                key={i}
                className="absolute font-serif text-5xl text-slate-900/[0.035] dark:text-white/[0.04]"
                style={{ left: `${(i * 37) % 95}%`, top: `${(i * 53 + 11) % 92}%`, transform: `rotate(${(i % 5) * 9 - 18}deg)` }}
              >
                {ch}
              </span>
            ))}
          </div>
        )}

        <div className="sticky top-0 z-20 flex items-center gap-2 border-b border-slate-200/70 bg-slate-50/85 px-3 py-2 backdrop-blur lg:hidden dark:border-slate-800 dark:bg-slate-950/85">
          <button onClick={() => setDrawer(true)} className="icon-btn" aria-label="Открыть меню">
            ☰
          </button>
          <Link to="/" className="font-extrabold tracking-tight">
            Название
          </Link>
        </div>

        {holiday && (
          <div className={`relative z-10 bg-gradient-to-r ${holiday.strip} px-4 py-1.5 text-center text-sm font-semibold`}>
            {holiday.emoji} {holiday.greeting}
          </div>
        )}
        <RunBanner />

        <main className="relative z-10 mx-auto w-full max-w-5xl flex-1 px-4 py-6 sm:py-8">
          <Suspense fallback={<PageLoading />}>
            <Outlet />
          </Suspense>
        </main>
        <footer className="relative z-10 mx-auto w-full max-w-5xl px-4 pb-6 text-xs text-slate-500">
          <Link to="/terms" className="hover:underline">
            Условия и данные
          </Link>{' '}
          · Часть задач и подсказок составлена ИИ, ответы вариантов проверены программой.
        </footer>
      </div>

      <SettingsDialog open={settings} onClose={() => setSettings(false)} onLogout={onLogout} />
    </div>
  )
}

/** Полоска с таймером, пока идёт пробная олимпиада (видна на любой странице). */
function RunBanner() {
  const [run, setRunState] = useState<OlympiadRun | null>(getRun)
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => onRunChange(() => setRunState(getRun())), [])
  useEffect(() => {
    if (!run || run.finished) return
    setNow(Date.now())
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [run])
  if (!run || run.finished) return null
  const left = msLeft(run, now)
  return (
    <Link
      to="/?mode=olympiad"
      className={`relative z-10 block px-4 py-1.5 text-center text-sm font-semibold ${
        left > 0 ? 'bg-brand-600 text-white' : 'bg-red-600 text-white'
      }`}
    >
      {left > 0 ? `⏱ Идёт олимпиада «${run.title}» · осталось ${formatLeft(left)}` : '⏱ Время вышло — посмотреть итоги'}
    </Link>
  )
}
