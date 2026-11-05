// Настройки интерфейса на этом устройстве: свёрнута ли левая панель, праздничное оформление, фоновые символы.

import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'

export interface Prefs {
  sidebarOpen: boolean
  holidays: boolean
  decor: boolean
}

const KEY = 'olymp-prefs'
const DEFAULTS: Prefs = { sidebarOpen: true, holidays: true, decor: true }

function load(): Prefs {
  try {
    return { ...DEFAULTS, ...(JSON.parse(localStorage.getItem(KEY) ?? '{}') as Partial<Prefs>) }
  } catch {
    return DEFAULTS
  }
}

interface PrefsCtx {
  prefs: Prefs
  setPref: <K extends keyof Prefs>(key: K, value: Prefs[K]) => void
}

const Ctx = createContext<PrefsCtx>({ prefs: DEFAULTS, setPref: () => {} })

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<Prefs>(load)
  const setPref = useCallback(<K extends keyof Prefs>(key: K, value: Prefs[K]) => {
    setPrefs((p) => {
      const next = { ...p, [key]: value }
      try {
        localStorage.setItem(KEY, JSON.stringify(next))
      } catch {
        /* не запомнится — не страшно */
      }
      return next
    })
  }, [])
  return <Ctx.Provider value={{ prefs, setPref }}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const usePrefs = () => useContext(Ctx)
