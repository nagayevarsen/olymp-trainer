import { useState } from 'react'
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

  return (
    <PrefsProvider>
      <PointsProvider key={user.id}>
        <BrowserRouter>
          <Routes>
            <Route
              element={
                <Layout
                  onLogout={() => {
                    clearUser()
                    setUser(null)
                  }}
                />
              }
            >
              <Route index element={<ChatPage />} />
              <Route path="problems" element={<ProblemsPage />} />
              <Route path="problem/:id" element={<ProblemPage />} />
              <Route
                path="profile"
                element={
                  <ProfilePage
                    onLogout={() => {
                      clearUser()
                      setUser(null)
                    }}
                  />
                }
              />
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
