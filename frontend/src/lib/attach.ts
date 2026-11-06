// Файлы для чата: фото задачи (уменьшаем на телефоне, чтобы не гонять 10-мегабайтные снимки) или PDF.

export interface Attached {
  name: string
  kind: 'image' | 'pdf'
  data: string // base64 без префикса data:
  preview?: string // data:-адрес уменьшенной картинки для показа
}

const MAX_SIDE = 1600
const MAX_PDF_BYTES = 4_000_000

function readAsDataUrl(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(String(r.result))
    r.onerror = () => reject(new Error('Не удалось прочитать файл'))
    r.readAsDataURL(file)
  })
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('Это не похоже на картинку'))
    img.src = url
  })
}

export async function toAttachment(file: File): Promise<Attached> {
  if (file.type === 'application/pdf') {
    if (file.size > MAX_PDF_BYTES) throw new Error('PDF слишком большой: до 4 МБ')
    const url = await readAsDataUrl(file)
    return { name: file.name, kind: 'pdf', data: url.split(',', 2)[1] }
  }
  if (!file.type.startsWith('image/')) throw new Error('Можно прикрепить фото или PDF')
  const img = await loadImage(await readAsDataUrl(file))
  const k = Math.min(1, MAX_SIDE / Math.max(img.width, img.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(img.width * k)
  canvas.height = Math.round(img.height * k)
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Не удалось обработать фото')
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
  const url = canvas.toDataURL('image/jpeg', 0.85)
  return { name: file.name, kind: 'image', data: url.split(',', 2)[1], preview: url }
}
