// Вход хранится в браузере: ник и токен сессии (не пароль). id пользователя секретом не является.

export interface StoredUser {
  id: string
  name: string
  token: string
}

const KEY = 'olymp-user'
// Личные данные на этом устройстве: на общем (школьном) компьютере после выхода их видеть не должны.
const PERSONAL_KEYS = ['olymp-chats', 'olymp-avatar', 'olymp-track']

export function getUser(): StoredUser | null {
  try {
    const raw = localStorage.getItem(KEY)
    const user = raw ? (JSON.parse(raw) as Partial<StoredUser>) : null
    // Старый формат без токена больше не принимается сервером — нужно войти заново.
    return user?.id && user.name && user.token ? (user as StoredUser) : null
  } catch {
    return null
  }
}

export function saveUser(user: StoredUser): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(user))
  } catch {
    /* приватный режим браузера */
  }
}

/** Выход: забыть вход, историю чатов, аватарку и выбранный трек. */
export function clearUser(): void {
  try {
    localStorage.removeItem(KEY)
    for (const k of PERSONAL_KEYS) localStorage.removeItem(k)
  } catch {
    /* ignore */
  }
}

// Выбранный трек (олимпиада + этап) запоминается между визитами.
const TRACK_KEY = 'olymp-track'

export function getTrack(): string | null {
  try {
    return localStorage.getItem(TRACK_KEY)
  } catch {
    return null
  }
}

export function saveTrack(id: string): void {
  try {
    localStorage.setItem(TRACK_KEY, id)
  } catch {
    /* ignore */
  }
}
