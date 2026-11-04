import { useState, type FormEvent } from 'react'
import { api } from '../api'
import { APP_NAME, APP_TAGLINE } from '../config'
import { saveUser, type StoredUser } from '../user'

const features = [
  { icon: '✓', title: 'Проверенные варианты', text: 'Каждый новый вариант задачи проверен кодом — без ошибок в условии.' },
  { icon: '↗', title: 'Подсказки по шагам', text: 'Сначала намёк, потом идея, потом план. Ответ — только если сам захочешь.' },
  { icon: '⚖', title: 'Проверка размерности', text: 'Перепутал м/с и м/с²? Тренажёр покажет, где ошибка.' },
]

export function Onboarding({ onDone }: { onDone: (u: StoredUser) => void }) {
  const [name, setName] = useState('')
  const [grade, setGrade] = useState<number | ''>('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    setBusy(true)
    setError('')
    try {
      const u = await api.createUser(name.trim(), grade === '' ? null : grade)
      const user = { id: u.id, name: u.name }
      saveUser(user)
      onDone(user)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-5xl flex-col justify-center gap-10 px-4 py-10 lg:flex-row lg:items-center">
      <section className="flex-1 animate-fade-up">
        <div className="mb-4 flex items-center gap-3">
          <img src="/favicon.svg" alt="" className="h-11 w-11" />
          <span className="text-xl font-extrabold tracking-tight">{APP_NAME}</span>
        </div>
        <h1 className="text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
          Готовься к олимпиадам <span className="text-brand-600 dark:text-brand-400">с наставником,</span> а не со
          шпаргалкой
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
        <h2 className="text-xl font-bold">Начнём</h2>
        <p className="mt-1 text-sm text-slate-500">Регистрация не нужна — просто представься.</p>
        <label className="mt-5 block text-sm font-semibold" htmlFor="name">
          Как тебя зовут?
        </label>
        <input
          id="name"
          autoFocus
          maxLength={40}
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 dark:border-slate-700 dark:bg-slate-950"
          placeholder="Имя или ник"
        />
        <label className="mt-4 block text-sm font-semibold" htmlFor="grade">
          Класс
        </label>
        <select
          id="grade"
          value={grade}
          onChange={(e) => setGrade(e.target.value ? Number(e.target.value) : '')}
          className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 dark:border-slate-700 dark:bg-slate-950"
        >
          <option value="">Не указывать</option>
          {[5, 6, 7, 8, 9, 10, 11].map((g) => (
            <option key={g} value={g}>
              {g} класс
            </option>
          ))}
        </select>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        <button className="btn-primary mt-6 w-full" disabled={busy || !name.trim()}>
          {busy ? 'Секунду…' : 'Перейти к задачам →'}
        </button>
      </form>
    </div>
  )
}
