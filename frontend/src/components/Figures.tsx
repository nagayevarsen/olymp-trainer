const BASE = import.meta.env.VITE_API_URL ?? ''

/** Рисунки к условию задачи (вырезаны из официального PDF). */
export function Figures({ urls }: { urls: string[] }) {
  if (!urls.length) return null
  return (
    <div className="mt-4 flex flex-wrap gap-3">
      {urls.map((u, i) => (
        <a key={u} href={BASE + u} target="_blank" rel="noreferrer" className="block">
          <img
            src={BASE + u}
            alt={`Рисунок ${i + 1} к условию`}
            loading="lazy"
            className="max-h-80 max-w-full rounded-xl border border-slate-200 bg-white p-2 dark:border-slate-700 dark:invert-[0.88]"
          />
        </a>
      ))}
    </div>
  )
}
