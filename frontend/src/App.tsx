import { useState } from 'react'
import { api } from './api'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ChatPage } from './pages/Chat'
import { ContestPage, ContestsPage } from './pages/Contests'
import { LeaderboardPage } from './pages/Leaderboard'
import { Onboarding } from './pages/Onboarding'
import { ProblemPage } from './pages/Problem'
import { ProblemsPage } from './pages/Problems'
import { ProfilePage } from './pages/Profile'
import { TermsPage } from './pages/Terms'
import { PointsProvider } from './points'
import { PrefsProvider } from './prefs'
import { clearUser, getUser, type StoredUser } from './user'

export default function App() {
  const [user, setUser] = useState<StoredUser | null>(getUser())

  if (!user) return <Onboarding onDone={setUser} />

  // Выход: отозвать сессию на сервере (токен перестаёт работать) и стереть данные с устройства.
  const logout = () => {
    api.logout().catch(() => {
      /* сервер недоступен — токен всё равно забываем на устройстве */
    })
    clearUser()
    setUser(null)
  }

  return (
    <PrefsProvider>
      <PointsProvider key={user.id}>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout onLogout={logout} />}>
              <Route index element={<ChatPage />} />
              <Route path="problems" element={<ProblemsPage />} />
              <Route path="problem/:id" element={<ProblemPage />} />
              <Route path="profile" element={<ProfilePage onLogout={logout} />} />
              <Route path="leaderboard" element={<LeaderboardPage />} />
              <Route path="chat" element={<ChatRedirect />} />
              <Route path="contests" element={<ContestsPage />} />
              <Route path="contests/:id" element={<ContestPage />} />
              <Route path="terms" element={<TermsPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </PointsProvider>
    </PrefsProvider>
  )
}

/** Старые ссылки /chat?problem=… ведут на главную с чатом. */
function ChatRedirect() {
  const { search } = useLocation()
  return <Navigate to={`/${search}`} replace />
}
