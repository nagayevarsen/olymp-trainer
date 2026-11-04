import { describe, expect, it } from 'vitest'
import { pluralPoints, splitMath } from './text'

describe('splitMath', () => {
  it('разделяет текст, формулы и жирный', () => {
    expect(splitMath('Скорость $v = 10$ м/с, **ответ** $$x^2$$')).toEqual([
      { kind: 'text', value: 'Скорость ' },
      { kind: 'math', value: 'v = 10', display: false },
      { kind: 'text', value: ' м/с, ' },
      { kind: 'bold', value: 'ответ' },
      { kind: 'text', value: ' ' },
      { kind: 'math', value: 'x^2', display: true },
    ])
  })
  it('текст без формул остаётся как есть', () => {
    expect(splitMath('просто текст')).toEqual([{ kind: 'text', value: 'просто текст' }])
  })
})

describe('pluralPoints', () => {
  it('склоняет «балл»', () => {
    expect(pluralPoints(1)).toBe('балл')
    expect(pluralPoints(3)).toBe('балла')
    expect(pluralPoints(5)).toBe('баллов')
    expect(pluralPoints(11)).toBe('баллов')
    expect(pluralPoints(21)).toBe('балл')
    expect(pluralPoints(112)).toBe('баллов')
  })
})
