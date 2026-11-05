import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, type ChatTurn } from '../api'
import { MathText } from '../components/MathText'

// Переписка хранится только на этом устройстве (на сервере её нет).
const KEY = 'olymp-chat'

function loadHistory(scope: string): ChatTurn[] {
  try {
    const all = JSON.parse(sessionStorage.getItem(KEY) ?? '{}') as Record<string, ChatTurn[]>
    return all[scope] ?? []
  } catch {
    return []
  }
}

function saveHistory(scope: string, turns: ChatTurn[]) {
  try {
    const all = JSON.parse(sessionStorage.getItem(KEY) ?? '{}') as Record<string, ChatTurn[]>
    all[scope] = turns.slice(-40)
    sessionStorage.setItem(KEY, JSON.stringify(all))
  } catch {
    /* хранилище недоступно — переписка просто не сохранится */
  }
}

const SUGGESTIONS = [
  'Подбери мне задачу на перебор',
  'Объясни принцип Дирихле на примере',
  'Как решать задачи на движение навстречу?',
  'Проверь мой ответ: сумма чисел от 1 до 50 равна 1275',
]

export function ChatPage() {
  const [params] = useSearchParams()
  const problemId = params.get('problem')
  const scope = problemId ?? 'general'
  const [turns, setTurns] = useState<ChatTurn[]>(() => loadHistory(scope))
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [left, setLeft] = useState<number | null>(null)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setTurns(loadHistory(scope))
  }, [scope])

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns, busy])

  async function send(message: string) {
    const q = message.trim()
    if (!q || busy) return
    const next: ChatTurn[] = [...turns, { role: 'user', content: q }]
    setTurns(next)
    setText('')
    setError('')
    setBusy(true)
    try {
      const r = await api.chat(next, problemId)
      const withReply: ChatTurn[] = [...next, { role: 'assistant', content: r.reply }]
      setTurns(withReply)
      saveHistory(scope, withReply)
      setLeft(r.left)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка')
      setTurns(turns)
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
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-extrabold tracking-tight">Помощник</h1>
        <span className="chip bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200">ИИ-помощник</span>
        {problemId && (
          <Link to={`/problem/${problemId}`} className="ml-auto text-sm font-semibold text-brand-600 hover:underline">
            ← к задаче
          </Link>
        )}
      </header>
      <p className="-mt-2 text-sm text-slate-500">
        Отвечает ИИ — только про математику, физику и олимпиады. Расчёты и новые задачи он проверяет программой, но
        может ошибаться. Не пиши в чат личные данные.
      </p>

      <div className="card min-h-[50dvh] space-y-4 p-4">
        {turns.length === 0 && (
          <div className="space-y-3">
            <p className="text-slate-600 dark:text-slate-400">
              {problemId
                ? 'Спроси, с чего начать эту задачу, или покажи своё решение — помогу найти ошибку.'
                : 'Спроси что-нибудь по математике или физике. Например:'}
            </p>
            {!problemId && (
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => void send(s)} className="btn-ghost text-left">
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
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
            </div>
          </div>
        ))}
        {busy && <div className="text-sm text-slate-500">Помощник думает…</div>}
        <div ref={bottom} />
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
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
          placeholder="Напиши вопрос или своё решение…"
          className="flex-1 resize-none rounded-xl border border-slate-300 bg-white px-3 py-2.5 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 dark:border-slate-700 dark:bg-slate-950"
        />
        <button className="btn-primary self-end" disabled={busy || !text.trim()}>
          Отправить
        </button>
      </form>
      <div className="flex justify-between text-xs text-slate-500">
        <span>{left != null ? `Осталось сообщений на сегодня: ${left}` : ''}</span>
        {turns.length > 0 && (
          <button
            onClick={() => {
              setTurns([])
              saveHistory(scope, [])
            }}
            className="hover:underline"
          >
            Очистить переписку
          </button>
        )}
      </div>
    </div>
  )
}
