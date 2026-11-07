// Язык интерфейса: русский (по умолчанию) или казахский. Ключ перевода — русская фраза;
// нет перевода в словаре — показывается русский текст. Язык меняется перезагрузкой страницы.
import { KK, KK_TOPICS } from './kk'

export type Lang = 'ru' | 'kk'
const KEY = 'olymp-lang'

export function getLang(): Lang {
  try {
    const v = localStorage.getItem(KEY)
    if (v === 'ru' || v === 'kk') return v
  } catch {
    /* хранилище недоступно */
  }
  return typeof navigator !== 'undefined' && /^kk\b/i.test(navigator.language) ? 'kk' : 'ru'
}

export function setLang(lang: Lang): void {
  try {
    localStorage.setItem(KEY, lang)
  } catch {
    /* язык просто не запомнится */
  }
  document.documentElement.lang = lang
  location.reload()
}

const lang = getLang()
if (typeof document !== 'undefined') document.documentElement.lang = lang

/** Перевод русской фразы на текущий язык; {имя} в фразе подставляется из params. */
export function t(ru: string, params?: Record<string, string | number>): string {
  const s = lang === 'kk' ? (KK[ru] ?? topic(ru)) : ru
  return params ? s.replace(/\{(\w+)\}/g, (m, k: string) => String(params[k] ?? m)) : s
}

/** Тема из банка («Кинематика, относительное движение») по частям; чего нет в словаре — остаётся по-русски. */
function topic(ru: string): string {
  return ru.replace(/[^,;]+/g, (part) => {
    const low = part.trim().toLowerCase()
    const kk = KK_TOPICS[low]
    return kk ? part.replace(part.trim(), part.trim()[0] === part.trim()[0].toUpperCase() ? kk[0].toUpperCase() + kk.slice(1) : kk) : part
  })
}
