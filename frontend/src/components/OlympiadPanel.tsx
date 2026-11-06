import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api, type ContestDetail, type ContestRow, type ProblemDetail } from '../api'
import { pluralTasks } from '../lib/text'
import { formatLeft, getRun, msLeft, onRunChange, parseRequest, setRun, type OlympiadRun } from '../olympiadRun'
import { Figures } from './Figures'
import { MathText } from './MathText'

function hours(min: number): string {
  return min % 60 === 0 ? `${min / 60} ч` : `${Math.floor(min / 60)} ч ${min % 60} мин`
}

/** Вкладка «Олимпиада»: строка «олимпиада и класс» → вариант → «Старт» → решения с таймером → проверка. */
export function OlympiadPanel({ onFinishDiscuss }: { onFinishDiscuss: (summary: string) => void }) {
  const [run, setRunState] = useState<OlympiadRun | null>(getRun)
  useEffect(() => onRunChange(() => setRunState(getRun())), [])

  if (run) return <RunView run={run} onFinishDiscuss={onFinishDiscuss} />
  return <Picker />
}

function Picker() {
  const [text, setText] = useState('')
  const [candidates, setCandidates] = useState<ContestRow[]>([])
  const [chosen, setChosen] = useState<ContestDetail | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  async function open(row: ContestRow) {
    setChosen(await api.contest(row.id))
  }

  async function find(e: FormEvent) {
    e.preventDefault()
    const { query, grade } = parseRequest(text)
    if (!query) return
    setBusy(true)
    setNote('')
    try {
      const all = await api.contests(query)
      // Пробная олимпиада — только там, где известно официальное время тура (не угадываем).
      const rows = all.filter((r) => r.duration_min)
      const byGrade = grade ? rows.filter((r) => r.grade === grade) : rows
      const list = byGrade.length ? byGrade : rows
      if (!list.length) {
        const available = await api.olympiadsWithTime().catch(() => [] as string[])
        setNote(
          (all.length
            ? 'Для этой олимпиады мы пока не нашли официального времени тура, поэтому пробная олимпиада на время недоступна.'
            : 'Такой олимпиады в банке пока нет.') + (available.length ? ` Доступны: ${available.join(', ')}.` : ''),
        )
        setChosen(null)
        return
      }
      if (grade && !byGrade.length) setNote(`За ${grade} класс вариантов нет — показываю другой класс.`)
      setCandidates(list)
      await open(list[Math.floor(Math.random() * list.length)])
    } catch (err) {
      setNote(err instanceof Error ? err.message : 'Ошибка')
    } finally {
      setBusy(false)
    }
  }

  async function anotherYear() {
    if (candidates.length < 2 || !chosen) return
    const others = candidates.filter((c) => c.id !== chosen.id)
    await open(others[Math.floor(Math.random() * others.length)])
  }

  function start() {
    if (!chosen) return
    const seeds: Record<string, number> = {}
    const points: Record<string, number> = {}
    for (const p of chosen.problems) {
      if (p.can_clone) seeds[p.id] = 1 + Math.floor(Math.random() * 1_000_000)
      points[p.id] = p.points
    }
    setRun({
      contestId: chosen.id,
      title: chosen.title,
      problemIds: chosen.problems.map((p) => p.id),
      seeds,
      points,
      answers: {},
      start: Date.now(),
      durationMin: chosen.duration_min ?? 0,
      finished: false,
    })
  }

  return (
    <div className="card space-y-4 p-5">
      <form onSubmit={find} className="flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Олимпиада и класс"
          className="flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2.5 dark:border-slate-700 dark:bg-slate-950"
        />
        <button className="btn-primary" disabled={busy || !text.trim()}>
          {busy ? 'Ищу…' : 'Найти'}
        </button>
      </form>
      {note && <p className="text-sm text-slate-500">{note}</p>}

      {chosen && (
        <div className="space-y-4 border-t border-slate-200 pt-4 dark:border-slate-800">
          <div>
            <h2 className="text-lg font-bold">{chosen.title}</h2>
            <p className="text-sm text-slate-500">
              {chosen.count} {pluralTasks(chosen.count)} · баллы за задачи:{' '}
              {chosen.problems
                .map((p) => p.points)
                .sort((a, b) => a - b)
                .join(', ')}{' '}
              (всего {chosen.total_points})
            </p>
            {candidates.length > 1 && (
              <button onClick={anotherYear} className="mt-1 text-sm font-semibold text-brand-600 hover:underline">
                Другой год
              </button>
            )}
          </div>
          <div className="rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-700">
            <div className="font-semibold">Время: {hours(chosen.duration_min ?? 0)} — как на настоящей олимпиаде</div>
            {chosen.duration_source && (
              <div className="mt-1 text-xs text-slate-500">
                Источник:{' '}
                <a href={chosen.duration_source.url} target="_blank" rel="noreferrer" className="underline">
                  {chosen.duration_source.name}
                </a>
                {chosen.official_points && ' · баллы за задачи — официальные'}
              </div>
            )}
          </div>
          <ul className="list-disc space-y-1 rounded-xl bg-amber-50 p-3 pl-7 text-sm dark:bg-amber-500/10">
            <li>Как на настоящей олимпиаде: к каждой задаче — полное решение с обоснованием и ответ.</li>
            <li>Без обоснования, с пробелами или неаккуратным оформлением баллы снимаются.</li>
            <li>Подсказок и разборов нет до конца времени. Результаты — после окончания.</li>
            <li>Задачи взяты из архивов олимпиад (источник указан), числа в части задач изменены и проверены кодом.</li>
          </ul>
          <button onClick={start} className="btn-primary w-full text-base">
            ▶ Старт
          </button>
        </div>
      )}
    </div>
  )
}

function RunView({ run, onFinishDiscuss }: { run: OlympiadRun; onFinishDiscuss: (summary: string) => void }) {
  const [now, setNow] = useState(() => Date.now())
  const [detail, setDetail] = useState<ContestDetail | null>(null)
  const [statements, setStatements] = useState<Record<string, ProblemDetail>>({})
  const [grading, setGrading] = useState(false)
  const [error, setError] = useState('')
  const left = msLeft(run, now)
  const over = run.finished || left === 0
  const runRef = useRef(run)
  runRef.current = run

  useEffect(() => {
    if (over) return
    setNow(Date.now())
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [over])

  useEffect(() => {
    api
      .contest(run.contestId)
      .then(setDetail)
      .catch(() => {})
    for (const id of run.problemIds) {
      api
        .problem(id, run.seeds[id] ?? null)
        .then((p) => setStatements((s) => ({ ...s, [id]: p })))
        .catch(() => {})
    }
  }, [run.contestId, run.problemIds, run.seeds])

  useEffect(() => {
    if (left === 0 && !run.finished) setRun({ ...run, finished: true })
  }, [left, run])

  function updateAnswer(id: string, field: 'answer' | 'solution', value: string) {
    const cur = runRef.current
    const prev = cur.answers[id] ?? { answer: '', solution: '' }
    setRun({ ...cur, answers: { ...cur.answers, [id]: { ...prev, [field]: value } } })
  }

  async function grade() {
    setGrading(true)
    setError('')
    try {
      const rows = await api.gradeOlympiad(
        run.problemIds.map((id) => ({
          problem_id: id,
          seed: run.seeds[id] ?? null,
          answer: run.answers[id]?.answer ?? '',
          solution: run.answers[id]?.solution ?? '',
          max_points: run.points[id] ?? 7,
        })),
      )
      setRun({ ...runRef.current, finished: true, grades: rows })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка проверки')
    } finally {
      setGrading(false)
    }
  }

  const order = [...run.problemIds].sort((a, b) => (run.points[a] ?? 0) - (run.points[b] ?? 0))
  const meta = Object.fromEntries((detail?.problems ?? []).map((p) => [p.id, p]))
  const grades = Object.fromEntries((run.grades ?? []).map((g) => [g.problem_id, g]))
  const total = order.reduce((s, id) => s + (run.points[id] ?? 0), 0)
  const scored = (run.grades ?? []).reduce((s, g) => s + g.points, 0)

  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-center gap-3 p-4">
        <div className="min-w-0 flex-1">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {run.grades ? 'Итоги' : over ? 'Время вышло' : 'Идёт олимпиада'}
          </div>
          <h2 className="truncate text-lg font-bold">{run.title}</h2>
        </div>
        {run.grades ? (
          <div className="rounded-xl bg-amber-50 px-4 py-2 text-2xl font-extrabold dark:bg-amber-500/10">
            {scored} <span className="text-base font-semibold text-slate-500">из {total}</span>
          </div>
        ) : (
          <div
            className={`rounded-xl px-4 py-2 font-mono text-2xl font-bold ${over ? 'bg-slate-100 dark:bg-slate-800' : 'bg-brand-600 text-white'}`}
          >
            {over ? '0:00:00' : formatLeft(left)}
          </div>
        )}
      </div>

      {order.map((id, i) => {
        const p = statements[id]
        const m = meta[id]
        const a = run.answers[id] ?? { answer: '', solution: '' }
        const g = grades[id]
        return (
          <section key={id} className="card space-y-3 p-5">
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-bold">Задача {i + 1}</h3>
              <span className="chip bg-slate-100 dark:bg-slate-800">
                {g ? `${g.points} из ${g.max_points} б.` : `${run.points[id]} б.`}
              </span>
            </div>
            {p ? (
              <>
                <MathText text={p.statement} />
                <Figures urls={p.figures} />
              </>
            ) : (
              <div className="h-16 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />
            )}
            {m && (
              <p className="text-xs text-slate-500">
                Источник: {m.source}
                {run.seeds[id] ? ' · числа изменены, ответ проверен кодом' : ''}
                {m.url && (
                  <>
                    {' · '}
                    <a href={m.url} target="_blank" rel="noreferrer" className="underline">
                      оригинал
                    </a>
                  </>
                )}
              </p>
            )}
            <textarea
              value={a.solution}
              onChange={(e) => updateAnswer(id, 'solution', e.target.value)}
              readOnly={over}
              rows={6}
              maxLength={6000}
              placeholder="Решение"
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-950"
            />
            <input
              value={a.answer}
              onChange={(e) => updateAnswer(id, 'answer', e.target.value)}
              readOnly={over}
              maxLength={200}
              placeholder="Ответ"
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
            />
            {g && (
              <p
                className={`rounded-xl p-3 text-sm ${g.answer_correct ? 'bg-emerald-50 dark:bg-emerald-500/10' : a.answer.trim() || a.solution.trim() ? 'bg-red-50 dark:bg-red-500/10' : 'bg-slate-100 dark:bg-slate-800'}`}
              >
                {a.answer.trim() || a.solution.trim() ? (
                  <>
                    <b>{g.answer_correct ? 'Ответ верный.' : 'Ответ неверный.'}</b> {g.comment}
                  </>
                ) : (
                  <b>Не сдано.</b>
                )}
              </p>
            )}
          </section>
        )
      })}

      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex flex-wrap gap-2">
        {!over && (
          <button onClick={() => setRun({ ...run, finished: true })} className="btn-ghost">
            Сдать досрочно
          </button>
        )}
        {over && !run.grades && (
          <button onClick={grade} disabled={grading} className="btn-primary">
            {grading ? 'Жюри проверяет…' : 'Отправить на проверку'}
          </button>
        )}
        {run.grades && (
          <>
            <button
              onClick={() => {
                const summary = `Я закончил олимпиаду «${run.title}»: ${scored} из ${total} баллов. Давай разберём задачи, где сняли баллы.`
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
