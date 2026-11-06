import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, type ChatCard, type ChatTurn } from '../api'
import { MathText } from '../components/MathText'
import { OlympiadPanel } from '../components/OlympiadPanel'
import { getChat, newChatId, saveChat, type ChatMode } from '../chats'
import { getRun, msLeft } from '../olympiadRun'
import { pluralTasks } from '../lib/text'

function Cards({ cards }: { cards: ChatCard[] }) {
  return (
    <div className="mt-3 grid gap-2">
      {cards.map((c) => (
        <Link
          key={c.kind + c.id}
          to={c.kind === 'problem' ? `/problem/${c.id}` : `/contests/${c.id}`}
          className="block rounded-xl border border-slate-200 bg-white p-3 text-sm transition hover:border-brand-400 dark:border-slate-700 dark:bg-slate-900"
        >
          <div className="text-xs text-slate-500">
            {c.kind === 'problem'
              ? `${c.topic ?? ''} · ${c.points} б.`
              : `олимпиада целиком · ${c.count} ${pluralTasks(c.count ?? 0)} · ${c.total_points} б.`}
          </div>
          <div className="font-semibold">{c.title}</div>
          {c.source && <div className="mt-0.5 text-xs text-slate-500">{c.source}</div>}
        </Link>
      ))}
    </div>
  )
}

// Быстрый старт в пустом чате: нажал — и вопрос ушёл помощнику.
const SUGGESTIONS = [
  'Подбери мне задачу по геометрии',
  'Хочу потренировать кинематику',
  'Объясни принцип Дирихле на примере',
  'С чего начать подготовку к Жаутыковской олимпиаде?',
]

export function ChatPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const chatId = params.get('c')
  const stored = getChat(chatId)
  const mode: ChatMode = stored?.mode ?? (params.get('mode') === 'olympiad' ? 'olympiad' : 'training')
  const problemId = stored?.problemId ?? params.get('problem')
  const [turns, setTurns] = useState<ChatTurn[]>(() => stored?.turns ?? [])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [left, setLeft] = useState<number | null>(null)
  const bottom = useRef<HTMLDivElement>(null)

  // Смена чата в истории или «Новый чат» — подгружаем переписку.
  useEffect(() => {
    setTurns(getChat(chatId)?.turns ?? [])
    setError('')
  }, [chatId])

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns, busy])

  function switchMode(m: ChatMode) {
    if (m !== mode) navigate(m === 'olympiad' ? '/?mode=olympiad' : '/')
  }

  async function send(message: string, forceMode?: ChatMode) {
    const q = message.trim()
    if (!q || busy) return
    const chatMode = forceMode ?? mode
    const id = forceMode && forceMode !== mode ? newChatId() : (chatId ?? newChatId())
    const base = forceMode && forceMode !== mode ? [] : turns
    const next: ChatTurn[] = [...base, { role: 'user', content: q }]
    setTurns(next)
    setText('')
    setError('')
    setBusy(true)
    // Во время олимпиады помощник только уточняет условия, без подсказок.
    const run = getRun()
    const apiMode = chatMode === 'olympiad' && run && !run.finished && msLeft(run) > 0 ? 'olympiad' : 'training'
    try {
      // В модель уходит только текст переписки, без карточек.
      const r = await api.chat(
        next.map(({ role, content }) => ({ role, content })),
        problemId,
        apiMode,
      )
      const withReply: ChatTurn[] = [...next, { role: 'assistant', content: r.reply, cards: r.cards }]
      setTurns(withReply)
      saveChat({
        id,
        title: '',
        mode: chatMode,
        problemId,
        turns: withReply,
        updated: Date.now(),
      })
      if (id !== chatId) navigate(`/?c=${id}`, { replace: !forceMode })
      setLeft(r.left)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка')
      setTurns(base)
      setText(q)
    } finally {
      setBusy(false)
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    void send(text)
  }

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-7rem)] max-w-3xl flex-col gap-4">
      <div className="grid items-center gap-x-6 gap-y-3 sm:grid-cols-[minmax(0,1fr)_auto]">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="chip w-fit bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200">
            ИИ-помощник
          </span>
          <span className="text-[11px] leading-snug text-slate-500 sm:text-xs">
            Отвечает ИИ, может ошибаться. Только математика, физика и олимпиады. Не пиши личные данные.
          </span>
        </div>
        <div
          role="tablist"
          className="grid w-full grid-cols-2 rounded-2xl bg-slate-200/70 p-1 sm:inline-grid sm:w-auto sm:justify-self-center dark:bg-slate-800"
        >
          {(
            [
              ['training', 'Тренировка'],
              ['olympiad', 'Олимпиада'],
            ] as const
          ).map(([m, label]) => (
            <button
              key={m}
              role="tab"
              aria-selected={mode === m}
              onClick={() => switchMode(m)}
              className={`rounded-xl px-5 py-2 text-sm font-semibold transition sm:py-1.5 ${
                mode === m
                  ? 'bg-white shadow-sm dark:bg-slate-950'
                  : 'text-slate-500 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="justify-self-end">
          {problemId && (
            <Link to={`/problem/${problemId}`} className="text-sm font-semibold text-brand-600 hover:underline">
              ← к задаче
            </Link>
          )}
        </div>
      </div>

      {mode === 'olympiad' && <OlympiadPanel onFinishDiscuss={(summary) => void send(summary, 'training')} />}

      {mode === 'training' && !problemId && turns.length === 0 && !busy && (
        <div className="animate-fade-up my-auto py-6 text-center">
          <h2 className="text-2xl font-extrabold tracking-tight sm:text-3xl">Чем займёмся?</h2>
          <p className="mt-1 text-sm text-slate-500">Напиши свой вопрос или начни с одного из этих:</p>
          <div className="mt-5 grid gap-2 sm:grid-cols-2">
            {SUGGESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => void send(q)}
                className="rounded-2xl border border-slate-200 bg-white/80 px-4 py-3 text-left text-sm font-medium transition hover:border-brand-400 hover:bg-white dark:border-slate-800 dark:bg-slate-900/80 dark:hover:border-brand-500"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {(turns.length > 0 || busy) && (
        <div className="card space-y-4 p-4">
          {turns.map((t, i) => (
            <div key={i} className={t.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
              <div
                className={`max-w-[90%] rounded-2xl px-4 py-2.5 ${
                  t.role === 'user'
                    ? 'bg-brand-600 text-white'
                    : 'bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-slate-100'
                }`}
              >
                {t.role === 'user' ? <p className="whitespace-pre-wrap">{t.content}</p> : <MathText text={t.content} />}
                {t.cards && t.cards.length > 0 && <Cards cards={t.cards} />}
              </div>
            </div>
          ))}
          {busy && <div className="text-sm text-slate-500">Помощник думает…</div>}
          <div ref={bottom} />
        </div>
      )}

      <div className="flex-1" />
      {/* строка ввода всегда внизу экрана, как в ChatGPT */}
      <div className="sticky bottom-0 z-10 -mx-1 bg-slate-50/95 px-1 pb-3 pt-2 backdrop-blur dark:bg-slate-950/95">
        {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
        <form
          onSubmit={submit}
          className="flex items-end gap-2 rounded-2xl border border-slate-300 bg-white p-1.5 pl-3 shadow-sm focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/30 dark:border-slate-700 dark:bg-slate-950"
        >
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void send(text)
              }
            }}
            onInput={(e) => {
              // поле растёт вместе с текстом, но не выше 10 строк
              const el = e.currentTarget
              el.style.height = 'auto'
              el.style.height = `${Math.min(el.scrollHeight, 240)}px`
            }}
            rows={1}
            maxLength={2000}
            aria-label="Сообщение помощнику"
            className="max-h-60 min-h-10 flex-1 resize-none bg-transparent py-2 outline-none"
          />
          <button
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white transition hover:bg-brand-700 disabled:opacity-40"
            disabled={busy || !text.trim()}
            aria-label="Отправить"
            title="Отправить"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
              <path d="M12 19V5M5 12l7-7 7 7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </form>
        {left != null && <div className="mt-1 text-xs text-slate-500">Осталось сообщений на сегодня: {left}</div>}
      </div>
    </div>
  )
}
