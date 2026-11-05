// История чатов — только на этом устройстве (на сервере переписка не хранится).

import type { ChatTurn } from './api'

export type ChatMode = 'training' | 'olympiad'

export interface StoredChat {
  id: string
  title: string
  mode: ChatMode
  problemId: string | null
  turns: ChatTurn[]
  updated: number
}

const KEY = 'olymp-chats'
const MAX_CHATS = 30
const listeners = new Set<() => void>()

function readAll(): StoredChat[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '[]') as StoredChat[]
  } catch {
    return []
  }
}

function writeAll(chats: StoredChat[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(chats.slice(0, MAX_CHATS)))
  } catch {
    /* хранилище недоступно */
  }
  listeners.forEach((f) => f())
}

export function listChats(): StoredChat[] {
  return readAll().sort((a, b) => b.updated - a.updated)
}

export function getChat(id: string | null): StoredChat | null {
  return id ? (readAll().find((c) => c.id === id) ?? null) : null
}

export function newChatId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
}

export function saveChat(chat: StoredChat) {
  const rest = readAll().filter((c) => c.id !== chat.id)
  const firstQuestion = chat.turns.find((t) => t.role === 'user')?.content ?? 'Новый чат'
  const title = chat.title && chat.title !== 'Новый чат' ? chat.title : firstQuestion.slice(0, 48)
  writeAll([{ ...chat, title, turns: chat.turns.slice(-40), updated: Date.now() }, ...rest])
}

export function deleteChat(id: string) {
  writeAll(readAll().filter((c) => c.id !== id))
}

export function onChatsChange(f: () => void): () => void {
  listeners.add(f)
  return () => listeners.delete(f)
}
