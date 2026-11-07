import { getLang, setLang, t, type Lang } from '../i18n'

const OPTIONS: { value: Lang; label: string; title: string }[] = [
  { value: 'ru', label: 'RU', title: 'Русский' },
  { value: 'kk', label: 'ҚАЗ', title: 'Қазақша' },
]

/** Плашка выбора языка: русский / казахский (рядом с переключателем темы). */
export function LangSwitch({ className = '' }: { className?: string }) {
  const lang = getLang()
  return (
    <div
      role="radiogroup"
      aria-label={t('Язык интерфейса')}
      className={`inline-flex rounded-xl border border-slate-200 bg-white p-0.5 dark:border-slate-700 dark:bg-slate-900 ${className}`}
    >
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={lang === o.value}
          aria-label={o.title}
          title={o.title}
          onClick={() => lang !== o.value && setLang(o.value)}
          className={`flex h-8 items-center justify-center rounded-lg px-2 text-xs font-bold transition ${
            lang === o.value
              ? 'bg-brand-600 text-white'
              : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
