import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { usePrefs } from '../prefs'
import { ThemeSwitch } from './ThemeSwitch'

/** Расширенные настройки (шестерёнка в левой панели). */
export function SettingsDialog({ open, onClose, onLogout }: { open: boolean; onClose: () => void; onLogout: () => void }) {
  const { prefs, setPref } = usePrefs()

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Настройки"
        className="card w-full max-w-md animate-fade-up space-y-5 p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">Настройки</h2>
          <button onClick={onClose} className="icon-btn" aria-label="Закрыть">
            ✕
          </button>
        </div>
        <Row title="Тема" hint="Светлая, тёмная или как в системе устройства">
          <ThemeSwitch />
        </Row>
        <Row title="Праздничное оформление" hint="Новый год, 8 Марта, Наурыз, День Конституции, День Независимости">
          <Toggle checked={prefs.holidays} onChange={(v) => setPref('holidays', v)} />
        </Row>
        <Row title="Фоновые символы" hint="Еле заметные π, ∑, ∫ на фоне">
          <Toggle checked={prefs.decor} onChange={(v) => setPref('decor', v)} />
        </Row>
        <div className="flex flex-wrap gap-4 border-t border-slate-200 pt-4 text-sm dark:border-slate-800">
          <Link to="/profile" onClick={onClose} className="font-semibold text-brand-600 hover:underline">
            Аккаунт и прогресс
          </Link>
          <Link to="/terms" onClick={onClose} className="font-semibold text-brand-600 hover:underline">
            Условия и данные
          </Link>
          <button onClick={onLogout} className="ml-auto font-semibold text-slate-500 hover:underline">
            Выйти
          </button>
        </div>
      </div>
    </div>
  )
}

function Row({ title, hint, children }: { title: string; hint: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <div className="font-semibold">{title}</div>
        <div className="text-xs text-slate-500">{hint}</div>
      </div>
      {children}
    </div>
  )
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-11 shrink-0 rounded-full transition ${checked ? 'bg-brand-600' : 'bg-slate-300 dark:bg-slate-700'}`}
    >
      <span
        className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${checked ? 'left-[22px]' : 'left-0.5'}`}
      />
    </button>
  )
}
