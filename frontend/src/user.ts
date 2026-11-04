// Профиль ученика хранится в браузере (MVP без паролей).

export interface StoredUser {
  id: string
  name: string
}

const KEY = 'olymp-user'

export function getUser(): StoredUser | null {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as StoredUser) : null
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

export function clearUser(): void {
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* ignore */
  }
}
