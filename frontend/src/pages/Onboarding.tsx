import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api'
import { APP_NAME, APP_TAGLINE } from '../config'
import { saveUser, type StoredUser } from '../user'
import { TermsText } from './Terms'
import { ThemeSwitch } from '../components/ThemeSwitch'

const features = [
  { icon: '✓', title: 'Проверенные варианты', text: 'Каждый новый вариант задачи проверен кодом — без ошибок в условии.' },
  { icon: '↗', title: 'Подсказки по шагам', text: 'Сначала намёк, потом идея, потом план. Ответ — только если сам захочешь.' },
  { icon: '⚖', title: 'Проверка размерности', text: 'Перепутал м/с и м/с²? Тренажёр покажет, где ошибка.' },
]

export function Onboarding({ onDone }: { onDone: (u: StoredUser) => void }) {
  const [mode, setMode] = useState<'register' | 'login'>('register')
  const [nick, setNick] = useState('')
  const [password, setPassword] = useState('')
  const [grade, setGrade] = useState<number | ''>('')
  const [agree, setAgree] = useState(false)
  const [showTerms, setShowTerms] = useState(false)
  const [nickNote, setNickNote] = useState<{ ok: boolean; text: string } | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // Живая проверка: занят ли ник (только при регистрации).
  useEffect(() => {
    if (mode !== 'register' || nick.trim().length < 3) {
      setNickNote(null)
      return
    }
    const t = setTimeout(() => {
      api
        .nickAvailable(nick.trim())
        .then((r) => setNickNote(r.available ? { ok: true, text: 'Ник свободен' } : { ok: false, text: r.reason ?? 'Ник занят' }))
        .catch(() => setNickNote(null))
    }, 350)
    return () => clearTimeout(t)
  }, [nick, mode])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const u =
        mode === 'register'
          ? await api.register(nick.trim(), password, grade === '' ? null : grade)
          : await api.login(nick.trim(), password)
      const user = { id: u.id, name: u.name }
      saveUser(user)
      onDone(user)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка')
    } finally {
      setBusy(false)
    }
  }

  const input =
    'mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 dark:border-slate-700 dark:bg-slate-950'
  const canSubmit =
    nick.trim().length >= 3 && password.length >= 6 && (mode === 'login' || (agree && nickNote?.ok !== false))

  return (
    <div className="mx-auto flex min-h-dvh max-w-5xl flex-col justify-center gap-10 px-4 py-10 lg:flex-row lg:items-center">
      <section className="flex-1 animate-fade-up">
        <div className="mb-4 flex items-center gap-3">
          <img src="/favicon.svg" alt="" className="h-11 w-11" />
          <span className="text-xl font-extrabold tracking-tight">{APP_NAME}</span>
          <ThemeSwitch className="ml-auto" />
        </div>
        <h1 className="text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
          Готовься к олимпиадам, видя <span className="text-brand-600 dark:text-brand-400">свой прогресс,</span> а
          не готовые ответы
        </h1>
        <p className="mt-4 max-w-xl text-lg text-slate-600 dark:text-slate-400">{APP_TAGLINE}</p>
        <ul className="mt-8 grid gap-4 sm:grid-cols-3">
          {features.map((f) => (
            <li key={f.title} className="card p-4">
              <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-lg font-bold text-brand-600 dark:bg-brand-900/40 dark:text-brand-300">
                {f.icon}
              </div>
              <div className="font-bold">{f.title}</div>
              <div className="mt-1 text-sm text-slate-600 dark:text-slate-400">{f.text}</div>
            </li>
          ))}
        </ul>
      </section>

      <form onSubmit={submit} className="card w-full max-w-sm animate-fade-up p-6 lg:shrink-0">
        <div className="mb-4 grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1 text-sm font-semibold dark:bg-slate-800">
          {(['register', 'login'] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => {
                setMode(m)
                setError('')
              }}
              className={`rounded-lg py-1.5 transition ${mode === m ? 'bg-white shadow-sm dark:bg-slate-950' : 'text-slate-500'}`}
            >
              {m === 'register' ? 'Регистрация' : 'Вход'}
            </button>
          ))}
        </div>
        <p className="text-sm text-slate-500">
          {mode === 'register'
            ? 'Нужны только ник и пароль — без почты и телефона. Прогресс сохранится на любом устройстве.'
            : 'Войди, чтобы продолжить с того места, где остановился.'}
        </p>
        <label className="mt-5 block text-sm font-semibold" htmlFor="nick">
          Ник
        </label>
        <input
          id="nick"
          autoFocus
          autoComplete="username"
          maxLength={20}
          value={nick}
          onChange={(e) => setNick(e.target.value)}
          className={input}
          placeholder="например, mathfox"
        />
        {mode === 'register' && (
          <p className={`mt-1 text-xs ${nickNote ? (nickNote.ok ? 'text-emerald-600' : 'text-red-600') : 'text-slate-500'}`}>
            {nickNote?.text ?? 'Придумай ник, настоящее имя не нужно. 3–20 символов.'}
          </p>
        )}
        <label className="mt-4 block text-sm font-semibold" htmlFor="password">
          Пароль
        </label>
        <input
          id="password"
          type="password"
          autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
          maxLength={64}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={input}
          placeholder="не меньше 6 символов"
        />
        {mode === 'register' && (
          <>
            <label className="mt-4 block text-sm font-semibold" htmlFor="grade">
              Класс
            </label>
            <select
              id="grade"
              value={grade}
              onChange={(e) => setGrade(e.target.value ? Number(e.target.value) : '')}
              className={input}
            >
              <option value="">Не указывать</option>
              {[5, 6, 7, 8, 9, 10, 11].map((g) => (
                <option key={g} value={g}>
                  {g} класс
                </option>
              ))}
            </select>
            <label className="mt-4 flex items-start gap-2 text-sm">
              <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-0.5" />
              <span>
                Согласен с{' '}
                <button type="button" onClick={() => setShowTerms((v) => !v)} className="font-semibold text-brand-600 underline">
                  условиями
                </button>
                . В тренажёре работает ИИ.
              </span>
            </label>
            {showTerms && (
              <div className="mt-3 max-h-64 overflow-y-auto rounded-xl border border-slate-200 p-3 dark:border-slate-700">
                <TermsText />
              </div>
            )}
          </>
        )}
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        <button className="btn-primary mt-6 w-full" disabled={busy || !canSubmit}>
          {busy ? 'Секунду…' : mode === 'register' ? 'Создать аккаунт →' : 'Войти →'}
        </button>
      </form>
    </div>
  )
}
