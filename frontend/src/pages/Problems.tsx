import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type ProblemListItem, type Subject } from '../api'
import { SUBJECT_NAMES } from '../lib/text'

type Filter = 'all' | Subject

export function ProblemsPage() {
  const [items, setItems] = useState<ProblemListItem[] | null>(null)
  const [error, setError] = useState('')
  const [subject, setSubject] = useState<Filter>('all')
  const [topic, setTopic] = useState<string | null>(null)
  const [hideSolved, setHideSolved] = useState(false)

  useEffect(() => {
    api
      .problems()
      .then(setItems)
      .catch((e) => setError(e.message))
  }, [])

  const topics = useMemo(() => {
    const set = new Set<string>()
    items?.forEach((p) => (subject === 'all' || p.subject === subject) && set.add(p.topic))
    return [...set].sort()
  }, [items, subject])

  const visible = (items ?? []).filter(
    (p) =>
      (subject === 'all' || p.subject === subject) &&
      (!topic || p.topic === topic) &&
      (!hideSolved || !p.solved),
  )

  const solvedCount = items?.filter((p) => p.solved).length ?? 0

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">Задачи</h1>
          {items && (
            <p className="mt-1 text-slate-500">
              Решено {solvedCount} из {items.length}. Чем больше баллов — тем интереснее задача.
            </p>
          )}
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-600 dark:text-slate-400">
          <input type="checkbox" checked={hideSolved} onChange={(e) => setHideSolved(e.target.checked)} />
          Скрыть решённые
        </label>
      </div>

      <div className="mb-3 flex flex-wrap gap-2" role="tablist">
        {(['all', 'math', 'physics'] as Filter[]).map((s) => (
          <button
            key={s}
            role="tab"
            aria-selected={subject === s}
            onClick={() => {
              setSubject(s)
              setTopic(null)
            }}
            className={`btn ${subject === s ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900' : 'btn-ghost'}`}
          >
            {s === 'all' ? 'Все' : SUBJECT_NAMES[s]}
          </button>
        ))}
      </div>
      <div className="mb-6 flex flex-wrap gap-2">
        {topics.map((t) => (
          <button
            key={t}
            onClick={() => setTopic(topic === t ? null : t)}
            className={`chip border transition ${
              topic === t
                ? 'border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200'
                : 'border-slate-200 text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:text-slate-400'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {error && <p className="card p-4 text-red-600">{error}</p>}
      {!items && !error && <SkeletonGrid />}

      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map((p, i) => (
          <li key={p.id} className="animate-fade-up" style={{ animationDelay: `${i * 30}ms` }}>
            <ProblemCard p={p} />
          </li>
        ))}
      </ul>
      {items && visible.length === 0 && (
        <p className="py-10 text-center text-slate-500">Здесь пусто. Попробуй другой фильтр.</p>
      )}
    </div>
  )
}

function ProblemCard({ p }: { p: ProblemListItem }) {
  return (
    <Link
      to={`/problem/${p.id}`}
      className="card group flex h-full flex-col p-5 transition hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-md dark:hover:border-brand-700"
    >
      <div className="flex items-center justify-between gap-2 text-xs font-semibold text-slate-500">
        <span>
          {SUBJECT_NAMES[p.subject]} · {p.topic}
        </span>
        <span
          className={`chip ${
            p.solved
              ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
              : 'bg-gold-400/15 text-amber-700 dark:text-gold-400'
          }`}
        >
          {p.solved ? `✓ +${p.earned}` : `★ ${p.points}`}
        </span>
      </div>
      <h3 className="mt-3 text-lg font-bold leading-snug group-hover:text-brand-700 dark:group-hover:text-brand-300">
        {p.title}
      </h3>
      <p className="mt-1 line-clamp-2 text-sm text-slate-500">{p.source}</p>
      <div className="mt-auto flex flex-wrap gap-2 pt-4 text-xs font-medium text-slate-500">
        {p.can_clone && <span className="chip bg-slate-100 dark:bg-slate-800">∞ варианты</span>}
        {p.started && !p.solved && <span className="chip bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300">в процессе</span>}
        {p.solve_rate !== null && <span className="chip bg-slate-100 dark:bg-slate-800">решили {p.solve_rate}%</span>}
      </div>
    </Link>
  )
}

function SkeletonGrid() {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-hidden>
      {Array.from({ length: 6 }).map((_, i) => (
        <li key={i} className="card h-40 animate-pulse bg-slate-100 dark:bg-slate-900" />
      ))}
    </ul>
  )
}
