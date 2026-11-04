import katex from 'katex'
import { Fragment, useMemo } from 'react'
import { splitMath } from '../lib/text'

function renderMath(tex: string, display: boolean): string {
  try {
    return katex.renderToString(tex, { displayMode: display, throwOnError: false, strict: false })
  } catch {
    return tex
  }
}

/** Текст с формулами LaTeX ($...$), жирным (**...**) и абзацами. */
export function MathText({ text, className = '' }: { text: string; className?: string }) {
  const paragraphs = useMemo(() => text.split(/\n{2,}/), [text])
  return (
    <div className={`space-y-3 leading-relaxed ${className}`}>
      {paragraphs.map((para, i) => (
        <p key={i}>
          {splitMath(para).map((seg, j) => {
            if (seg.kind === 'math')
              return (
                <span key={j} dangerouslySetInnerHTML={{ __html: renderMath(seg.value, seg.display) }} />
              )
            if (seg.kind === 'bold') return <strong key={j}>{seg.value}</strong>
            return (
              <Fragment key={j}>
                {seg.value.split('\n').map((line, k, arr) => (
                  <Fragment key={k}>
                    {line}
                    {k < arr.length - 1 && <br />}
                  </Fragment>
                ))}
              </Fragment>
            )
          })}
        </p>
      ))}
    </div>
  )
}
