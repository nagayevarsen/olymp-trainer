// Аватарка: по умолчанию случайная пиксельная мордочка (бесцветная, 8×8), можно сменить на своё фото.
// Фото хранится ТОЛЬКО на этом устройстве (на сервер не отправляется) — так мы не собираем персональные данные.

import { useEffect, useRef, useState } from 'react'

type AvatarData = { kind: 'pixel'; seed: number } | { kind: 'photo'; dataUrl: string }

const KEY = 'olymp-avatar'
const listeners = new Set<() => void>()

function load(): AvatarData {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? 'null') as AvatarData | null
    if (v) return v
  } catch {
    /* нет хранилища */
  }
  const fresh: AvatarData = { kind: 'pixel', seed: Math.floor(Math.random() * 1_000_000_000) }
  save(fresh)
  return fresh
}

function save(a: AvatarData) {
  try {
    localStorage.setItem(KEY, JSON.stringify(a))
  } catch {
    /* фото слишком большое или хранилище недоступно — просто не запомнится */
  }
  listeners.forEach((f) => f())
}

/** Детерминированный генератор чисел по seed. */
function rng(seed: number) {
  let s = seed >>> 0 || 1
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0
    return s / 2 ** 32
  }
}

/** 8×8 пикселей, симметрично слева-направо: шумный серый фон + глаза и рот одного из нескольких видов. */
function pixelFace(seed: number): string[][] {
  const r = rng(seed)
  const grays = ['#d4d4d8', '#bdbdc2', '#a1a1aa', '#c8c8cc']
  const grid: string[][] = Array.from({ length: 8 }, () => Array(8).fill(''))
  for (let y = 0; y < 8; y++)
    for (let x = 0; x < 4; x++) {
      const c = grays[Math.floor(r() * grays.length)]
      grid[y][x] = c
      grid[y][7 - x] = c
    }
  const dark = '#27272a'
  const eyeY = 2 + Math.floor(r() * 2)
  const eyeW = r() < 0.5 ? 1 : 2
  const eyeX = eyeW === 2 ? 1 : 1 + Math.floor(r() * 2)
  for (let dx = 0; dx < eyeW; dx++)
    for (let dy = 0; dy < (r() < 0.6 ? 2 : 1); dy++) {
      grid[eyeY + dy][eyeX + dx] = dark
      grid[eyeY + dy][7 - eyeX - dx] = dark
    }
  const mouth = Math.floor(r() * 3)
  const my = 5 + (r() < 0.5 ? 0 : 1)
  if (mouth === 0) for (let x = 2; x <= 5; x++) grid[my][x] = dark // прямая
  if (mouth === 1) {
    grid[my][3] = grid[my][4] = dark // «о»
    if (my < 7) grid[my + 1][3] = grid[my + 1][4] = dark
  }
  if (mouth === 2) {
    grid[my][2] = grid[my][5] = dark // улыбка
    if (my < 7) for (let x = 3; x <= 4; x++) grid[my + 1][x] = dark
  }
  return grid
}

export function AvatarImage({ size = 40 }: { size?: number }) {
  const [data, setData] = useState<AvatarData>(load)
  useEffect(() => {
    const f = () => setData(load())
    listeners.add(f)
    return () => {
      listeners.delete(f)
    }
  }, [])
  if (data.kind === 'photo')
    return (
      <img
        src={data.dataUrl}
        alt=""
        width={size}
        height={size}
        className="rounded-xl object-cover"
        style={{ width: size, height: size }}
      />
    )
  const grid = pixelFace(data.seed)
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 8 8"
      shapeRendering="crispEdges"
      className="rounded-xl"
      aria-hidden="true"
    >
      {grid.flatMap((row, y) =>
        row.map((c, x) => <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" fill={c} />),
      )}
    </svg>
  )
}

/** Сжать фото до 128×128 (квадрат по центру), чтобы влезло в хранилище браузера. */
function shrink(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const side = Math.min(img.width, img.height)
      const canvas = document.createElement('canvas')
      canvas.width = canvas.height = 128
      canvas
        .getContext('2d')
        ?.drawImage(img, (img.width - side) / 2, (img.height - side) / 2, side, side, 0, 0, 128, 128)
      URL.revokeObjectURL(img.src)
      resolve(canvas.toDataURL('image/jpeg', 0.85))
    }
    img.onerror = reject
    img.src = URL.createObjectURL(file)
  })
}

/** Аватарка, по нажатию — меню: другая мордочка / своё фото. */
export function AvatarButton({ size = 44 }: { size?: number }) {
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const file = useRef<HTMLInputElement>(null)
  const box = useRef<HTMLDivElement>(null)

  // Закрыть меню по клику мимо или по Esc.
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  async function onFile(f: File | undefined) {
    if (!f) return
    if (!f.type.startsWith('image/')) return setError('Нужна картинка')
    try {
      save({ kind: 'photo', dataUrl: await shrink(f) })
      setOpen(false)
    } catch {
      setError('Не получилось открыть фото')
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        title="Сменить аватарку"
        aria-label="Сменить аватарку"
        className="block"
      >
        <AvatarImage size={size} />
      </button>
      {open && (
        <div className="card absolute bottom-full left-0 z-30 mb-2 w-60 space-y-1 p-2 text-sm">
          <button
            onClick={() => save({ kind: 'pixel', seed: Math.floor(Math.random() * 1_000_000_000) })}
            className="w-full rounded-lg px-3 py-2 text-left hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            🎲 Другая фигурка
          </button>
          <button
            onClick={() => file.current?.click()}
            className="w-full rounded-lg px-3 py-2 text-left hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            🖼 Поставить своё фото
          </button>
          <p className="px-3 pb-1 text-xs text-slate-500">
            Фото остаётся только на этом устройстве и никуда не отправляется.
          </p>
          {error && <p className="px-3 text-xs text-red-600">{error}</p>}
          <input ref={file} type="file" accept="image/*" hidden onChange={(e) => void onFile(e.target.files?.[0])} />
        </div>
      )}
    </div>
  )
}
