import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type ContestDetail, type ContestRow, type Subject } from '../api'
import { SUBJECT_NAMES, pluralTasks } from '../lib/text'
import { t } from '../i18n'

/** Список «олимпиад целиком»: задачи одной олимпиады, года и класса из банка. */
export function ContestsPage() {
  const [rows, setRows] = useState<ContestRow[] | null>(null)
  const [subject, setSubject] = useState<Subject | ''>('')
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .contests()
      .then(setRows)
      .catch((e) => setError(e.message))
  }, [])

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase()
    const out = new Map<string, ContestRow[]>()
    for (const r of rows ?? []) {
      if (subject && r.subject !== subject) continue
      if (q && !r.title.toLowerCase().includes(q)) continue
      const name = r.title.split(',')[0]
      out.set(name, [...(out.get(name) ?? []), r])
    }
    // Сначала казахстанская IZhO, дальше — олимпиады, где больше вариантов.
    return [...out.entries()].sort(
      (a, b) => Number(b[0].includes('IZhO')) - Number(a[0].includes('IZhO')) || b[1].length - a[1].length,
    )
  }, [rows, subject, query])

  if (error) return <p className="card p-6 text-red-600">{error}</p>
  if (!rows) return <div className="card h-64 animate-pulse" />

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold tracking-tight">{t('Олимпиады целиком')}</h1>
        <p className="mt-1 text-sm text-slate-500">
          {t('Реши вариант олимпиады: задачи одного года и класса, у каждой — свои баллы. В вариант входят задачи из банка тренажёра (с числовым ответом). Российские олимпиады (Курчатов, Всесибирская, ММО) здесь не показываются: их очные этапы проходят в России, у нас это тренировочные задачи. Найти их можно поиском.')}
        </p>
      </header>
      <div className="flex flex-wrap gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('Поиск')}
          className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm sm:w-72 dark:border-slate-700 dark:bg-slate-950"
        />
        {(['', 'math', 'physics'] as const).map((s) => (
          <button
            key={s}
            onClick={() => setSubject(s)}
            className={subject === s ? 'btn-primary' : 'btn-ghost'}
          >
            {s ? SUBJECT_NAMES[s] : t('Все')}
          </button>
        ))}
      </div>
      {groups.length === 0 && <p className="text-slate-500">{t('Ничего не нашлось.')}</p>}
      {groups.map(([name, list]) => (
        <section key={name}>
          <h2 className="mb-2 font-bold">{name}</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {list.map((r) => (
              <Link key={r.id} to={`/contests/${r.id}`} className="card block p-4 transition hover:border-brand-400">
                <div className="text-xs text-slate-500">
                  {SUBJECT_NAMES[r.subject]} · {r.count} {pluralTasks(r.count)} · {t('{n} б.', { n: r.total_points })}
                </div>
                <div className="mt-1 font-semibold">
                  {[r.year, r.grade ? t('{n} класс', { n: r.grade }) : null].filter(Boolean).join(', ') || t('Вариант')}
                </div>
                {r.solved > 0 && (
                  <div className="mt-2 text-xs font-semibold text-emerald-600">
                    {t('решено {a} из {b}', { a: r.solved, b: r.count })} · {t('{n} б.', { n: r.earned })}
                  </div>
                )}
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

/** Один вариант: задачи по порядку, баллы за каждую и итог. */
export function ContestPage() {
  const { id = '' } = useParams()
  const [c, setC] = useState<ContestDetail | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .contest(id)
      .then(setC)
      .catch((e) => setError(e.message))
  }, [id])

  if (error) return <p className="card p-6 text-red-600">{error}</p>
  if (!c) return <div className="card h-64 animate-pulse" />

  const pct = c.total_points ? Math.round((100 * c.earned) / c.total_points) : 0
  return (
    <div className="space-y-5">
      <Link to="/contests" className="text-sm font-semibold text-brand-600 hover:underline">
        {t('← все олимпиады')}
      </Link>
      <section className="card p-5">
        <h1 className="text-xl font-extrabold tracking-tight">{c.title}</h1>
        <div className="mt-3 flex flex-wrap items-end gap-6">
          <div>
            <div className="text-3xl font-extrabold text-amber-600">
              {c.earned} <span className="text-base font-semibold text-slate-400">/ {c.total_points}</span>
            </div>
            <div className="text-xs uppercase tracking-wide text-slate-500">{t('баллов набрано')}</div>
          </div>
          <div>
            <div className="text-3xl font-extrabold">
              {c.solved} <span className="text-base font-semibold text-slate-400">/ {c.count}</span>
            </div>
            <div className="text-xs uppercase tracking-wide text-slate-500">{t('задач решено')}</div>
          </div>
        </div>
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
          <div className="h-full rounded-full bg-amber-500 transition-all" style={{ width: `${pct}%` }} />
        </div>
      </section>
      <ol className="space-y-2">
        {c.problems.map((p) => (
          <li key={p.id}>
            <Link to={`/problem/${p.id}`} className="card flex items-center gap-4 p-4 transition hover:border-brand-400">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 font-bold text-brand-700 dark:bg-brand-900/40 dark:text-brand-200">
                {p.n}
              </span>
              <span className="flex-1">
                <span className="block font-semibold">{p.title}</span>
                <span className="text-xs text-slate-500">{p.topic}</span>
              </span>
              <span className="text-right text-sm">
                {p.solved ? (
                  <span className="font-semibold text-emerald-600">✓ {t('{n} б.', { n: p.earned })}</span>
                ) : (
                  <span className="font-semibold text-slate-600 dark:text-slate-300">{t('{n} б.', { n: p.points })}</span>
                )}
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </div>
  )
}
