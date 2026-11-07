import type { ProblemDetail } from '../api'
import { t } from '../i18n'

/** Как вводить ответ: число с единицами, число или формула с перечнем обозначений. */
export function answerHint(p: Pick<ProblemDetail, 'answer_kind' | 'needs_unit' | 'variables'>): {
  text: string
} {
  if (p.answer_kind === 'proof') {
    return {
      text: t('Задача на доказательство: напиши решение полностью. ИИ сверит его с официальным решением жюри и поставит баллы из 7 — оценка ориентировочная.'),
    }
  }
  if (p.answer_kind === 'formula') {
    const names = Object.entries(p.variables)
      .map(([k, v]) => `${k} — ${v}`)
      .join('; ')
    return {
      text: t('Ответ — формула. Пиши через обозначения: {names}. Пример записи: 17*g/29, 2*pi*sqrt(l/g), m*v0^2/2.', { names }),
    }
  }
  return p.needs_unit
    ? {
        text: t('Пиши с единицами измерения: 12 м/с, 4,5 кДж, 300 мА. Тренажёр сам переведёт и проверит размерность.'),
      }
    : { text: t('Число или выражение: 42, 3/4, 2√3, 1,5.') }
}
