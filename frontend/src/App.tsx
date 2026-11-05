import { useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ChatPage } from './pages/Chat'
import { LeaderboardPage } from './pages/Leaderboard'
import { Onboarding } from './pages/Onboarding'
import { ProblemPage } from './pages/Problem'
import { ProblemsPage } from './pages/Problems'
import { ProfilePage } from './pages/Profile'
import { TermsPage } from './pages/Terms'
import { PointsProvider } from './points'
import { clearUser, getUser, type StoredUser } from './user'

export default function App() {
  const [user, setUser] = useState<StoredUser | null>(getUser())

  if (!user) return <Onboarding onDone={setUser} />

  return (
    <PointsProvider key={user.id}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<ProblemsPage />} />
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
            <Route path="chat" element={<ChatPage />} />
            <Route path="terms" element={<TermsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </PointsProvider>
  )
}
