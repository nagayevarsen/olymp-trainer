import { useEffect, useState } from 'react'
import { getThemeChoice, setThemeChoice, watchSystemTheme, type ThemeChoice } from '../theme'
import { t } from '../i18n'

const svg = {
  width: 16,
  height: 16,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

const ICONS: Record<ThemeChoice, React.ReactNode> = {
  light: (
    <svg {...svg} aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  ),
  dark: (
    <svg {...svg} aria-hidden="true">
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </svg>
  ),
  system: (
    <svg {...svg} aria-hidden="true">
      <rect x="3" y="4" width="18" height="12" rx="2" />
      <path d="M8 20h8M12 16v4" />
    </svg>
  ),
}

const OPTIONS: { value: ThemeChoice; label: string }[] = [
  { value: 'light', label: t('Светлая тема') },
  { value: 'dark', label: t('Тёмная тема') },
  { value: 'system', label: t('Как в системе') },
]

/** Плашка из трёх кнопок: светлая / тёмная / как в системе. */
export function ThemeSwitch({ className = '' }: { className?: string }) {
  const [choice, setChoice] = useState<ThemeChoice>(getThemeChoice)

  useEffect(() => watchSystemTheme(), [])

  return (
    <div
      role="radiogroup"
      aria-label={t('Тема оформления')}
      className={`inline-flex rounded-xl border border-slate-200 bg-white p-0.5 dark:border-slate-700 dark:bg-slate-900 ${className}`}
    >
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={choice === o.value}
          aria-label={o.label}
          title={o.label}
          onClick={() => {
            setThemeChoice(o.value)
            setChoice(o.value)
          }}
          className={`flex h-8 w-8 items-center justify-center rounded-lg text-sm transition ${
            choice === o.value
              ? 'bg-brand-600 text-white'
              : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
          }`}
        >
          {ICONS[o.value]}
        </button>
      ))}
    </div>
  )
}
