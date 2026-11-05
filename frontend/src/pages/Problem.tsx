import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, type CheckResult, type ProblemDetail } from "../api";
import { MathText } from "../components/MathText";
import { SUBJECT_NAMES, pluralPoints } from "../lib/text";
import { usePoints } from "../points";
import { problemLocked } from "../olympiadRun";

const HINT_NAMES = ["Намёк", "Ключевая идея", "План решения"];
const HINT_FACTORS = [1, 0.8, 0.6, 0.4];

export function ProblemPage() {
  const { id = "" } = useParams();
  const locked = problemLocked(id);
  const [params, setParams] = useSearchParams();
  const seed = params.get("v") ? Number(params.get("v")) : null;

  const [p, setP] = useState<ProblemDetail | null>(null);
  const [error, setError] = useState("");
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<CheckResult | null>(null);
  const [busy, setBusy] = useState<
    "" | "check" | "hint" | "solution" | "variant"
  >("");
  const [confirmSolution, setConfirmSolution] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);
  const { setPoints } = usePoints();
  const inputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    setError("");
    api
      .problem(id, seed)
      .then(setP)
      .catch((e) => setError(e.message));
  }, [id, seed]);

  useEffect(() => {
    load();
    setResult(null);
    setAnswer("");
    setShowOriginal(false);
  }, [load]);

  if (error) return <ErrorBox text={error} />;
  if (!p) return <div className="card h-80 animate-pulse" />;

  const solved = p.progress.solved;

  async function check(e: FormEvent) {
    e.preventDefault();
    if (!answer.trim()) return;
    setBusy("check");
    try {
      const r = await api.check(id, answer, seed);
      setResult(r);
      setPoints(r.total_points);
      if (r.correct) load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setBusy("");
    }
  }

  async function openHint() {
    if (!p) return;
    setBusy("hint");
    try {
      await api.hint(id, p.hints_opened.length + 1);
      load();
    } catch (err) {
      setResult({
        status: "unparsable",
        correct: false,
        message: (err as Error).message,
      } as CheckResult);
    } finally {
      setBusy("");
    }
  }

  async function openSolution() {
    setBusy("solution");
    setConfirmSolution(false);
    try {
      await api.solution(id);
      load();
    } catch (err) {
      setResult({
        status: "unparsable",
        correct: false,
        message: (err as Error).message,
      } as CheckResult);
    } finally {
      setBusy("");
    }
  }

  async function newVariant() {
    setBusy("variant");
    try {
      const v = await api.variant(id);
      setParams({ v: String(v.seed) });
      setTimeout(() => inputRef.current?.focus(), 50);
    } catch (err) {
      setResult({
        status: "unparsable",
        correct: false,
        message: (err as Error).message,
      } as CheckResult);
    } finally {
      setBusy("");
    }
  }

  const nextHintReward =
    Math.round(
      (p.points * HINT_FACTORS[Math.min(p.hints_opened.length + 1, 3)]) / 5,
    ) * 5;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="min-w-0 space-y-6">
        <Link
          to="/problems"
          className="text-sm font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
        >
          ← Все задачи
        </Link>

        <article className="card p-6 sm:p-8">
          <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-500">
            <span>{SUBJECT_NAMES[p.subject]}</span>·<span>{p.topic}</span>
            <span className="chip ml-auto bg-gold-400/15 text-base text-amber-700 dark:text-gold-400">
              ★ {p.points}
            </span>
          </div>
          <h1 className="mt-2 text-2xl font-extrabold tracking-tight sm:text-3xl">
            {p.title}
          </h1>

          {seed !== null && (
            <VariantBanner
              p={p}
              showOriginal={showOriginal}
              toggle={() => setShowOriginal((s) => !s)}
            />
          )}

          <MathText text={p.statement} className="statement mt-5 text-lg" />

          {showOriginal && p.original_statement && (
            <div className="mt-4 rounded-xl border border-dashed border-slate-300 p-4 text-slate-500 dark:border-slate-700">
              <div className="mb-1 text-xs font-bold uppercase tracking-wide">
                Оригинал
              </div>
              <MathText text={p.original_statement} />
            </div>
          )}

          <div className="mt-6 text-sm text-slate-500">
            {p.source.label}
            {p.source.url && (
              <>
                {" · "}
                <a
                  href={p.source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="underline"
                >
                  оригинал
                </a>
              </>
            )}
          </div>
        </article>

        <form onSubmit={check} className="card p-6">
          <label htmlFor="answer" className="font-bold">
            Твой ответ
          </label>
          <p className="mt-1 text-sm text-slate-500">
            {p.needs_unit
              ? "Пиши с единицами измерения: 12 м/с, 4,5 кДж, 300 мА. Тренажёр сам переведёт и проверит размерность."
              : "Число или выражение: 42, 3/4, 2√3, 1,5."}
          </p>
          <div className="mt-3 flex gap-2">
            <input
              id="answer"
              ref={inputRef}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              autoComplete="off"
              placeholder={p.needs_unit ? "например, 4 с" : "например, 42"}
              className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-white px-4 py-3 text-lg outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 dark:border-slate-700 dark:bg-slate-950"
            />
            <button
              className="btn-primary px-6"
              disabled={busy === "check" || !answer.trim()}
            >
              {busy === "check" ? "…" : "Проверить"}
            </button>
          </div>
          {result && <ResultBox r={result} />}
        </form>

        {p.solution && (
          <section className="card animate-fade-up p-6">
            <h2 className="mb-3 text-lg font-bold">Разбор</h2>
            <MathText text={p.solution} />
            {p.can_clone && !solved && (
              <div className="mt-5 rounded-xl bg-brand-50 p-4 text-sm dark:bg-brand-900/30">
                Разобрался? Реши <b>новый вариант</b> этой задачи с другими
                числами — и получи половину баллов.
                <button
                  onClick={newVariant}
                  className="btn-primary mt-3 w-full"
                  disabled={busy === "variant"}
                >
                  Новый вариант →
                </button>
              </div>
            )}
          </section>
        )}
      </div>

      <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
        <div className="card p-5">
          {solved ? (
            <div>
              <div className="text-sm font-semibold text-emerald-600">
                Задача решена ✓
              </div>
              <div className="mt-1 text-2xl font-extrabold">
                +{p.progress.earned} {pluralPoints(p.progress.earned)}
              </div>
              {p.solve_rate !== null && (
                <div className="mt-1 text-sm text-slate-500">
                  Эту задачу решили {p.solve_rate}% учеников
                </div>
              )}
            </div>
          ) : (
            <div>
              <div className="text-sm font-semibold text-slate-500">
                Сейчас можно получить
              </div>
              <div className="mt-1 text-3xl font-extrabold text-amber-600 dark:text-gold-400">
                ★ {p.potential}
              </div>
            </div>
          )}
        </div>

        {locked ? (
          <div className="card p-5 text-sm">
            <h2 className="font-bold">⏱ Идёт олимпиада</h2>
            <p className="mt-1 text-slate-500">
              Подсказки, разбор и помощник откроются после окончания времени —
              как на настоящей олимпиаде.
            </p>
          </div>
        ) : (
          <div className="card p-5">
            <h2 className="font-bold">Подсказки</h2>
            <p className="mt-1 text-sm text-slate-500">
              Открывай по одной. Каждая немного снижает награду. Подсказки
              составляет ИИ.
            </p>
            <ol className="mt-4 space-y-3">
              {p.hints_opened.map((h, i) => (
                <li
                  key={i}
                  className="animate-fade-up rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-800/60"
                >
                  <div className="mb-1 text-xs font-bold uppercase tracking-wide text-brand-600 dark:text-brand-300">
                    {i + 1}. {HINT_NAMES[i] ?? "Подсказка"}
                  </div>
                  <MathText text={h} />
                </li>
              ))}
            </ol>
            <Link to={`/?problem=${p.id}`} className="btn-ghost mt-3 w-full">
              Спросить ИИ-помощника об этой задаче
            </Link>
            {p.hints_opened.length < p.hints_total && !p.solution && (
              <button
                onClick={openHint}
                disabled={busy === "hint"}
                className="btn-ghost mt-3 w-full"
              >
                {busy === "hint"
                  ? "Наставник думает…"
                  : `${HINT_NAMES[p.hints_opened.length]}${solved ? "" : ` · станет ★ ${nextHintReward}`}`}
              </button>
            )}

            {!p.solution && (
              <div className="mt-4 border-t border-slate-200 pt-4 dark:border-slate-800">
                {confirmSolution ? (
                  <div className="text-sm">
                    <p>
                      После разбора за эту задачу баллов не будет.
                      {p.can_clone &&
                        " Но можно будет решить новый вариант за половину баллов."}
                    </p>
                    <div className="mt-3 flex gap-2">
                      <button
                        onClick={openSolution}
                        className="btn-primary flex-1"
                        disabled={busy === "solution"}
                      >
                        Показать
                      </button>
                      <button
                        onClick={() => setConfirmSolution(false)}
                        className="btn-ghost flex-1"
                      >
                        Ещё подумаю
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() =>
                      solved ? openSolution() : setConfirmSolution(true)
                    }
                    className="w-full text-sm font-semibold text-slate-500 underline-offset-4 hover:underline"
                  >
                    Показать полный разбор
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {p.can_clone && (
          <div className="card p-5">
            <h2 className="font-bold">Тренировка на вариантах</h2>
            <p className="mt-1 text-sm text-slate-500">
              Та же идея, другие числа. Каждый вариант проверен: решатель
              воспроизводит официальный ответ.
            </p>
            <button
              onClick={newVariant}
              disabled={busy === "variant"}
              className="btn-ghost mt-3 w-full"
            >
              {busy === "variant"
                ? "Подбираю и проверяю…"
                : "∞ Сделать новый вариант"}
            </button>
            {seed !== null && (
              <button
                onClick={() => setParams({})}
                className="mt-2 w-full text-sm font-semibold text-slate-500 hover:underline"
              >
                Вернуться к оригиналу
              </button>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}

function VariantBanner({
  p,
  showOriginal,
  toggle,
}: {
  p: ProblemDetail;
  showOriginal: boolean;
  toggle: () => void;
}) {
  const v = p.verification;
  return (
    <div className="mt-4 flex flex-wrap items-center gap-2 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200">
      <span className="font-bold">✓ Проверенный вариант</span>
      <span className="text-emerald-700/80 dark:text-emerald-300/80">
        решатель воспроизводит официальный ответ
        {v?.cross_checked && ", ответ сверен с независимой ИИ-моделью"}
      </span>
      <button
        onClick={toggle}
        className="ml-auto font-semibold underline-offset-4 hover:underline"
      >
        {showOriginal ? "Скрыть оригинал" : "Показать оригинал"}
      </button>
    </div>
  );
}

function ResultBox({ r }: { r: CheckResult }) {
  const styles: Record<CheckResult["status"], string> = {
    correct:
      "bg-emerald-50 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200",
    unit_missing:
      "bg-emerald-50 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200",
    wrong: "bg-rose-50 text-rose-800 dark:bg-rose-900/30 dark:text-rose-200",
    wrong_dimension:
      "bg-amber-50 text-amber-900 dark:bg-amber-900/30 dark:text-amber-200",
    unparsable:
      "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  };
  const icon = {
    correct: "🎉",
    unit_missing: "✓",
    wrong: "✗",
    wrong_dimension: "⚖",
    unparsable: "?",
  }[r.status];
  return (
    <div
      role="status"
      className={`mt-4 rounded-xl p-4 ${styles[r.status]} ${r.correct ? "animate-pop" : "animate-fade-up"}`}
    >
      <div className="flex items-start gap-3">
        <span className="text-xl leading-none">{icon}</span>
        <div>
          <div className="font-semibold">{r.message}</div>
          {r.first_solve && r.earned > 0 && (
            <div className="mt-1 text-lg font-extrabold">
              +{r.earned} {pluralPoints(r.earned)}
            </div>
          )}
          {r.first_solve && r.earned === 0 && (
            <div className="mt-1 text-sm">
              Баллы не начислены — был открыт разбор. Попробуй новый вариант!
            </div>
          )}
          {r.already_solved && (
            <div className="mt-1 text-sm">
              Задача уже решена — это была тренировка.
            </div>
          )}
          {r.solve_rate !== null && r.first_solve && (
            <div className="mt-1 text-sm opacity-80">
              Эту задачу решили {r.solve_rate}% учеников.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ErrorBox({ text }: { text: string }) {
  return (
    <div className="card p-6">
      <p className="text-red-600">{text}</p>
      <Link to="/problems" className="btn-ghost mt-4">
        ← К задачам
      </Link>
    </div>
  );
}
