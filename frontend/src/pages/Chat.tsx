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
          <span className="text-xs leading-snug text-slate-500">
            Отвечает ИИ, может ошибаться. Только математика, физика и олимпиады. Не пиши личные данные.
          </span>
        </div>
        <div
          role="tablist"
          className="inline-flex justify-self-center rounded-2xl bg-slate-200/70 p-1 dark:bg-slate-800"
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
              className={`rounded-xl px-5 py-1.5 text-sm font-semibold transition ${
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
        <form onSubmit={submit} className="flex gap-2">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void send(text)
              }
            }}
            rows={2}
            maxLength={2000}
            placeholder={
              mode === 'olympiad'
                ? 'Вопрос по условию задачи…'
                : problemId
                  ? 'Спроси про эту задачу или покажи своё решение…'
                  : 'Напиши, что хочешь потренировать или спроси что угодно по математике и физике…'
            }
            className="flex-1 resize-none rounded-xl border border-slate-300 bg-white px-3 py-2.5 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 dark:border-slate-700 dark:bg-slate-950"
          />
          <button className="btn-primary self-end" disabled={busy || !text.trim()}>
            Отправить
          </button>
        </form>
        {left != null && <div className="mt-1 text-xs text-slate-500">Осталось сообщений на сегодня: {left}</div>}
      </div>
    </div>
  )
}
