import { t } from '../i18n'
// Праздники (Казахстан и международные) для тонкой праздничной полоски.

export interface Holiday {
  id: string
  emoji: string
  greeting: string
  /** Классы Tailwind для тонкой праздничной полоски. */
  strip: string
}

// [месяц (1–12), день] — первый и последний день показа, включительно.
const HOLIDAYS: { from: [number, number]; to: [number, number]; h: Holiday }[] = [
  {
    from: [12, 25],
    to: [1, 2],
    h: { id: 'newyear', emoji: '❄️', greeting: t('С Новым годом!'), strip: 'from-sky-500/15 via-indigo-500/15 to-sky-500/15' },
  },
  {
    from: [3, 7],
    to: [3, 8],
    h: { id: 'march8', emoji: '🌷', greeting: t('С 8 Марта!'), strip: 'from-pink-500/15 via-rose-400/15 to-pink-500/15' },
  },
  {
    from: [3, 20],
    to: [3, 23],
    h: {
      id: 'nauryz',
      emoji: '🌸',
      greeting: t('Наурыз мейрамы құтты болсын!'),
      strip: 'from-emerald-500/15 via-amber-400/15 to-emerald-500/15',
    },
  },
  {
    from: [8, 30],
    to: [8, 30],
    h: { id: 'constitution', emoji: '📜', greeting: t('С Днём Конституции Республики Казахстан!'), strip: 'from-sky-500/15 via-amber-400/15 to-sky-500/15' },
  },
  {
    from: [12, 16],
    to: [12, 17],
    h: { id: 'independence', emoji: '🇰🇿', greeting: t('С Днём Независимости!'), strip: 'from-sky-500/15 via-amber-400/15 to-sky-500/15' },
  },
]

function inRange(m: number, d: number, from: [number, number], to: [number, number]): boolean {
  const v = m * 100 + d
  const a = from[0] * 100 + from[1]
  const b = to[0] * 100 + to[1]
  return a <= b ? v >= a && v <= b : v >= a || v <= b // интервал через Новый год
}

export function holidayOn(date = new Date()): Holiday | null {
  const m = date.getMonth() + 1
  const d = date.getDate()
  return HOLIDAYS.find((x) => inRange(m, d, x.from, x.to))?.h ?? null
}
