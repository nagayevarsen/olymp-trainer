import { NavLink, Outlet } from 'react-router-dom'
import { APP_NAME } from '../config'
import { usePoints } from '../points'
import { ThemeSwitch } from './ThemeSwitch'

const links = [
  { to: '/', label: 'Задачи', short: 'Задачи', end: true },
  { to: '/contests', label: 'Олимпиады', short: 'Олимп.' },
  { to: '/chat', label: 'Помощник', short: 'ИИ' },
  { to: '/profile', label: 'Мой прогресс', short: 'Я' },
  { to: '/leaderboard', label: 'Рейтинг', short: 'Топ' },
]

export function Layout() {
  const { points } = usePoints()
  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
        <div className="mx-auto flex max-w-5xl items-center gap-2 px-4 py-3">
          <NavLink to="/" className="mr-2 flex items-center gap-2 font-extrabold tracking-tight">
            <img src="/favicon.svg" alt="" className="h-7 w-7" />
            <span className="hidden sm:inline">{APP_NAME}</span>
          </NavLink>
          <nav className="flex flex-1 gap-1 overflow-x-auto">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.end}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-lg px-2.5 py-1.5 sm:px-3 text-sm font-semibold transition ${
                    isActive
                      ? 'bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200'
                      : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
                  }`
                }
              >
                <span className="hidden sm:inline">{l.label}</span>
                <span className="sm:hidden">{l.short}</span>
              </NavLink>
            ))}
          </nav>
          {/* на телефоне переключатель темы — в чате и в профиле, чтобы не теснить меню */}
          <div className="hidden shrink-0 sm:block">
            <ThemeSwitch />
          </div>
          <div
            className="chip bg-gold-400/15 text-amber-700 dark:text-gold-400"
            title="Твои баллы"
            aria-label={`Баллы: ${points}`}
          >
            ★ {points}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-5xl px-4 pb-8 text-xs text-slate-500">
        <NavLink to="/terms" className="hover:underline">
          Условия и данные
        </NavLink>{' '}
        · Часть задач и подсказок составлена ИИ, ответы вариантов проверены программой.
      </footer>
    </div>
  )
}
