import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, type ChatCard, type ChatTurn } from '../api'
import { MathText } from '../components/MathText'
import { OlympiadPanel } from '../components/OlympiadPanel'
import { getChat, newChatId, saveChat, type ChatMode } from '../chats'
import { getRun, msLeft } from '../olympiadRun'
import { pluralTasks } from '../lib/text'
import { toAttachment, type Attached } from '../lib/attach'
import { useDictation } from '../lib/dictation'

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
const SUGGESTIONS: [string, string][] = [
  ['📐', 'Подбери мне задачу по геометрии'],
  ['🚀', 'Хочу потренировать кинематику'],
  ['🕊️', 'Объясни принцип Дирихле на примере'],
  ['🏆', 'С чего начать подготовку к Жаутыковской?'],
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
  const [files, setFiles] = useState<Attached[]>([])
  const fileInput = useRef<HTMLInputElement>(null)
  const bottom = useRef<HTMLDivElement>(null)
  const mic = useDictation((said) => setText((t) => (t.trim() ? `${t.trim()} ${said}` : said)))

  async function addFiles(list: FileList | null) {
    if (!list) return
    setError('')
    try {
      const added = await Promise.all(Array.from(list).slice(0, 3).map(toAttachment))
      setFiles((f) => [...f, ...added].slice(0, 3))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось прикрепить файл')
    }
  }

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
    const sending = forceMode ? [] : files
    const q = message.trim() || (sending.length ? 'Помоги разобраться с задачей из файла' : '')
    if (!q || busy) return
    const shown = sending.length ? `${q}\n📎 ${sending.map((f) => f.name).join(', ')}` : q
    const chatMode = forceMode ?? mode
    const id = forceMode && forceMode !== mode ? newChatId() : (chatId ?? newChatId())
    const base = forceMode && forceMode !== mode ? [] : turns
    const next: ChatTurn[] = [...base, { role: 'user', content: shown }]
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
        sending.map((f) => ({ data: f.data })),
      )
      if (sending.length) setFiles([])
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
    <div className="mx-auto flex min-h-[calc(100dvh-4.5rem)] max-w-3xl flex-col gap-4 lg:min-h-[calc(100dvh-7rem)]">
      <div className="grid items-center gap-x-6 gap-y-3 sm:grid-cols-[minmax(0,1fr)_auto]">
        <div className="hidden min-w-0 flex-col gap-1 lg:flex">
          <span className="chip w-fit bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200">
            ИИ-помощник
          </span>
          <span className="text-[11px] leading-snug text-slate-500 sm:text-xs">
            Отвечает ИИ, может ошибаться. Только математика, физика и олимпиады. Не пиши личные данные.
          </span>
        </div>
        <div
          role="tablist"
          className="fixed left-1/2 top-2.5 z-30 inline-grid -translate-x-1/2 grid-cols-[auto_auto] lg:grid-cols-2 rounded-full bg-white/90 p-1 shadow-sm ring-1 ring-slate-200 backdrop-blur lg:static lg:translate-x-0 lg:justify-self-center lg:rounded-2xl lg:bg-slate-200/70 lg:shadow-none lg:ring-0 dark:bg-slate-900/90 dark:ring-slate-800 lg:dark:bg-slate-800"
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
              className={`whitespace-nowrap rounded-full px-5 py-2 text-sm font-semibold transition lg:rounded-xl lg:px-5 lg:py-1.5 ${
                mode === m
                  ? 'bg-slate-200 shadow-sm lg:bg-white dark:bg-slate-700 lg:dark:bg-slate-950'
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
      {mode === 'training' && !problemId && turns.length === 0 && !busy && (
        <ul className="animate-fade-up space-y-1 px-1">
          {SUGGESTIONS.map(([icon, q]) => (
            <li key={q}>
              <button
                onClick={() => void send(q)}
                className="flex w-full items-center gap-3 rounded-xl px-2 py-2.5 text-left text-[15px] transition hover:bg-slate-200/60 dark:hover:bg-slate-800/60"
              >
                <span className="w-6 shrink-0 text-center text-lg" aria-hidden="true">
                  {icon}
                </span>
                <span className="truncate">{q}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {/* строка ввода всегда внизу экрана, как в ChatGPT */}
      <div className="sticky bottom-0 z-10 -mx-1 bg-slate-50/95 px-1 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2 backdrop-blur dark:bg-slate-950/95">
        {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
        {files.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-2">
            {files.map((f, i) => (
              <div
                key={i}
                className="relative flex h-16 items-center gap-2 overflow-hidden rounded-xl border border-slate-200 bg-white pr-7 text-xs dark:border-slate-800 dark:bg-slate-900"
              >
                {f.preview ? (
                  <img src={f.preview} alt="" className="h-16 w-16 object-cover" />
                ) : (
                  <span className="pl-3 text-2xl" aria-hidden="true">
                    📄
                  </span>
                )}
                <span className="max-w-28 truncate">{f.name}</span>
                <button
                  type="button"
                  onClick={() => setFiles((all) => all.filter((_, j) => j !== i))}
                  className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-slate-900/70 text-white"
                  aria-label="Убрать файл"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
        <form
          onSubmit={submit}
          className="flex items-end gap-1 rounded-[1.75rem] border border-slate-300 bg-white p-1.5 shadow-sm focus-within:border-brand-500 dark:border-slate-800 dark:bg-slate-900"
        >
          {mode === 'training' && (
            <>
              <input
                ref={fileInput}
                type="file"
                accept="image/*,application/pdf"
                multiple
                hidden
                onChange={(e) => {
                  void addFiles(e.target.files)
                  e.target.value = ''
                }}
              />
              <button
                type="button"
                onClick={() => fileInput.current?.click()}
                disabled={files.length >= 3}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 disabled:opacity-40 dark:hover:bg-slate-800 dark:hover:text-white"
                aria-label="Прикрепить фото или PDF"
                title="Прикрепить фото задачи или PDF"
              >
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                  <path d="M12 5v14M5 12h14" />
                </svg>
              </button>
            </>
          )}
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
            placeholder={mode === 'olympiad' ? 'Вопрос по условию' : 'Спросить помощника'}
            className={`max-h-60 min-h-10 flex-1 resize-none bg-transparent py-2 outline-none placeholder:text-slate-400 ${mode === 'training' ? '' : 'pl-3.5'}`}
          />
          {mic.supported && (
            <button
              type="button"
              onClick={mic.toggle}
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition ${
                mic.listening
                  ? 'animate-pulse bg-red-500 text-white'
                  : 'text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-slate-800 dark:hover:text-white'
              }`}
              aria-label={mic.listening ? 'Остановить диктовку' : 'Надиктовать'}
              title={mic.listening ? 'Остановить диктовку' : 'Надиктовать'}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <rect x="9" y="3" width="6" height="11" rx="3" />
                <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
              </svg>
            </button>
          )}
          <button
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-600 text-white transition hover:bg-brand-700 active:scale-95 disabled:opacity-40"
            disabled={busy || (!text.trim() && files.length === 0)}
            aria-label="Отправить"
            title="Отправить"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
              <path d="M12 19V5M5 12l7-7 7 7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </form>
        <div className="mt-1.5 text-center text-[11px] text-slate-500 lg:hidden">
          ИИ может ошибаться. Не пиши личные данные.
        </div>
        {left != null && <div className="mt-1 text-xs text-slate-500">Осталось сообщений на сегодня: {left}</div>}
      </div>
    </div>
  )
}
