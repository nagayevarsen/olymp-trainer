import { useEffect, useState } from 'react'
import { Link, NavLink, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { deleteChat, listChats, onChatsChange, type StoredChat } from '../chats'
import { usePoints } from '../points'
import { getUser } from '../user'
import { ThemeSwitch } from './ThemeSwitch'

const NAV = [
  { to: '/problems', label: 'Задачи', icon: '∑' },
  { to: '/contests', label: 'Олимпиады', icon: '🏆' },
  { to: '/profile', label: 'Прогресс', icon: '📈' },
  { to: '/leaderboard', label: 'Рейтинг', icon: '★' },
]

/** Левая панель: тема и настройки, название и слоган, разделы, история чатов, серия и факт дня, ник. */
export function Sidebar({ onSettings, onCollapse }: { onSettings: () => void; onCollapse: () => void }) {
  const { points } = usePoints()
  const [chats, setChats] = useState<StoredChat[]>(listChats)
  const [streak, setStreak] = useState<number | null>(null)
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const activeChat = params.get('c')
  const nick = getUser()?.name ?? ''

  useEffect(() => onChatsChange(() => setChats(listChats())), [])
  useEffect(() => {
    api
      .me()
      .then((m) => setStreak(m.streak))
      .catch(() => setStreak(null))
  }, [points])

  return (
    <div className="flex h-full flex-col gap-4 p-3">
      <div className="flex items-center gap-2">
        <ThemeSwitch />
        <button onClick={onSettings} className="icon-btn" title="Настройки" aria-label="Настройки">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
          </svg>
        </button>
        <button onClick={onCollapse} className="icon-btn ml-auto" title="Свернуть панель" aria-label="Свернуть панель">
          «
        </button>
      </div>

      <Link to="/" className="block rounded-xl px-1">
        {/* Название и слоган придумаем позже — пока заглушки. */}
        <div className="text-xl font-extrabold tracking-tight">Название</div>
        <div className="text-sm text-slate-500">Слоган</div>
      </Link>

      <nav className="grid grid-cols-2 gap-1">
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            className={({ isActive }) =>
              `flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-semibold transition ${
                isActive
                  ? 'bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200'
                  : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
              }`
            }
          >
            <span className="w-4 text-center" aria-hidden="true">
              {n.icon}
            </span>
            {n.label}
          </NavLink>
        ))}
      </nav>

      <button onClick={() => navigate('/')} className="btn-ghost justify-start">
        ＋ Новый чат
      </button>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mb-1 px-1 text-xs font-semibold uppercase tracking-wide text-slate-400">История</div>
        {chats.length === 0 && <p className="px-1 text-sm text-slate-500">Здесь появятся твои чаты.</p>}
        <ul className="space-y-0.5">
          {chats.map((c) => (
            <li key={c.id} className="group flex items-center">
              <Link
                to={`/?c=${c.id}`}
                className={`flex-1 truncate rounded-lg px-2 py-1.5 text-sm transition ${
                  activeChat === c.id
                    ? 'bg-slate-200/70 font-semibold dark:bg-slate-800'
                    : 'hover:bg-slate-100 dark:hover:bg-slate-800/60'
                }`}
                title={c.title}
              >
                {c.mode === 'olympiad' ? '⏱ ' : ''}
                {c.title}
              </Link>
              <button
                onClick={() => {
                  deleteChat(c.id)
                  if (activeChat === c.id) navigate('/')
                }}
                className="invisible px-1 text-slate-400 hover:text-red-500 group-hover:visible"
                title="Удалить чат"
                aria-label="Удалить чат"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="space-y-2">
        {streak != null && (
          <div className="rounded-xl bg-amber-50 px-3 py-2 text-sm dark:bg-amber-500/10">
            <span className="font-bold">🔥 {streak}</span>{' '}
            <span className="text-slate-600 dark:text-slate-300">
              {streak === 0
                ? '— реши задачу сегодня и начни серию'
                : `${streakWord(streak)} подряд с решёнными задачами`}
            </span>
          </div>
        )}
      </div>

      <Link
        to="/profile"
        className="flex items-center gap-3 rounded-xl px-2 py-2 transition hover:bg-slate-100 dark:hover:bg-slate-800"
      >
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-lg font-extrabold text-white">
          {nick.slice(0, 1).toUpperCase()}
        </span>
        <span className="min-w-0">
          <span className="block truncate text-base font-bold">{nick}</span>
          <span className="text-xs text-amber-600 dark:text-gold-400">{points} б.</span>
        </span>
      </Link>
    </div>
  )
}

function streakWord(n: number): string {
  const m10 = n % 10
  const m100 = n % 100
  if (m10 === 1 && m100 !== 11) return 'день'
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return 'дня'
  return 'дней'
}
