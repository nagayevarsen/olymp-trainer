import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { OfflineOverlay } from './components/Offline'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
    <OfflineOverlay />
  </StrictMode>,
)

// Service worker хранит оболочку приложения — без интернета откроется экран «Нет интернета».
// Только в собранной версии: в разработке он мешал бы видеть свежие изменения.
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      /* без service worker приложение работает как обычно */
    })
  })
}
