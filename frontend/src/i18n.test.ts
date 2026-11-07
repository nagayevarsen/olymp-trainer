import { describe, expect, it } from 'vitest'
import { KK } from './kk'

// Исходники приложения как текст (без самих тестов и словаря).
const SOURCES = import.meta.glob(['./**/*.ts', './**/*.tsx', '!./**/*.test.ts', '!./kk.ts'], {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

/** Русские фразы из вызовов t('…') во всём коде. */
function keys(): string[] {
  const out = new Set<string>()
  for (const src of Object.values(SOURCES)) {
    for (const m of src.matchAll(/(?<![\w.])t\('((?:[^'\\\n]|\\.)*)'/g)) {
      const k = m[1].replace(/\\'/g, "'")
      if (/[А-Яа-яЁё]/.test(k)) out.add(k)
    }
  }
  return [...out]
}

describe('казахский перевод', () => {
  it('у каждой русской фразы в коде есть перевод', () => {
    expect(keys().length).toBeGreaterThan(200)
    const missing = keys().filter((k) => !(k in KK))
    expect(missing).toEqual([])
  })

  it('в переводе сохранены все {подстановки}', () => {
    const bad = Object.entries(KK).filter(([ru, kk]) => {
      const slots = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join()
      return slots(ru) !== slots(kk)
    })
    expect(bad.map(([ru]) => ru)).toEqual([])
  })
})
