// Идущая пробная олимпиада на время. Хранится на устройстве, чтобы таймер и решения пережили перезагрузку.

import type { GradeRow } from './api'

export interface OlympiadRun {
  contestId: string
  title: string
  problemIds: string[]
  /** Варианты с другими числами: id задачи → seed. */
  seeds: Record<string, number>
  /** Баллы за задачу (самая сложная — 10, самая простая — 3). */
  points: Record<string, number>
  /** Решения ученика: id задачи → ответ и полное решение. */
  answers: Record<string, { answer: string; solution: string }>
  start: number
  durationMin: number
  finished: boolean
  grades?: GradeRow[]
}

const KEY = 'olymp-run'
const listeners = new Set<() => void>()

export function getRun(): OlympiadRun | null {
  try {
    const run = JSON.parse(localStorage.getItem(KEY) ?? 'null') as OlympiadRun | null
    return run ? { ...run, answers: run.answers ?? {}, points: run.points ?? {} } : null
  } catch {
    return null
  }
}

export function setRun(run: OlympiadRun | null) {
  try {
    if (run) localStorage.setItem(KEY, JSON.stringify(run))
    else localStorage.removeItem(KEY)
  } catch {
    /* хранилище недоступно */
  }
  listeners.forEach((f) => f())
}

export function onRunChange(f: () => void): () => void {
  listeners.add(f)
  return () => listeners.delete(f)
}

export function msLeft(run: OlympiadRun, now = Date.now()): number {
  return Math.max(0, run.start + run.durationMin * 60_000 - now)
}

export function formatLeft(ms: number): string {
  const s = Math.ceil(ms / 1000)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

/** Идёт ли сейчас олимпиада, в которую входит задача (тогда подсказки и разбор скрыты). */
export function problemLocked(problemId: string): boolean {
  const run = getRun()
  return !!run && !run.finished && msLeft(run) > 0 && run.problemIds.includes(problemId)
}

/** Время по умолчанию — типичное для этапа; ученик может поменять. */
export function defaultDuration(stage: string): number {
  if (['final', 'republic', 'international'].includes(stage)) return 240
  if (['region', 'city'].includes(stage)) return 180
  return 120
}

/** «Жаутыковская 10 класс» → { query: 'Жаутыковская', grade: 10 }. */
export function parseRequest(text: string): { query: string; grade: number | null } {
  const m = text.match(/(\d{1,2})\s*(?:-?й\s*)?(?:класс|кл\.?|сынып|grade)?/i)
  const grade = m && Number(m[1]) >= 1 && Number(m[1]) <= 11 ? Number(m[1]) : null
  const query = text
    .replace(/(\d{1,2})\s*(?:-?й\s*)?(?:класс\w*|кл\.?|сынып\w*|grade)/gi, ' ')
    .replace(/\b(\d{1,2})\b/g, (d) => (grade !== null && Number(d) === grade ? ' ' : d))
    .replace(/\s+/g, ' ')
    .trim()
  return { query, grade }
}
