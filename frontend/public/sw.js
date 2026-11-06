// Service worker: хранит оболочку приложения, чтобы без интернета открывался экран «Нет интернета»,
// а не страница ошибки браузера. Запросы к API никогда не кэшируются.

const VERSION = 'v1'
const SHELL = `olymp-shell-${VERSION}`
const ASSETS = `olymp-assets-${VERSION}`
const FONTS = 'olymp-fonts'

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL)
      .then((c) => c.addAll(['/', '/favicon.svg']))
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (event) => {
  const keep = new Set([SHELL, ASSETS, FONTS])
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => !keep.has(k)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)

  // API — только сеть: данные учеников не должны залежаться в кэше.
  if (url.origin === self.location.origin && url.pathname.startsWith('/api/')) return

  // Страницы: сначала сеть (новая версия), без сети — сохранённая оболочка.
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone()
          caches.open(SHELL).then((c) => c.put('/', copy))
          return res
        })
        .catch(() => caches.match('/')),
    )
    return
  }

  // Собранные файлы с хэшем в имени не меняются — берём из кэша, иначе из сети и запоминаем.
  if (url.origin === self.location.origin && (url.pathname.startsWith('/assets/') || url.pathname === '/favicon.svg')) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            if (res.ok) {
              const copy = res.clone()
              caches.open(ASSETS).then((c) => c.put(req, copy))
            }
            return res
          }),
      ),
    )
    return
  }

  // Шрифт Manrope: из кэша, а в фоне обновляем.
  if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com') {
    event.respondWith(
      caches.open(FONTS).then((c) =>
        c.match(req).then((hit) => {
          const net = fetch(req)
            .then((res) => {
              if (res.ok || res.type === 'opaque') c.put(req, res.clone())
              return res
            })
            .catch(() => hit)
          return hit || net
        }),
      ),
    )
  }
})
