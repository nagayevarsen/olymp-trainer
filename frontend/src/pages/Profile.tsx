import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, type Me, type TopicStat } from '../api'
import { SUBJECT_NAMES, pluralPoints } from '../lib/text'
import { clearUser, getTrack, getUser, saveUser } from '../user'
import { ThemeSwitch } from '../components/ThemeSwitch'
import { t, tt } from '../i18n'

export function ProfilePage({ onLogout }: { onLogout: () => void }) {
  const [me, setMe] = useState<Me | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .me(getTrack())
      .then(setMe)
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <p className="card p-6 text-red-600">{error}</p>
  if (!me) return <div className="card h-64 animate-pulse" />

  const bySubject = (['math', 'physics'] as const).map((s) => ({
    subject: s,
    topics: me.topics.filter((t) => t.subject === s),
  }))

  return (
    <div className="space-y-6">
      <section className="card flex flex-wrap items-center gap-6 p-6">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-600 text-2xl font-extrabold text-white">
          {me.name.slice(0, 1).toUpperCase()}
        </div>
        <div className="flex-1">
          <h1 className="text-2xl font-extrabold">{me.name}</h1>
          {me.grade && <p className="text-slate-500">{t('{n} класс', { n: me.grade })}</p>}
        </div>
        <Stat label={pluralPoints(me.points)} value={me.points} accent />
        <Stat label={t('решено')} value={me.solved} />
        <Stat label={t('место из {n}', { n: me.users_total })} value={me.rank ?? '—'} />
      </section>

      <AccountBox hasAccount={me.has_account} onLogout={onLogout} onAttached={(name) => setMe({ ...me, name, has_account: true })} />

      {me.weak_topics.length > 0 && (
        <section className="card border-amber-200 bg-amber-50/60 p-6 dark:border-amber-900 dark:bg-amber-950/20">
          <h2 className="font-bold">{t('Стоит подтянуть')}</h2>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            {t('В этих темах ты чаще ошибаешься или берёшь много подсказок:')}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {me.weak_topics.map((t) => (
              <span key={t} className="chip bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200">
                {t}
              </span>
            ))}
          </div>
        </section>
      )}

      {me.recommended.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-bold">{t('Рекомендуем дальше в этой олимпиаде')}</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            {me.recommended.map((r) => (
              <Link
                key={r.id}
                to={`/problem/${r.id}`}
                className="card p-4 transition hover:border-brand-300 hover:shadow-md"
              >
                <div className="text-xs font-semibold text-slate-500">
                  {t(r.topic)} · {t('{n} б.', { n: r.points })}
                </div>
                <div className="mt-1 font-bold">{tt(r.id, r.title)}</div>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="grid gap-6 md:grid-cols-2">
        {bySubject.map(({ subject, topics }) => (
          <SkillMap key={subject} subject={subject} topics={topics} weak={me.weak_topics} />
        ))}
      </section>
    </div>
  )
}

function SkillMap({ subject, topics, weak }: { subject: string; topics: TopicStat[]; weak: string[] }) {
  const [open, setOpen] = useState(false) // список длинный (все темы банка): по умолчанию свёрнут
  return (
    <div className="card p-6">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between text-left"
      >
        <h2 className="text-lg font-bold">
          {t('Карта навыков:')} {SUBJECT_NAMES[subject]}
        </h2>
        <span className={`text-sm text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden>
          ▾
        </span>
      </button>
      {open && (
        <ul className="mt-4 space-y-4">
          {topics.map((tp) => {
            const pct = tp.mastery ?? 0
            const isWeak = weak.includes(tp.topic)
            return (
              <li key={tp.topic}>
                <div className="mb-1 flex justify-between text-sm">
                  <span className="font-semibold">{t(tp.topic)}</span>
                  <span className="text-slate-500">
                    {tp.mastery === null ? t('не начато') : `${tp.mastery}%`} · {t('решено {a} из {b}', { a: tp.solved, b: tp.total })}
                  </span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                  <div
                    className={`h-full rounded-full transition-all ${isWeak ? 'bg-amber-500' : 'bg-brand-500'}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

function Stat({ label, value, accent }: { label: string; value: number | string; accent?: boolean }) {
  return (
    <div className="text-center">
      <div className={`text-3xl font-extrabold ${accent ? 'text-amber-600 dark:text-gold-400' : ''}`}>{value}</div>
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  )
}

function AccountBox({
  hasAccount,
  onLogout,
  onAttached,
}: {
  hasAccount: boolean
  onLogout: () => void
  onAttached: (name: string) => void
}) {
  const [nick, setNick] = useState('')
  const [password, setPassword] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function attach(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const r = await api.attachAccount(nick.trim(), password)
      const u = getUser()
      if (u) saveUser({ ...u, name: r.name })
      onAttached(r.name)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('Ошибка'))
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    setBusy(true)
    try {
      await api.deleteMe()
      clearUser()
      onLogout()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('Ошибка'))
      setBusy(false)
    }
  }

  const input =
    'w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950'
  return (
    <section className="card space-y-4 p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-bold">{t('Аккаунт')}</h2>
        <span className="flex items-center gap-2 text-sm text-slate-500">
          {t('Тема')} <ThemeSwitch />
        </span>
      </div>
      {!hasAccount && (
        <form onSubmit={attach} className="space-y-2">
          <p className="text-sm text-slate-600 dark:text-slate-400">
            {t('Сейчас прогресс хранится только в этом браузере. Задай ник и пароль — и он сохранится на любом устройстве.')}
          </p>
          <div className="flex flex-wrap gap-2">
            <input value={nick} onChange={(e) => setNick(e.target.value)} placeholder={t('ник')} maxLength={20} className={input + ' sm:w-40'} />
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              placeholder={t('пароль')}
              maxLength={64}
              className={input + ' sm:w-56'}
            />
            <button className="btn-primary" disabled={busy || nick.trim().length < 3 || password.length < 8}>
              {t('Сохранить')}
            </button>
          </div>
        </form>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex flex-wrap gap-4 text-sm">
        <button onClick={onLogout} className="font-semibold text-slate-500 hover:underline">
          {t('Выйти')}
        </button>
        {confirmDelete ? (
          <span className="flex flex-wrap items-center gap-2">
            {t('Удалить ник, пароль и весь прогресс навсегда?')}
            <button onClick={remove} disabled={busy} className="font-semibold text-red-600 hover:underline">
              {t('Да, удалить')}
            </button>
            <button onClick={() => setConfirmDelete(false)} className="text-slate-500 hover:underline">
              {t('Отмена')}
            </button>
          </span>
        ) : (
          <button onClick={() => setConfirmDelete(true)} className="font-semibold text-red-600 hover:underline">
            {t('Удалить аккаунт')}
          </button>
        )}
      </div>
    </section>
  )
}
