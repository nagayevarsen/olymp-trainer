import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Me } from '../api'
import { SUBJECT_NAMES, pluralPoints } from '../lib/text'

export function ProfilePage({ onLogout }: { onLogout: () => void }) {
  const [me, setMe] = useState<Me | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .me()
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
          {me.grade && <p className="text-slate-500">{me.grade} класс</p>}
        </div>
        <Stat label={pluralPoints(me.points)} value={me.points} accent />
        <Stat label="решено" value={me.solved} />
        <Stat label={`место из ${me.users_total}`} value={me.rank ?? '—'} />
      </section>

      {me.weak_topics.length > 0 && (
        <section className="card border-amber-200 bg-amber-50/60 p-6 dark:border-amber-900 dark:bg-amber-950/20">
          <h2 className="font-bold">Стоит подтянуть</h2>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            В этих темах ты чаще ошибаешься или берёшь много подсказок:
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
          <h2 className="mb-3 text-lg font-bold">Рекомендуем дальше</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            {me.recommended.map((r) => (
              <Link
                key={r.id}
                to={`/problem/${r.id}`}
                className="card p-4 transition hover:border-brand-300 hover:shadow-md"
              >
                <div className="text-xs font-semibold text-slate-500">
                  {r.topic} · ★ {r.points}
                </div>
                <div className="mt-1 font-bold">{r.title}</div>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="grid gap-6 md:grid-cols-2">
        {bySubject.map(({ subject, topics }) => (
          <div key={subject} className="card p-6">
            <h2 className="mb-4 text-lg font-bold">Карта навыков: {SUBJECT_NAMES[subject]}</h2>
            <ul className="space-y-4">
              {topics.map((t) => {
                const pct = t.total ? Math.round((100 * t.solved) / t.total) : 0
                const weak = me.weak_topics.includes(t.topic)
                return (
                  <li key={t.topic}>
                    <div className="mb-1 flex justify-between text-sm">
                      <span className="font-semibold">{t.topic}</span>
                      <span className="text-slate-500">
                        {t.solved}/{t.total} · ★ {t.points}
                      </span>
                    </div>
                    <div className="h-2.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                      <div
                        className={`h-full rounded-full transition-all ${weak ? 'bg-amber-500' : 'bg-brand-500'}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </section>

      <button onClick={onLogout} className="text-sm font-semibold text-slate-500 hover:underline">
        Выйти и начать заново
      </button>
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
