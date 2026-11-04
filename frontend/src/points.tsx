// Общие баллы ученика в шапке: обновляются после каждого решения.

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api } from './api'

interface PointsCtx {
  points: number
  setPoints: (n: number) => void
  refresh: () => void
}

const Ctx = createContext<PointsCtx>({ points: 0, setPoints: () => {}, refresh: () => {} })

export function PointsProvider({ children }: { children: ReactNode }) {
  const [points, setPoints] = useState(0)
  const refresh = useCallback(() => {
    api
      .me()
      .then((me) => setPoints(me.points))
      .catch(() => {})
  }, [])
  useEffect(refresh, [refresh])
  return <Ctx.Provider value={{ points, setPoints, refresh }}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const usePoints = () => useContext(Ctx)
