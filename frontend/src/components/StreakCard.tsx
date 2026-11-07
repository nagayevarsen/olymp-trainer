import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type DailyInfo } from '../api'
import { usePoints } from '../points'
import { t, tt } from '../i18n'

/** Серия дней и задача дня. Внешний вид — временный, команда пришлёт свой вариант. */
export function StreakCard() {
  const { points } = usePoints()
  const [info, setInfo] = useState<DailyInfo | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api
      .daily()
      .then(setInfo)
      .catch(() => setInfo(null))
  }, [points])

  if (!info) return null
  const { streak, problem } = info
  const text = {
    new: t('Реши задачу дня — начнётся серия'),
    done_today: t('Задача дня решена — до завтра!'),
    active: t('Реши задачу дня, чтобы серия продолжилась'),
    restorable: t('Вчера пропущено — серию можно восстановить'),
    broken: t('Серия погасла. Реши задачу дня — начнётся новая'),
  }[streak.status]

  async function restore() {
    setBusy(true)
    try {
      const s = await api.restoreStreak()
      setInfo((i) => (i ? { ...i, streak: s } : i))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-2 rounded-xl bg-amber-50 p-3 text-sm dark:bg-amber-500/10">
      <div className="flex items-center gap-2">
        <span className="text-xl">{streak.status === 'broken' ? '🪨' : '🔥'}</span>
        <span className="text-lg font-extrabold">{streak.count}</span>
        <span className="ml-auto text-xs text-slate-500" title={t('Восстановления серии на этот месяц')}>
          ♻ {streak.restores_left}/{streak.restores_per_month}
        </span>
      </div>
      <div className="text-slate-600 dark:text-slate-300">{text}</div>
      {streak.status === 'restorable' && (
        <button onClick={restore} disabled={busy} className="btn-ghost w-full">
          {t('Восстановить серию')}
        </button>
      )}
      {problem && streak.status !== 'done_today' && (
        <Link
          to={`/problem/${problem.id}`}
          className="block rounded-lg bg-white px-3 py-2 transition hover:ring-2 hover:ring-amber-400 dark:bg-slate-900"
        >
          <div className="text-xs text-slate-500">{t('Задача дня · {n} б.', { n: problem.points })}</div>
          <div className="truncate font-semibold">{tt(problem.id, problem.title)}</div>
        </Link>
      )}
    </div>
  )
}
