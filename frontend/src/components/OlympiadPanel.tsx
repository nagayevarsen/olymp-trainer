import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { api, type ContestDetail, type ContestRow, type ProblemDetail } from '../api'
import { pluralTasks } from '../lib/text'
import { formatLeft, getRun, msLeft, onRunChange, parseRequest, setRun, type OlympiadRun } from '../olympiadRun'
import { Figures } from './Figures'
import { MathText } from './MathText'
import { t } from '../i18n'

function hours(min: number): string {
  return min % 60 === 0 ? t('{h} ч', { h: min / 60 }) : t('{h} ч {m} мин', { h: Math.floor(min / 60), m: min % 60 })
}

// Название вида «Олимпиада — этап, год, класс (предмет)»: берём олимпиаду и этап.
const nameOf = (r: ContestRow) => r.title.split(' — ')[0]
const stageOf = (r: ContestRow) => r.title.split(' — ')[1]?.split(',')[0] ?? ''

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
  const [olymp, setOlymp] = useState('')
  const [subject, setSubject] = useState('')
  const [stage, setStage] = useState('')
  const [gradeF, setGradeF] = useState(0) // 0 — все классы
  const [idx, setIdx] = useState(0)

  // Варианты по выбранным фильтрам: от старых годов к новым, стрелками можно листать все.
  const view = useMemo(
    () =>
      candidates
        .filter((r) => nameOf(r) === olymp && (!subject || r.subject === subject) && (!stage || stageOf(r) === stage) && (!gradeF || r.grade === gradeF))
        .sort((a, b) => (a.year ?? 0) - (b.year ?? 0) || (a.grade ?? 0) - (b.grade ?? 0)),
    [candidates, olymp, subject, stage, gradeF],
  )
  const current = view[Math.min(idx, view.length - 1)]
  const olympNames = [...new Set(candidates.map(nameOf))]
  const ofOlymp = candidates.filter((r) => nameOf(r) === olymp)
  const stages = [...new Set(ofOlymp.filter((r) => !subject || r.subject === subject).map(stageOf))].filter(Boolean)
  const subjects = [...new Set(ofOlymp.map((r) => r.subject))]
  const gradeList = [...new Set(ofOlymp.map((r) => r.grade).filter((g): g is number => !!g))].sort((a, b) => a - b)

  // Фильтры или поиск поменялись — начинаем с самого свежего года.
  useEffect(() => setIdx(Math.max(0, view.length - 1)), [view.length, olymp, subject, stage, gradeF])

  const currentId = current?.id
  useEffect(() => {
    if (!currentId) return
    let stale = false
    api
      .contest(currentId)
      .then((c) => !stale && setChosen(c))
      .catch((err) => !stale && setNote(err instanceof Error ? err.message : t('Ошибка')))
    return () => {
      stale = true
    }
  }, [currentId])

  async function find(e: FormEvent) {
    e.preventDefault()
    const { query, grade } = parseRequest(text)
    if (!query) return
    setBusy(true)
    setNote('')
    try {
      const all = await api.contests(query)
      // Пробная олимпиада — только там, где известно официальное время тура (не угадываем).
      // и только если в банке все задачи официального варианта: число задач должно быть как на настоящей олимпиаде.
      const rows = all.filter((r) => r.duration_min && r.complete !== false)
      const byGrade = grade ? rows.filter((r) => r.grade === grade) : rows
      // Если нужного класса нет — оставляем все классы, фильтр «Класс» ниже покажет, какие есть.
      const list = byGrade.length ? byGrade : rows
      if (!list.length) {
        const available = await api.olympiadsWithTime().catch(() => [] as string[])
        if (all.length) {
          const partial = all.find((r) => r.duration_min && r.complete === false)
          setNote(
            (partial
              ? t('В банке пока не все задачи этого тура (в официальном их {n}), поэтому пробная олимпиада на время недоступна.', { n: partial.official_count ?? 0 })
              : t('Для этой олимпиады мы пока не нашли официального времени тура, поэтому пробная олимпиада на время недоступна.')) +
              (available.length ? ' ' + t('Доступны: {list}.', { list: available.join(', ') }) : ''),
          )
        } else {
          // Весь список олимпиад банка, а не только те, где известно время тура.
          const every = await api.contests().catch(() => [] as ContestRow[])
          const names = [...new Set(every.map((r) => r.title.split(' — ')[0]))].join(', ')
          setNote(
            t('Такой олимпиады в банке пока нет.') +
              (names ? ' ' + t('В банке есть: {list}.', { list: names }) : '') +
              (available.length ? ' ' + t('Пробная олимпиада на время доступна для: {list}.', { list: available.join(', ') }) : ''),
          )
        }
        setChosen(null)
        return
      }
      if (list.some((r) => r.approx)) {
        const names = [...new Set(list.map((r) => r.title.split(' — ')[0]))].join(', ')
        setNote(t('Точного совпадения нет. Возможно, вы искали: {list}.', { list: names }))
      } else if (grade && !byGrade.length) {
        const have = [...new Set(list.map((r) => r.grade).filter(Boolean))].sort()
        setNote(
          t('За {n} класс вариантов нет — показываю другой класс.', { n: grade }) +
            (have.length ? ' ' + t('Есть классы: {list}.', { list: have.join(', ') }) : ''),
        )
      }
      setSubject('')
      setStage('')
      setGradeF(byGrade.length ? (grade ?? 0) : 0)
      setOlymp(nameOf(list[0]))
      setCandidates(list)
    } catch (err) {
      setNote(err instanceof Error ? err.message : t('Ошибка'))
    } finally {
      setBusy(false)
    }
  }

  function start() {
    if (!chosen) return
    const seeds: Record<string, number> = {}
    const points: Record<string, number> = {}
    for (const p of chosen.problems) {
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
          placeholder={t('Олимпиада и класс')}
          className="flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2.5 dark:border-slate-700 dark:bg-slate-950"
        />
        <button className="btn-primary" disabled={busy || !text.trim()}>
          {busy ? t('Ищу…') : t('Найти')}
        </button>
      </form>
      {note && <p className="text-sm text-slate-500">{note}</p>}
      {candidates.length > 0 && (olympNames.length > 1 || subjects.length > 1 || stages.length > 1 || gradeList.length > 1) && (
        <div className="flex flex-wrap gap-2 text-sm">
          {olympNames.length > 1 && (
            <select
              value={olymp}
              onChange={(e) => {
                setOlymp(e.target.value)
                setSubject('')
                setStage('')
                setGradeF(0)
              }}
              aria-label={t('Олимпиада')}
              className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 dark:border-slate-700 dark:bg-slate-950"
            >
              {olympNames.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          )}
          {subjects.length > 1 && (
            <select
              value={subject}
              onChange={(e) => {
                setSubject(e.target.value)
                setStage('')
              }}
              aria-label={t('Предмет')}
              className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 dark:border-slate-700 dark:bg-slate-950"
            >
              <option value="">{t('Все предметы')}</option>
              {subjects.map((s) => (
                <option key={s} value={s}>
                  {s === 'physics' ? t('Физика') : t('Математика')}
                </option>
              ))}
            </select>
          )}
          {stages.length > 1 && (
            <select
              value={stage}
              onChange={(e) => setStage(e.target.value)}
              aria-label={t('Этап')}
              className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 dark:border-slate-700 dark:bg-slate-950"
            >
              <option value="">{t('Все этапы')}</option>
              {stages.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          )}
          {gradeList.length > 1 && (
            <select
              value={gradeF}
              onChange={(e) => setGradeF(Number(e.target.value))}
              aria-label={t('Класс')}
              className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 dark:border-slate-700 dark:bg-slate-950"
            >
              <option value={0}>{t('Все классы')}</option>
              {gradeList.map((g) => (
                <option key={g} value={g}>
                  {t('{n} класс', { n: g })}
                </option>
              ))}
            </select>
          )}
        </div>
      )}

      {chosen && (
        <div className="space-y-4 border-t border-slate-200 pt-4 dark:border-slate-800">
          <div>
            <h2 className="text-lg font-bold">{chosen.title}</h2>
            <p className="text-sm text-slate-500">
              {chosen.count} {pluralTasks(chosen.count)} · {t('баллы за задачи:')}{' '}
              {chosen.problems
                .map((p) => p.points)
                .sort((a, b) => a - b)
                .join(', ')}{' '}
              {t('(всего {n})', { n: chosen.total_points })}
            </p>
          </div>
          {view.length > 1 && (
            <div className="flex items-center justify-between gap-3 rounded-xl bg-slate-100 px-3 py-2 dark:bg-slate-800">
              <button
                onClick={() => setIdx(idx - 1)}
                disabled={idx <= 0}
                aria-label={t('Предыдущий год')}
                className="btn-ghost px-3 py-1 text-lg disabled:opacity-30"
              >
                ←
              </button>
              <span className="text-center text-sm font-semibold">
                {[current?.year, current?.grade ? t('{n} класс', { n: current.grade }) : null].filter(Boolean).join(', ')}
                <span className="ml-2 font-normal text-slate-500">{t('{i} из {n}', { i: idx + 1, n: view.length })}</span>
              </span>
              <button
                onClick={() => setIdx(idx + 1)}
                disabled={idx >= view.length - 1}
                aria-label={t('Следующий год')}
                className="btn-ghost px-3 py-1 text-lg disabled:opacity-30"
              >
                →
              </button>
            </div>
          )}
          <div className="rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-700">
            <div className="font-semibold">{t('Время: {h} — как на настоящей олимпиаде', { h: hours(chosen.duration_min ?? 0) })}</div>
            {chosen.duration_source && (
              <div className="mt-1 text-xs text-slate-500">
                {t('Источник:')}{' '}
                <a href={chosen.duration_source.url} target="_blank" rel="noreferrer" className="underline">
                  {chosen.duration_source.name}
                </a>
                {chosen.official_points && t(' · баллы за задачи — официальные')}
              </div>
            )}
          </div>
          <ul className="list-disc space-y-1 rounded-xl bg-amber-50 p-3 pl-7 text-sm dark:bg-amber-500/10">
            <li>{t('Как на настоящей олимпиаде: к каждой задаче — полное решение с обоснованием и ответ.')}</li>
            <li>{t('Без обоснования, с пробелами или неаккуратным оформлением баллы снимаются.')}</li>
            <li>{t('Подсказок и разборов нет до конца времени. Результаты — после окончания.')}</li>
            <li>{t('Задачи взяты из архивов олимпиад (источник указан), условия без изменений.')}</li>
          </ul>
          <button onClick={start} className="btn-primary w-full text-base">
            {t('▶ Старт')}
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
      setError(err instanceof Error ? err.message : t('Ошибка проверки'))
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
            {run.grades ? t('Итоги') : over ? t('Время вышло') : t('Идёт олимпиада')}
          </div>
          <h2 className="truncate text-lg font-bold">{run.title}</h2>
        </div>
        {run.grades ? (
          <div className="rounded-xl bg-amber-50 px-4 py-2 text-2xl font-extrabold dark:bg-amber-500/10">
            {scored} <span className="text-base font-semibold text-slate-500">{t('из {n}', { n: total })}</span>
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
              <h3 className="font-bold">{t('Задача {n}', { n: i + 1 })}</h3>
              <span className="chip bg-slate-100 dark:bg-slate-800">
                {g ? t('{a} из {b} б.', { a: g.points, b: g.max_points }) : t('{n} б.', { n: run.points[id] })}
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
                {t('Источник:')} {m.source}
                {run.seeds[id] ? t(' · числа изменены, ответ проверен кодом') : ''}
                {m.url && (
                  <>
                    {' · '}
                    <a href={m.url} target="_blank" rel="noreferrer" className="underline">
                      {t('оригинал')}
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
              placeholder={p?.answer_kind === 'proof' ? t('Доказательство') : t('Решение')}
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-950"
            />
            {p?.answer_kind !== 'proof' && (
            <input
              value={a.answer}
              onChange={(e) => updateAnswer(id, 'answer', e.target.value)}
              readOnly={over}
              maxLength={200}
              placeholder={t('Ответ')}
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
            />
            )}
            {g && (
              <p
                className={`rounded-xl p-3 text-sm ${g.answer_correct ? 'bg-emerald-50 dark:bg-emerald-500/10' : a.answer.trim() || a.solution.trim() ? 'bg-red-50 dark:bg-red-500/10' : 'bg-slate-100 dark:bg-slate-800'}`}
              >
                {a.answer.trim() || a.solution.trim() ? (
                  <>
                    {p?.answer_kind !== 'proof' && <b>{g.answer_correct ? t('Ответ верный.') : t('Ответ неверный.')}</b>}{' '}
                    {g.comment}
                  </>
                ) : (
                  <b>{t('Не сдано.')}</b>
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
            {t('Сдать досрочно')}
          </button>
        )}
        {over && !run.grades && (
          <button onClick={grade} disabled={grading} className="btn-primary">
            {grading ? t('Жюри проверяет…') : t('Отправить на проверку')}
          </button>
        )}
        {run.grades && (
          <>
            <button
              onClick={() => {
                const summary = t('Я закончил олимпиаду «{title}»: {a} из {b} баллов. Давай разберём задачи, где сняли баллы.', { title: run.title, a: scored, b: total })
                setRun(null)
                onFinishDiscuss(summary)
              }}
              className="btn-primary"
            >
              {t('Разобрать с помощником')}
            </button>
            <button onClick={() => setRun(null)} className="btn-ghost">
              {t('Новая олимпиада')}
            </button>
          </>
        )}
      </div>
    </div>
  )
}
