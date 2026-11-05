import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type ContestDetail, type ContestRow } from '../api'
import { pluralTasks } from '../lib/text'
import { defaultDuration, formatLeft, getRun, msLeft, onRunChange, setRun, type OlympiadRun } from '../olympiadRun'

const DURATIONS = [60, 90, 120, 180, 240, 300]

/** Вкладка «Олимпиада»: выбрать вариант → время → «Старт» → задачи с таймером → итоги. */
export function OlympiadPanel({ onFinishDiscuss }: { onFinishDiscuss: (summary: string) => void }) {
  const [run, setRunState] = useState<OlympiadRun | null>(getRun)
  useEffect(() => onRunChange(() => setRunState(getRun())), [])

  if (run) return <RunView run={run} onFinishDiscuss={onFinishDiscuss} />
  return <Picker />
}

function Picker() {
  const [query, setQuery] = useState('')
  const [rows, setRows] = useState<ContestRow[] | null>(null)
  const [chosen, setChosen] = useState<ContestDetail | null>(null)
  const [duration, setDuration] = useState(120)
  const [error, setError] = useState('')

  useEffect(() => {
    const t = setTimeout(() => {
      api
        .contests(query)
        .then(setRows)
        .catch((e) => setError(e.message))
    }, 250)
    return () => clearTimeout(t)
  }, [query])

  async function choose(id: string) {
    try {
      const c = await api.contest(id)
      setChosen(c)
      setDuration(defaultDuration(c.stage))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка')
    }
  }

  function start() {
    if (!chosen) return
    const seeds: Record<string, number> = {}
    for (const p of chosen.problems) if (p.can_clone) seeds[p.id] = 1 + Math.floor(Math.random() * 1_000_000)
    setRun({
      contestId: chosen.id,
      title: chosen.title,
      problemIds: chosen.problems.map((p) => p.id),
      seeds,
      start: Date.now(),
      durationMin: duration,
      finished: false,
    })
  }

  if (chosen) {
    const variants = chosen.problems.filter((p) => p.can_clone).length
    return (
      <div className="card space-y-4 p-5">
        <button onClick={() => setChosen(null)} className="text-sm font-semibold text-brand-600 hover:underline">
          ← другая олимпиада
        </button>
        <div>
          <h2 className="text-lg font-bold">{chosen.title}</h2>
          <p className="text-sm text-slate-500">
            {chosen.count} {pluralTasks(chosen.count)} по возрастанию сложности · ★ {chosen.total_points}
            {variants > 0 && ` · ${variants} — с новыми числами (ответы посчитаны кодом)`}
          </p>
        </div>
        <div>
          <div className="mb-2 text-sm font-semibold">Время на олимпиаду</div>
          <div className="flex flex-wrap gap-2">
            {DURATIONS.map((d) => (
              <button key={d} onClick={() => setDuration(d)} className={duration === d ? 'btn-primary' : 'btn-ghost'}>
                {d >= 60 ? `${d / 60} ч`.replace('.5', ',5') : `${d} мин`}
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Подставлено типичное время для этого этапа — поменяй, если на твоей олимпиаде дают другое.
          </p>
        </div>
        <p className="rounded-xl bg-amber-50 p-3 text-sm dark:bg-amber-500/10">
          Как на настоящей олимпиаде: пока идёт время, подсказки и разборы закрыты, а помощник только уточняет условия.
        </p>
        <button onClick={start} className="btn-primary w-full text-base">
          ▶ Старт
        </button>
      </div>
    )
  }

  return (
    <div className="card space-y-3 p-5">
      <h2 className="text-lg font-bold">Пробная олимпиада на время</h2>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Напиши олимпиаду: Жаутыковская, Эйлера, Всесиб…"
        className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 dark:border-slate-700 dark:bg-slate-950"
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="max-h-80 space-y-1 overflow-y-auto">
        {rows?.slice(0, 40).map((r) => (
          <button
            key={r.id}
            onClick={() => choose(r.id)}
            className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left text-sm transition hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <span>{r.title}</span>
            <span className="shrink-0 text-xs text-slate-500">
              {r.count} {pluralTasks(r.count)} · ★ {r.total_points}
            </span>
          </button>
        ))}
        {rows && rows.length === 0 && <p className="text-sm text-slate-500">Такой олимпиады в банке пока нет.</p>}
      </div>
    </div>
  )
}

function RunView({ run, onFinishDiscuss }: { run: OlympiadRun; onFinishDiscuss: (summary: string) => void }) {
  const [now, setNow] = useState(() => Date.now())
  const [detail, setDetail] = useState<ContestDetail | null>(null)
  const left = msLeft(run, now)
  const over = run.finished || left === 0

  useEffect(() => {
    if (over) return
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [over])

  useEffect(() => {
    api.contest(run.contestId).then(setDetail).catch(() => {})
  }, [run.contestId, over])

  useEffect(() => {
    if (left === 0 && !run.finished) setRun({ ...run, finished: true })
  }, [left, run])

  const problems = [...(detail?.problems ?? [])].sort((a, b) => a.points - b.points)

  return (
    <div className="card space-y-4 p-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {over ? 'Олимпиада окончена' : 'Идёт олимпиада'}
          </div>
          <h2 className="truncate text-lg font-bold">{run.title}</h2>
        </div>
        <div className={`rounded-xl px-4 py-2 font-mono text-2xl font-bold ${over ? 'bg-slate-100 dark:bg-slate-800' : 'bg-brand-600 text-white'}`}>
          {over ? '0:00:00' : formatLeft(left)}
        </div>
      </div>

      {over && detail && (
        <div className="rounded-xl bg-amber-50 p-4 dark:bg-amber-500/10">
          <div className="text-2xl font-extrabold">
            ★ {detail.earned} <span className="text-base font-semibold text-slate-500">из {detail.total_points}</span>
          </div>
          <div className="text-sm text-slate-600 dark:text-slate-300">
            Решено {detail.solved} из {detail.count}. Теперь можно открыть подсказки и разборы.
          </div>
        </div>
      )}

      <ol className="space-y-2">
        {problems.map((p, i) => {
          const seed = run.seeds[p.id]
          return (
            <li key={p.id}>
              <Link
                to={`/problem/${p.id}${seed ? `?seed=${seed}` : ''}`}
                className="flex items-center gap-3 rounded-xl border border-slate-200 p-3 transition hover:border-brand-400 dark:border-slate-700"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 font-bold text-brand-700 dark:bg-brand-900/40 dark:text-brand-200">
                  {i + 1}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold">{p.title}</span>
                  <span className="text-xs text-slate-500">
                    {p.topic}
                    {seed ? ' · новые числа' : ''}
                  </span>
                </span>
                <span className="text-sm font-semibold">{p.solved ? `✓ ★ ${p.earned}` : `★ ${p.points}`}</span>
              </Link>
            </li>
          )
        })}
      </ol>

      <div className="flex flex-wrap gap-2">
        {!over && (
          <button onClick={() => setRun({ ...run, finished: true })} className="btn-ghost">
            Завершить досрочно
          </button>
        )}
        {over && (
          <>
            <button
              onClick={() => {
                const summary = detail
                  ? `Я закончил олимпиаду «${run.title}»: решил ${detail.solved} из ${detail.count}, ★ ${detail.earned} из ${detail.total_points}. Давай разберём задачи, которые не получились.`
                  : `Я закончил олимпиаду «${run.title}». Давай разберём задачи.`
                setRun(null)
                onFinishDiscuss(summary)
              }}
              className="btn-primary"
            >
              Разобрать с помощником
            </button>
            <button onClick={() => setRun(null)} className="btn-ghost">
              Новая олимпиада
            </button>
          </>
        )}
      </div>
    </div>
  )
}
