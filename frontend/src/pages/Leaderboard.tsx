import { Fragment, useEffect, useState } from 'react'
import { api, type LeaderRow } from '../api'
import { t } from '../i18n'

const MEDALS = ['🥇', '🥈', '🥉']

export function LeaderboardPage() {
  const [rows, setRows] = useState<LeaderRow[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .leaderboard()
      .then(setRows)
      .catch((e) => setError(e.message))
  }, [])

  return (
    <div>
      <h1 className="text-3xl font-extrabold tracking-tight">{t('Рейтинг')}</h1>
      <p className="mt-1 text-slate-500">{t('Баллы за решённые задачи. Подсказки и разборы уменьшают награду. Ники других не показываем.')}</p>
      {error && <p className="card mt-6 p-4 text-red-600">{error}</p>}
      <ol className="card mt-6 divide-y divide-slate-100 overflow-hidden dark:divide-slate-800">
        {!rows && !error && <li className="h-40 animate-pulse" />}
        {rows?.map((r, i) => (
          <Fragment key={r.place}>
            {i > 0 && r.place - rows[i - 1].place > 1 && (
              <li className="py-1 text-center text-slate-400" aria-hidden>
                ⋮
              </li>
            )}
            <li className={`flex items-center gap-4 px-5 py-3 ${r.me ? 'bg-brand-50 dark:bg-brand-900/30' : ''}`}>
              <span className="w-8 text-center text-lg font-bold text-slate-400">{MEDALS[r.place - 1] ?? r.place}</span>
              <span className="flex-1 font-semibold">
                {r.me ? r.name : t('Участник')}
                {r.me && <span className="ml-2 text-sm font-normal text-slate-500">{t('это ты')}</span>}
              </span>
              <span className="text-sm text-slate-500">{t('{n} реш.', { n: r.solved })}</span>
              <span className="w-20 text-right font-extrabold text-amber-600 dark:text-gold-400">{t('{n} б.', { n: r.points })}</span>
            </li>
          </Fragment>
        ))}
        {rows?.length === 0 && <li className="p-6 text-center text-slate-500">{t('Пока никого. Будь первым!')}</li>}
      </ol>
    </div>
  )
}
