import { describe, expect, it } from 'vitest'
import { formatLeft, parseRequest } from './olympiadRun'

describe('parseRequest', () => {
  it('отделяет класс от названия олимпиады', () => {
    expect(parseRequest('Жаутыковская 10 класс')).toEqual({ query: 'Жаутыковская', grade: 10 })
    expect(parseRequest('всесиб 9 кл')).toEqual({ query: 'всесиб', grade: 9 })
    expect(parseRequest('Эйлера')).toEqual({ query: 'Эйлера', grade: null })
    expect(parseRequest('смагулов 7')).toEqual({ query: 'смагулов', grade: 7 })
  })
})

describe('formatLeft', () => {
  it('часы:минуты:секунды', () => {
    expect(formatLeft(3_600_000 + 61_000)).toBe('1:01:01')
    expect(formatLeft(0)).toBe('0:00:00')
  })
})
