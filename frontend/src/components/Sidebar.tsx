import { APP_NAME } from '../config'
import { useEffect, useState } from 'react'
import { Link, NavLink, useNavigate, useSearchParams } from 'react-router-dom'
import { deleteChat, listChats, onChatsChange, type StoredChat } from '../chats'
import { usePoints } from '../points'
import { getUser } from '../user'
import { AvatarButton } from './Avatar'
import { StreakCard } from './StreakCard'
import { ThemeSwitch } from './ThemeSwitch'
import { LangSwitch } from './LangSwitch'
import { t } from '../i18n'

const NAV = [
  // Главная — чат с ИИ-помощником; первой и на всю ширину, чтобы из любого раздела было видно, как вернуться.
  { to: '/', label: t('Чат с помощником'), icon: '💬', wide: true },
  { to: '/problems', label: t('Задачи'), icon: '∑' },
  { to: '/contests', label: t('Олимпиады'), icon: '🏆' },
  { to: '/profile', label: t('Прогресс'), icon: '📈' },
  { to: '/leaderboard', label: t('Рейтинг'), icon: '★' },
]

/** Левая панель: тема и настройки, название и слоган, разделы, история чатов, серия и факт дня, ник. */
export function Sidebar({ onSettings, onCollapse }: { onSettings: () => void; onCollapse: () => void }) {
  const { points } = usePoints()
  const [chats, setChats] = useState<StoredChat[]>(listChats)
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const activeChat = params.get('c')
  const nick = getUser()?.name ?? ''

  useEffect(() => onChatsChange(() => setChats(listChats())), [])

  return (
    <div className="flex h-full flex-col gap-4 p-3">
      <div className="flex items-center gap-2">
        <ThemeSwitch />
        <LangSwitch />
        <button onClick={onSettings} className="icon-btn" title={t('Настройки')} aria-label={t('Настройки')}>
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
        <button onClick={onCollapse} className="icon-btn ml-auto" title={t('Свернуть панель')} aria-label={t('Свернуть панель')}>
          «
        </button>
      </div>

      <Link to="/" className="block rounded-xl px-1">
        <div className="font-brand text-lg font-bold tracking-tight">{APP_NAME}</div>
      </Link>

      <nav className="grid grid-cols-2 gap-1">
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-semibold transition ${'wide' in n ? 'col-span-2' : ''} ${
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
        {t('＋ Новый чат')}
      </button>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mb-1 px-1 text-xs font-semibold uppercase tracking-wide text-slate-400">{t('История')}</div>
        {chats.length === 0 && <p className="px-1 text-sm text-slate-500">{t('Здесь появятся твои чаты.')}</p>}
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
                title={c.title === 'Новый чат' ? t('Новый чат') : c.title}
              >
                {c.mode === 'olympiad' ? '⏱ ' : ''}
                {c.title === 'Новый чат' ? t('Новый чат') : c.title}
              </Link>
              <button
                onClick={() => {
                  deleteChat(c.id)
                  if (activeChat === c.id) navigate('/')
                }}
                className="invisible px-1 text-slate-400 hover:text-red-500 group-hover:visible"
                title={t('Удалить чат')}
                aria-label={t('Удалить чат')}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </div>

      <StreakCard />

      <div className="flex items-center gap-3 rounded-xl px-2 py-2">
        <AvatarButton size={44} />
        <Link to="/profile" className="min-w-0 flex-1 rounded-lg hover:underline">
          <span className="block truncate text-lg font-bold">{nick}</span>
          <span className="text-xs text-amber-600 dark:text-gold-400">{t('{n} б.', { n: points })}</span>
        </Link>
      </div>
    </div>
  )
}
