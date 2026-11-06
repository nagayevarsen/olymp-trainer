import { lazy, useState } from 'react'
import { api } from './api'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Onboarding } from './pages/Onboarding'
import { PointsProvider } from './points'
import { PrefsProvider } from './prefs'
import { clearUser, getUser, type StoredUser } from './user'

// Страницы грузятся по мере перехода: экран входа и первая страница открываются быстрее,
// а KaTeX (формулы) не нужен, пока ученик не вошёл.
const ChatPage = lazy(() => import('./pages/Chat').then((m) => ({ default: m.ChatPage })))
const ContestsPage = lazy(() => import('./pages/Contests').then((m) => ({ default: m.ContestsPage })))
const ContestPage = lazy(() => import('./pages/Contests').then((m) => ({ default: m.ContestPage })))
const LeaderboardPage = lazy(() => import('./pages/Leaderboard').then((m) => ({ default: m.LeaderboardPage })))
const ProblemPage = lazy(() => import('./pages/Problem').then((m) => ({ default: m.ProblemPage })))
const ProblemsPage = lazy(() => import('./pages/Problems').then((m) => ({ default: m.ProblemsPage })))
const ProfilePage = lazy(() => import('./pages/Profile').then((m) => ({ default: m.ProfilePage })))
const TermsPage = lazy(() => import('./pages/Terms').then((m) => ({ default: m.TermsPage })))

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
