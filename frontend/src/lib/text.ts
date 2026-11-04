// Разбор текста задачи на куски: обычный текст, жирный, формулы $...$ и $$...$$.

export type Segment =
  | { kind: 'text'; value: string }
  | { kind: 'bold'; value: string }
  | { kind: 'math'; value: string; display: boolean }

export function splitMath(src: string): Segment[] {
  const out: Segment[] = []
  const re = /\$\$([\s\S]+?)\$\$|\$([^$]+?)\$|\*\*([^*]+?)\*\*/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(src))) {
    if (m.index > last) out.push({ kind: 'text', value: src.slice(last, m.index) })
    if (m[1] !== undefined) out.push({ kind: 'math', value: m[1], display: true })
    else if (m[2] !== undefined) out.push({ kind: 'math', value: m[2], display: false })
    else out.push({ kind: 'bold', value: m[3] })
    last = re.lastIndex
  }
  if (last < src.length) out.push({ kind: 'text', value: src.slice(last) })
  return out
}

export const SUBJECT_NAMES: Record<string, string> = {
  math: 'Математика',
  physics: 'Физика',
}

export function pluralPoints(n: number): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return 'балл'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'балла'
  return 'баллов'
}
