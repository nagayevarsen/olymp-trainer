import { getLang, t } from './i18n'
// Клиент HTTP API бэкенда. В разработке запросы /api проксируются на localhost:8000.

import { clearUser, getUser } from './user'

const BASE = import.meta.env.VITE_API_URL ?? ''

export type Subject = 'math' | 'physics'

export interface Track {
  id: string
  title: string
  olympiad: string
  russian: boolean
  stage: string
  subjects: Subject[]
  years: number[]
  grades: number[]
  count: number
}

export interface ProblemListItem {
  id: string
  track: string
  year: number | null
  title: string
  subject: Subject
  topic: string
  points: number
  source: string
  can_clone: boolean
  solved: boolean
  earned: number
  started: boolean
  solve_rate: number | null
}

export interface Verification {
  reproduces_original: boolean
  cross_checked: boolean
  checked_by: string[]
}

export interface ProblemDetail {
  id: string
  title: string
  subject: Subject
  topic: string
  statement: string
  original_statement: string | null
  analogue_only: boolean // в тренировке показываем только аналог, оригинал берегут для олимпиады
  seed: number | null
  points: number
  source: { label: string; stage: string; url: string | null; russian: boolean }
  track: { id: string; title: string }
  needs_unit: boolean
  answer_kind: 'number' | 'formula' | 'proof'
  variables: Record<string, string>
  figures: string[]
  can_clone: boolean
  verification: Verification | null
  hints_total: number
  hints_opened: string[]
  solution: string | null
  progress: {
    attempts: number
    hints_used: number
    solution_viewed: boolean
    solved: boolean
    earned: number
  }
  potential: number
  solve_rate: number | null
}

export interface ProofResult {
  points: number
  max_points: number
  comment: string
  correct: boolean
  earned: number
  first_solve: boolean
  total_points: number
}

export interface CheckResult {
  status: 'correct' | 'wrong' | 'wrong_dimension' | 'unparsable' | 'unit_missing'
  correct: boolean
  message: string
  earned: number
  first_solve: boolean
  already_solved: boolean
  solve_rate: number | null
  total_points: number
}

export interface TopicStat {
  subject: Subject
  topic: string
  total: number
  solved: number
  tried: number
  points: number
  mastery: number | null // уровень в теме, %: набранные баллы / баллы задач, которые пробовал
}

export interface Me {
  id: string
  name: string
  grade: number | null
  has_account: boolean
  streak: number
  points: number
  solved: number
  rank: number | null
  users_total: number
  topics: TopicStat[]
  weak_topics: string[]
  track: string | null
  recommended: { id: string; title: string; topic: string; subject: Subject; points: number }[]
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
  cards?: ChatCard[]
}

export interface ChatCard {
  kind: 'problem' | 'contest'
  id: string
  title: string
  source?: string
  topic?: string
  points?: number
  total_points?: number
  count?: number
}

export interface ChatReply {
  reply: string
  code_runs: number
  cards: ChatCard[]
  left: number
}

export interface ContestRow {
  russian: boolean
  duration_min: number | null
  duration_source: { name: string; url: string } | null
  official_points: boolean
  id: string
  title: string
  subject: Subject
  year: number | null
  grade: number | null
  count: number
  total_points: number
  solved: number
  earned: number
  /** Точного совпадения с запросом нет, олимпиада показана как «возможно подходящая». */
  approx?: boolean
  /** Сколько задач в официальном варианте (null — не подтверждено) и все ли они есть в банке. */
  official_count?: number | null
  complete?: boolean
  equal_weight?: boolean
}

export interface MixItem {
  id: string
  title: string
  source: string
  topic: string
  points: number
  subject: Subject
}

export interface StreakInfo {
  count: number
  status: 'new' | 'done_today' | 'active' | 'restorable' | 'broken'
  restores_left: number
  restores_per_month: number
}

export interface DailyInfo {
  problem: { id: string; title: string; topic: string; points: number; source: string } | null
  streak: StreakInfo
}

export interface GradeRow {
  problem_id: string
  points: number
  max_points: number
  answer_correct: boolean
  comment: string
}

export interface ContestDetail extends ContestRow {
  stage: string
  problems: {
    can_clone: boolean
    source: string
    url: string | null
    n: number
    id: string
    title: string
    topic: string
    points: number
    solved: boolean
    earned: number
    started: boolean
  }[]
}

type Account = { id: string; name: string; grade: number | null; token: string }

export interface LeaderRow {
  place: number
  me: boolean
  name: string | null // ник виден только владельцу строки
  grade: number | null
  points: number
  solved: number
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const user = getUser()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (user) headers['Authorization'] = `Bearer ${user.token}`
  let res: Response
  // Чтение (GET) повторяем при коротких сбоях сервера или прокси (502–504, 520–526): после выкладки или
  // перезапуска он отвечает так секунд 20–60. Запись (POST и др.) не повторяем, чтобы не продублировать действие.
  const retryable = !init.method || init.method === 'GET'
  for (let attempt = 0; ; attempt++) {
    try {
      res = await fetch(BASE + path, { ...init, headers: { ...headers, ...(init.headers ?? {}) } })
    } catch {
      window.dispatchEvent(new Event('olymp:network-error')) // покажет экран «Нет интернета», если сети нет
      throw new ApiError(0, t('Нет связи с сервером. Проверь интернет.'))
    }
    const transient = [502, 503, 504, 520, 521, 522, 523, 524, 525, 526].includes(res.status)
    if (!(retryable && transient && attempt < 3)) break
    await new Promise((r) => setTimeout(r, 1500 * (attempt + 1)))
  }
  if (res.status === 401 && user) {
    // Сессия истекла или отозвана (выход на другом устройстве) — вернуться к экрану входа.
    clearUser()
    window.location.reload()
  }
  if (!res.ok) {
    let msg = t('Ошибка {n}', { n: res.status })
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') msg = body.detail
    } catch {
      /* тело не JSON */
    }
    throw new ApiError(res.status, msg)
  }
  return res.json() as Promise<T>
}

const post = <T>(path: string, body: unknown = {}) => request<T>(path, { method: 'POST', body: JSON.stringify(body) })

export const api = {
  createUser: (name: string, grade: number | null) => post<Account>('/api/users', { name, grade }),
  logout: () => post<{ ok: boolean }>('/api/logout'),
  getAvatar: () => request<{ avatar: unknown }>('/api/me/avatar'),
  setAvatar: (a: unknown) => request<{ avatar: unknown }>('/api/me/avatar', { method: 'PUT', body: JSON.stringify(a) }),
  me: (track?: string | null) => request<Me>(`/api/me${track ? `?track=${track}` : ''}`),
  tracks: () => request<Track[]>('/api/tracks'),
  problems: (track?: string | null) => request<ProblemListItem[]>(`/api/problems${track ? `?track=${track}` : ''}`),
  problem: (id: string, seed?: number | null) =>
    request<ProblemDetail>(`/api/problems/${id}?lang=${getLang()}${seed != null ? `&seed=${seed}` : ''}`),
  variant: (id: string) =>
    post<{ seed: number; statement: string; verification: Verification | null }>(`/api/problems/${id}/variant`),
  check: (id: string, answer: string, seed?: number | null) =>
    post<CheckResult>(`/api/problems/${id}/check`, { answer, seed: seed ?? null }),
  proof: (id: string, solution: string) => post<ProofResult>(`/api/problems/${id}/proof`, { solution }),
  hint: (id: string, level: number) =>
    post<{ level: number; text: string; total: number; potential: number }>(`/api/problems/${id}/hints/${level}`),
  solution: (id: string) => post<{ solution: string; can_clone: boolean }>(`/api/problems/${id}/solution`),
  leaderboard: () => request<LeaderRow[]>('/api/leaderboard'),
  nickAvailable: (nick: string) =>
    request<{ available: boolean; reason: string | null }>(`/api/nick-available?nick=${encodeURIComponent(nick)}`),
  register: (nick: string, password: string, grade: number | null) =>
    post<Account>('/api/register', { nick, password, grade, accept_terms: true }),
  login: (nick: string, password: string) => post<Account>('/api/login', { nick, password }),
  attachAccount: (nick: string, password: string) =>
    post<{ id: string; name: string }>('/api/me/account', { nick, password }),
  deleteMe: () => request<{ deleted: boolean }>('/api/me', { method: 'DELETE' }),
  contests: (query = '', subject?: Subject | null) =>
    request<ContestRow[]>(`/api/contests?query=${encodeURIComponent(query)}${subject ? `&subject=${subject}` : ''}`),
  mix: (kind: 'answer' | 'proof', subject: Subject | null, n: number) =>
    request<MixItem[]>(`/api/mix?kind=${kind}&n=${n}${subject ? `&subject=${subject}` : ''}`),
  contest: (id: string) => request<ContestDetail>(`/api/contests/${id}`),
  daily: () => request<DailyInfo>('/api/daily'),
  restoreStreak: () => post<StreakInfo>('/api/daily/restore'),
  olympiadsWithTime: () => request<string[]>('/api/olympiad/available'),
  gradeOlympiad: (
    items: { problem_id: string; seed: number | null; answer: string; solution: string; max_points: number }[],
  ) => post<GradeRow[]>('/api/olympiad/grade', { items }),
  chat: (
    messages: ChatTurn[],
    problemId?: string | null,
    mode: 'training' | 'olympiad' = 'training',
    attachments: { data: string }[] = [],
    seed: number | null = null,
  ) => post<ChatReply>('/api/chat', { messages, problem_id: problemId ?? null, seed, mode, attachments, lang: getLang() }),
}
