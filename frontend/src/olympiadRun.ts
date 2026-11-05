// Идущая пробная олимпиада на время. Хранится на устройстве, чтобы таймер пережил перезагрузку.

export interface OlympiadRun {
  contestId: string
  title: string
  problemIds: string[]
  /** Варианты с другими числами: id задачи → seed. */
  seeds: Record<string, number>
  start: number
  durationMin: number
  finished: boolean
}

const KEY = 'olymp-run'
const listeners = new Set<() => void>()

export function getRun(): OlympiadRun | null {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? 'null') as OlympiadRun | null
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
