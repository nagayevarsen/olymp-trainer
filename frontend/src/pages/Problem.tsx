import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api, type ChatTurn, type CheckResult, type ProblemDetail, type ProofResult } from '../api'
import { Figures } from '../components/Figures'
import { answerHint } from '../lib/answer'
import { MathText } from '../components/MathText'
import { SUBJECT_NAMES, pluralPoints } from '../lib/text'
import { usePoints } from '../points'
import { problemLocked } from '../olympiadRun'
import { t, tt } from '../i18n'

const HINT_NAMES = [t('Направление'), t('Подход'), t('Наводящий вопрос')]
// Штраф за открытые подсказки, как в backend/app/scoring.py: 0, 1, 2, 4, 6…
const hintPenalty = (k: number) => (k <= 0 ? 0 : k === 1 ? 1 : 2 * (k - 1))

// Короткий вопрос по разбору: помощник видит задачу и разбор, который ученик уже открыл.
function SolutionAsk({ problemId }: { problemId: string }) {
  const [q, setQ] = useState('')
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function ask(e: FormEvent) {
    e.preventDefault()
    const text = q.trim()
    if (!text || busy) return
    const next: ChatTurn[] = [...turns, { role: 'user', content: text }]
    setTurns(next)
    setQ('')
    setBusy(true)
    setError('')
    try {
      const r = await api.chat(next, problemId, 'training')
      setTurns([...next, { role: 'assistant', content: r.reply }])
    } catch (err) {
      setError(err instanceof Error ? err.message : t('Не удалось получить ответ'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-5 border-t border-slate-200 pt-4 dark:border-slate-800">
      {turns.map((t, i) => (
        <div
          key={i}
          className={t.role === 'user' ? 'mb-2 ml-auto w-fit max-w-[85%] rounded-2xl bg-brand-600 px-3 py-2 text-white' : 'mb-3'}
        >
          {t.role === 'user' ? t.content : <MathText text={t.content} />}
        </div>
      ))}
      {busy && <p className="mb-2 text-sm text-slate-500">{t('Думаю…')}</p>}
      {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
      <form onSubmit={ask} className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          maxLength={500}
          placeholder={t('Что непонятно в разборе?')}
          className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2 outline-none focus:border-brand-500 dark:border-slate-700 dark:bg-slate-950"
        />
        <button className="btn-primary" disabled={busy || !q.trim()}>
          {t('Спросить')}
        </button>
      </form>
    </div>
  )
}

export function ProblemPage() {
  const { id = '' } = useParams()
  const locked = problemLocked(id)
  const [params, setParams] = useSearchParams()
  const seed = params.get('v') ? Number(params.get('v')) : null

  const [p, setP] = useState<ProblemDetail | null>(null)
  const [error, setError] = useState('')
  const [answer, setAnswer] = useState('')
  const [result, setResult] = useState<CheckResult | null>(null)
  const [busy, setBusy] = useState<'' | 'check' | 'hint' | 'solution' | 'variant'>('')
  const [confirmSolution, setConfirmSolution] = useState(false)
  const [showOriginal, setShowOriginal] = useState(false)
  const [variantFailed, setVariantFailed] = useState(false)
  const [variantTry, setVariantTry] = useState(0)
  const { setPoints } = usePoints()
  const inputRef = useRef<HTMLInputElement>(null)

  const load = useCallback(() => {
    setError('')
    api
      .problem(id, seed)
      .then(setP)
      .catch((e) => setError(e.message))
  }, [id, seed])

  // Задача олимпиады открыта без варианта — сразу подбираем аналог (оригинал остаётся для тура на время).
  useEffect(() => {
    if (!p || seed !== null || !p.analogue_only || p.id !== id) return
    // Аналог запоминаем в браузере: повторное открытие не запускает решатель на сервере заново.
    const key = 'olymp-analogue:' + id
    let cached: string | null = null
    try {
      cached = localStorage.getItem(key)
    } catch {
      /* без localStorage подберём заново */
    }
    if (cached && Number(cached) > 0) {
      setParams({ v: cached }, { replace: true })
      return
    }
    setVariantFailed(false)
    api
      .variant(id)
      .then((v) => {
        try {
          localStorage.setItem(key, String(v.seed))
        } catch {
          /* не страшно */
        }
        setParams({ v: String(v.seed) }, { replace: true })
      })
      .catch(() => setVariantFailed(true))
  }, [p, seed, id, setParams, variantTry])

  useEffect(() => {
    load()
    setResult(null)
    setAnswer('')
    setShowOriginal(false)
  }, [load])

  if (error) return <ErrorBox text={error} />
  if (!p) return <div className="card h-80 animate-pulse" />
  // Условие оригинала не показываем: ждём аналог, а при ошибке просим повторить.
  if (p.analogue_only && seed === null) {
    return variantFailed ? (
      <div className="card p-6">
        <p>{t('Не удалось подобрать вариант задачи. Попробуй ещё раз.')}</p>
        <button onClick={() => setVariantTry((n) => n + 1)} className="btn-primary mt-4">
          {t('Повторить')}
        </button>
      </div>
    ) : (
      <div className="card h-80 animate-pulse" />
    )
  }

  const solved = p.progress.solved

  async function check(e: FormEvent) {
    e.preventDefault()
    if (!answer.trim()) return
    setBusy('check')
    try {
      const r = await api.check(id, answer, seed)
      setResult(r)
      setPoints(r.total_points)
      if (r.correct) load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('Ошибка'))
    } finally {
      setBusy('')
    }
  }

  async function openHint() {
    if (!p) return
    setBusy('hint')
    try {
      await api.hint(id, p.hints_opened.length + 1)
      load()
    } catch (err) {
      setResult({
        status: 'unparsable',
        correct: false,
        message: (err as Error).message,
      } as CheckResult)
    } finally {
      setBusy('')
    }
  }

  async function openSolution() {
    setBusy('solution')
    setConfirmSolution(false)
    try {
      await api.solution(id)
      load()
    } catch (err) {
      setResult({
        status: 'unparsable',
        correct: false,
        message: (err as Error).message,
      } as CheckResult)
    } finally {
      setBusy('')
    }
  }

  async function newVariant() {
    setBusy('variant')
    try {
      const v = await api.variant(id)
      try {
        localStorage.setItem('olymp-analogue:' + id, String(v.seed))
      } catch {
        /* не страшно */
      }
      setParams({ v: String(v.seed) })
      setTimeout(() => inputRef.current?.focus(), 50)
    } catch (err) {
      setResult({
        status: 'unparsable',
        correct: false,
        message: (err as Error).message,
      } as CheckResult)
    } finally {
      setBusy('')
    }
  }

  const nextHintReward = Math.max(0, p.points - hintPenalty(p.hints_opened.length + 1))

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="min-w-0 space-y-6">
        <Link
          to="/problems"
          className="text-sm font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
        >
          {t('← Все задачи')}
        </Link>

        <article className="card p-6 sm:p-8">
          <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-500">
            <span>{SUBJECT_NAMES[p.subject]}</span>·<span>{t(p.topic)}</span>
            <span className="chip ml-auto bg-gold-400/15 text-base text-amber-700 dark:text-gold-400">
              {t('{n} б.', { n: p.points })}
            </span>
          </div>
          <h1 className="mt-2 text-2xl font-extrabold tracking-tight sm:text-3xl">{tt(p.id, p.title)}</h1>

          {seed !== null && (
            <VariantBanner p={p} showOriginal={showOriginal} toggle={() => setShowOriginal((s) => !s)} />
          )}

          <MathText text={p.statement} className="statement mt-5 text-lg" />
          <Figures urls={p.figures} />

          {showOriginal && p.original_statement && (
            <div className="mt-4 rounded-xl border border-dashed border-slate-300 p-4 text-slate-500 dark:border-slate-700">
              <div className="mb-1 text-xs font-bold uppercase tracking-wide">{t('Оригинал')}</div>
              <MathText text={p.original_statement} />
            </div>
          )}

          <div className="mt-6 text-sm text-slate-500">
            {p.source.label}
            {p.source.russian && t(' · российская олимпиада, для тренировки')}
            {p.source.url && (
              <>
                {' · '}
                <a href={p.source.url} target="_blank" rel="noreferrer" className="underline">
                  {t('оригинал')}
                </a>
              </>
            )}
          </div>
        </article>

        {p.answer_kind === 'proof' ? (
          <ProofForm
            id={id}
            hint={answerHint(p).text}
            onDone={(r) => {
              setPoints(r.total_points)
              if (r.correct) load()
            }}
          />
        ) : (
        <form onSubmit={check} className="card p-6">
          <label htmlFor="answer" className="font-bold">
            {t('Твой ответ')}
          </label>
          <p className="mt-1 text-sm text-slate-500">
            {answerHint(p).text}
          </p>
          <div className="mt-3 flex gap-2">
            <input
              id="answer"
              ref={inputRef}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              autoComplete="off"
              aria-label={t('Ответ')}
              className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-white px-4 py-3 text-lg outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 dark:border-slate-700 dark:bg-slate-950"
            />
            <button className="btn-primary px-6" disabled={busy === 'check' || !answer.trim()}>
              {busy === 'check' ? '…' : t('Проверить')}
            </button>
          </div>
          {result && <ResultBox r={result} />}
        </form>
        )}

        {p.solution && (
          <section className="card animate-fade-up p-6">
            <h2 className="mb-3 text-lg font-bold">{t('Разбор')}</h2>
            <MathText text={p.solution} />
            <SolutionAsk problemId={p.id} />
            {p.can_clone && !solved && (
              <div className="mt-5 rounded-xl bg-brand-50 p-4 text-sm dark:bg-brand-900/30">
                {t('Разобрался? Реши новый вариант этой задачи с другими числами — и получи половину баллов.')}
                <button onClick={newVariant} className="btn-primary mt-3 w-full" disabled={busy === 'variant'}>
                  {t('Новый вариант →')}
                </button>
              </div>
            )}
          </section>
        )}
      </div>

      <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
        <div className="card p-5">
          {solved ? (
            <div>
              <div className="text-sm font-semibold text-emerald-600">{t('Задача решена ✓')}</div>
              <div className="mt-1 text-2xl font-extrabold">
                +{p.progress.earned} {pluralPoints(p.progress.earned)}
              </div>
              {p.solve_rate !== null && (
                <div className="mt-1 text-sm text-slate-500">{t('Эту задачу решили {n}% учеников', { n: p.solve_rate })}</div>
              )}
            </div>
          ) : (
            <div>
              <div className="text-sm font-semibold text-slate-500">{t('Сейчас можно получить')}</div>
              <div className="mt-1 text-3xl font-extrabold text-amber-600 dark:text-gold-400">{t('{n} б.', { n: p.potential })}</div>
            </div>
          )}
        </div>

        {locked ? (
          <div className="card p-5 text-sm">
            <h2 className="font-bold">{t('⏱ Идёт олимпиада')}</h2>
            <p className="mt-1 text-slate-500">
              {t('Подсказки, разбор и помощник откроются после окончания времени — как на настоящей олимпиаде.')}
            </p>
          </div>
        ) : (
          <div className="card p-5">
            <h2 className="font-bold">{t('Подсказки')}</h2>
            <p className="mt-1 text-sm text-slate-500">
              {t('Открывай по одной. Подсказки снимают баллы (всего): открыл одну — −1, две — −2, три — −4. Подсказки составляет ИИ.')}
            </p>
            <ol className="mt-4 space-y-3">
              {p.hints_opened.map((h, i) => (
                <li key={i} className="animate-fade-up rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-800/60">
                  <div className="mb-1 text-xs font-bold uppercase tracking-wide text-brand-600 dark:text-brand-300">
                    {i + 1}. {HINT_NAMES[i] ?? t('Подсказка')}
                  </div>
                  <MathText text={h} />
                </li>
              ))}
            </ol>
            <Link to={`/?problem=${p.id}`} className="btn-ghost mt-3 w-full">
              {t('Спросить ИИ-помощника об этой задаче')}
            </Link>
            {p.hints_opened.length < p.hints_total && !p.solution && (
              <button onClick={openHint} disabled={busy === 'hint'} className="btn-ghost mt-3 w-full">
                {busy === 'hint'
                  ? t('Наставник думает…')
                  : `${HINT_NAMES[p.hints_opened.length]}${solved ? '' : t(' · станет {n} б.', { n: nextHintReward })}`}
              </button>
            )}

            {!p.solution && (
              <div className="mt-4 border-t border-slate-200 pt-4 dark:border-slate-800">
                {confirmSolution ? (
                  <div className="text-sm">
                    <p>
                      {t('После разбора за эту задачу баллов не будет.')}
                      {p.can_clone && t(' Но можно будет решить новый вариант за половину баллов.')}
                    </p>
                    <div className="mt-3 flex gap-2">
                      <button onClick={openSolution} className="btn-primary flex-1" disabled={busy === 'solution'}>
                        {t('Показать')}
                      </button>
                      <button onClick={() => setConfirmSolution(false)} className="btn-ghost flex-1">
                        {t('Ещё подумаю')}
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => (solved ? openSolution() : setConfirmSolution(true))}
                    className="w-full text-sm font-semibold text-slate-500 underline-offset-4 hover:underline"
                  >
                    {t('Показать полный разбор')}
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {p.can_clone && (
          <div className="card p-5">
            <h2 className="font-bold">{t('Тренировка на вариантах')}</h2>
            <p className="mt-1 text-sm text-slate-500">
              {t('Та же идея, другие числа. Каждый вариант проверен: решатель воспроизводит официальный ответ.')}
            </p>
            <button onClick={newVariant} disabled={busy === 'variant'} className="btn-ghost mt-3 w-full">
              {busy === 'variant' ? t('Подбираю и проверяю…') : t('∞ Сделать новый вариант')}
            </button>
            {seed !== null && (
              <button
                onClick={() => setParams({})}
                className="mt-2 w-full text-sm font-semibold text-slate-500 hover:underline"
              >
                {t('Вернуться к оригиналу')}
              </button>
            )}
          </div>
        )}
      </aside>
    </div>
  )
}

function VariantBanner({ p, showOriginal, toggle }: { p: ProblemDetail; showOriginal: boolean; toggle: () => void }) {
  const v = p.verification
  return (
    <div className="mt-4 flex flex-wrap items-center gap-2 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200">
      <span className="font-bold">{t('✓ Проверенный вариант')}</span>
      <span className="text-emerald-700/80 dark:text-emerald-300/80">
        {t('решатель воспроизводит официальный ответ')}
        {v?.cross_checked && t(', ответ сверен с независимой ИИ-моделью')}
      </span>
      {p.original_statement && (
        <button onClick={toggle} className="ml-auto font-semibold underline-offset-4 hover:underline">
          {showOriginal ? t('Скрыть оригинал') : t('Показать оригинал')}
        </button>
      )}
    </div>
  )
}

function ResultBox({ r }: { r: CheckResult }) {
  const styles: Record<CheckResult['status'], string> = {
    correct: 'bg-emerald-50 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200',
    unit_missing: 'bg-emerald-50 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200',
    wrong: 'bg-rose-50 text-rose-800 dark:bg-rose-900/30 dark:text-rose-200',
    wrong_dimension: 'bg-amber-50 text-amber-900 dark:bg-amber-900/30 dark:text-amber-200',
    unparsable: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  }
  const icon = {
    correct: '🎉',
    unit_missing: '✓',
    wrong: '✗',
    wrong_dimension: '⚖',
    unparsable: '?',
  }[r.status]
  return (
    <div
      role="status"
      className={`mt-4 rounded-xl p-4 ${styles[r.status]} ${r.correct ? 'animate-pop' : 'animate-fade-up'}`}
    >
      <div className="flex items-start gap-3">
        <span className="text-xl leading-none">{icon}</span>
        <div>
          <div className="font-semibold">{r.message}</div>
          {r.first_solve && r.earned > 0 && (
            <div className="mt-1 text-lg font-extrabold">
              +{r.earned} {pluralPoints(r.earned)}
            </div>
          )}
          {r.first_solve && r.earned === 0 && (
            <div className="mt-1 text-sm">{t('Баллы не начислены — был открыт разбор. Попробуй новый вариант!')}</div>
          )}
          {r.already_solved && <div className="mt-1 text-sm">{t('Задача уже решена — это была тренировка.')}</div>}
          {r.solve_rate !== null && r.first_solve && (
            <div className="mt-1 text-sm opacity-80">{t('Эту задачу решили {n}% учеников.', { n: r.solve_rate })}</div>
          )}
        </div>
      </div>
    </div>
  )
}

function ErrorBox({ text }: { text: string }) {
  return (
    <div className="card p-6">
      <p className="text-red-600">{text}</p>
      <Link to="/problems" className="btn-ghost mt-4">
        {t('← К задачам')}
      </Link>
    </div>
  )
}

/** Сдача доказательства: текст решения → баллы и комментарий «жюри» (Sonnet по официальному решению). */
function ProofForm({ id, hint, onDone }: { id: string; hint: string; onDone: (r: ProofResult) => void }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState<ProofResult | null>(null)
  const [err, setErr] = useState('')

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!text.trim() || busy) return
    setBusy(true)
    setErr('')
    try {
      const r = await api.proof(id, text)
      setRes(r)
      onDone(r)
    } catch (e) {
      setErr(e instanceof Error ? e.message : t('Ошибка'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="card p-6">
      <label htmlFor="proof" className="font-bold">
        {t('Твоё решение')}
      </label>
      <p className="mt-1 text-sm text-slate-500">{hint}</p>
      <textarea
        id="proof"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={10}
        maxLength={8000}
        className="mt-3 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 dark:border-slate-700 dark:bg-slate-950"
      />
      <div className="mt-2 flex items-center gap-3">
        <button className="btn-primary px-6" disabled={busy || !text.trim()}>
          {busy ? t('Жюри проверяет…') : t('Отправить на проверку')}
        </button>
        <span className="text-xs text-slate-500">{t('Формулы можно писать как $x^2$')}</span>
      </div>
      {err && <p className="mt-3 text-sm text-red-600">{err}</p>}
      {res && (
        <div
          className={`mt-4 animate-fade-up rounded-xl p-4 text-sm ${res.correct ? 'bg-emerald-50 dark:bg-emerald-500/10' : 'bg-amber-50 dark:bg-amber-500/10'}`}
        >
          <div className="text-lg font-extrabold">
            {t('{a} из {b} баллов', { a: res.points, b: res.max_points })} {res.correct ? '✓' : ''}
          </div>
          <p className="mt-1 whitespace-pre-wrap">{res.comment}</p>
          {res.first_solve && res.earned > 0 && (
            <p className="mt-2 font-semibold text-emerald-700 dark:text-emerald-400">
              {t('Задача засчитана:')} +{res.earned} {pluralPoints(res.earned)}
            </p>
          )}
          <p className="mt-2 text-xs text-slate-500">{t('Оценка ИИ по официальному решению жюри — ориентировочная.')}</p>
        </div>
      )}
    </form>
  )
}
