import type { ProblemDetail } from '../api'

/** Как вводить ответ: число с единицами, число или формула с перечнем обозначений. */
export function answerHint(p: Pick<ProblemDetail, 'answer_kind' | 'needs_unit' | 'variables'>): {
  text: string
} {
  if (p.answer_kind === 'formula') {
    const names = Object.entries(p.variables)
      .map(([k, v]) => `${k} — ${v}`)
      .join('; ')
    return {
      text: `Ответ — формула. Пиши через обозначения: ${names}. Пример записи: 17*g/29, 2*pi*sqrt(l/g), m*v0^2/2.`,
    }
  }
  return p.needs_unit
    ? {
        text: 'Пиши с единицами измерения: 12 м/с, 4,5 кДж, 300 мА. Тренажёр сам переведёт и проверит размерность.',
      }
    : { text: 'Число или выражение: 42, 3/4, 2√3, 1,5.' }
}
