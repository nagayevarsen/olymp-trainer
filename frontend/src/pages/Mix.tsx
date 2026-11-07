// Микс: несколько задач из разных олимпиад, все одного типа — либо на доказательство, либо с ответом.
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type MixItem, type Subject } from '../api'
import { SUBJECT_NAMES } from '../lib/text'
import { t } from '../i18n'

export function MixPage() {
  const [kind, setKind] = useState<'answer' | 'proof'>('answer')
  const [subject, setSubject] = useState<Subject | null>(null)
  const [items, setItems] = useState<MixItem[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function build() {
    setBusy(true)
    setError('')
    try {
      setItems(await api.mix(kind, subject, 6))
    } catch (e) {
      setError(e instanceof Error ? e.message : t('Не удалось собрать микс'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <header>
        <Link to="/problems" className="text-sm font-semibold text-brand-600 hover:underline">
          {t('← задачи')}
        </Link>
        <h1 className="mt-2 text-2xl font-extrabold tracking-tight">{t('Микс задач')}</h1>
        <p className="mt-1 text-sm text-slate-500">
          {t('Шесть ещё не решённых задач из разных олимпиад. Все одного типа: или с ответом, или на доказательство.')}
        </p>
      </header>
      <div className="flex flex-wrap gap-2">
        {(['answer', 'proof'] as const).map((k) => (
          <button key={k} onClick={() => setKind(k)} className={kind === k ? 'btn-primary' : 'btn-ghost'}>
            {k === 'answer' ? t('С ответом') : t('Доказательства')}
          </button>
        ))}
        {([null, 'math', 'physics'] as const).map((s) => (
          <button key={s ?? 'all'} onClick={() => setSubject(s)} className={subject === s ? 'btn-primary' : 'btn-ghost'}>
            {s ? SUBJECT_NAMES[s] : t('Любой предмет')}
          </button>
        ))}
      </div>
      <button onClick={build} disabled={busy} className="btn-primary">
        {busy ? t('Собираю…') : items ? t('Собрать другой') : t('Собрать микс')}
      </button>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {items && items.length === 0 && <p className="text-slate-500">{t('Подходящих нерешённых задач не нашлось.')}</p>}
      {items && items.length > 0 && (
        <ol className="space-y-2">
          {items.map((p, i) => (
            <li key={p.id}>
              <Link to={`/problem/${p.id}`} className="card block p-4 transition hover:border-brand-400">
                <div className="text-xs text-slate-500">
                  {i + 1}. {SUBJECT_NAMES[p.subject]} · {t(p.topic)} · {t('{n} б.', { n: p.points })}
                </div>
                <div className="mt-1 font-semibold">{p.title}</div>
                <div className="mt-0.5 text-xs text-slate-500">{p.source}</div>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
