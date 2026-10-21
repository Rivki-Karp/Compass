import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import type { ComparisonView } from "../api/types";
import { originText, type PlacedSource } from "../lib/numberSources";
import { Amount } from "./Amount";
import { BidiText } from "./BidiText";
import { Icon } from "./icons";
import { SourceChip } from "./SourceChip";

/**
 * "מאיפה המספר הזה?": a verified number in a reply is a real button; it opens a popover (a
 * bottom sheet below 700px) with the number, what it is, its source chip, how it was produced
 * and, for a comparison's difference, the lines it adds up from. Every word is the server's
 * (the `number_sources` of the reply); the lines are the stored comparison view's own
 * `breakdown`, the data the waterfall draws. Nothing is computed or looked up here.
 *
 * One popover at a time (the provider owns the only one). Esc, an outside click or the close
 * button close it and focus goes back to the number.
 */

const SHEET_QUERY = "(max-width: 699px)";
const WIDTH = 320;
const GAP = 8;

interface Opened {
  source: PlacedSource;
  shown: string;
  anchor: HTMLElement;
}

interface Api {
  current: Opened | null;
  toggle: (opened: Opened) => void;
}

const NumberSourceContext = createContext<Api | null>(null);

export function NumberSourceProvider({
  views,
  children,
}: {
  views: Record<string, ComparisonView>;
  children: ReactNode;
}) {
  const [current, setCurrent] = useState<Opened | null>(null);
  const currentRef = useRef<Opened | null>(null);
  currentRef.current = current;

  const close = useCallback((restoreFocus = true) => {
    const was = currentRef.current;
    setCurrent(null);
    if (restoreFocus) was?.anchor.focus({ preventScroll: true });
  }, []);

  const toggle = useCallback(
    (opened: Opened) => {
      if (currentRef.current?.anchor === opened.anchor) close();
      else setCurrent(opened);
    },
    [close],
  );

  return (
    <NumberSourceContext.Provider value={{ current, toggle }}>
      {children}
      {current
        ? createPortal(<Popover opened={current} views={views} onClose={close} />, document.body)
        : null}
    </NumberSourceContext.Provider>
  );
}

/** A verified number: a dotted-underline button. Outside a provider it is just the text. */
export function SourceNumber({ source, shown }: { source: PlacedSource; shown: string }) {
  const api = useContext(NumberSourceContext);
  const ref = useRef<HTMLButtonElement>(null);
  if (!api) return <>{shown}</>;
  const open = api.current !== null && api.current.anchor === ref.current;
  return (
    <button
      ref={ref}
      type="button"
      data-testid="number-source"
      aria-label={`מאיפה המספר ${shown}?`}
      aria-haspopup="dialog"
      aria-expanded={open}
      onClick={(event) => api.toggle({ source, shown, anchor: event.currentTarget })}
      className="cursor-pointer rounded-[3px] border-0 bg-transparent p-0 font-[inherit] text-[inherit] underline decoration-dotted decoration-1 underline-offset-4 hover:bg-provenance-bg"
    >
      {shown}
    </button>
  );
}

function useSheet(): boolean {
  const [sheet, setSheet] = useState(() => window.matchMedia?.(SHEET_QUERY).matches ?? false);
  useEffect(() => {
    const query = window.matchMedia?.(SHEET_QUERY);
    if (!query) return;
    const update = () => setSheet(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return sheet;
}

function Popover({
  opened,
  views,
  onClose,
}: {
  opened: Opened;
  views: Record<string, ComparisonView>;
  onClose: (restoreFocus?: boolean) => void;
}) {
  const { source, shown, anchor } = opened;
  const sheet = useSheet();
  const box = useRef<HTMLDivElement>(null);
  const [style, setStyle] = useState<CSSProperties>({ visibility: "hidden" });

  useLayoutEffect(() => {
    if (sheet) {
      setStyle({});
      return;
    }
    const rect = anchor.getBoundingClientRect();
    const room = window.innerWidth - WIDTH - GAP;
    const left = Math.max(GAP, Math.min(room, rect.left + rect.width / 2 - WIDTH / 2));
    const height = box.current?.offsetHeight ?? 0;
    const below = rect.bottom + GAP;
    const top =
      below + height > window.innerHeight ? Math.max(GAP, rect.top - GAP - height) : below;
    setStyle({ top, left, width: WIDTH });
  }, [sheet, anchor, source]);

  useEffect(() => {
    box.current?.focus({ preventScroll: true });
  }, [source]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    const onPointer = (event: PointerEvent) => {
      const target = event.target as Node;
      if (box.current?.contains(target) || anchor.contains(target)) return;
      // A click on a control keeps that control's focus; a click on plain content sends focus
      // back to the number, after the browser has moved it to the page.
      const control =
        target instanceof Element && target.closest("a, button, input, textarea, select");
      onClose(false);
      if (!control) setTimeout(() => anchor.focus({ preventScroll: true }), 0);
    };
    const onScroll = (event: Event) => {
      if (!box.current?.contains(event.target as Node)) onClose(false);
    };
    const onResize = () => onClose(false);
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", onResize);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onResize);
    };
  }, [anchor, onClose]);

  const percent = shown.trim().endsWith("%");
  const ref = source.ref;
  const view =
    ref.comparison_seq !== undefined
      ? views[String(ref.comparison_seq)]
      : ref.option_set_seq !== undefined
        ? views[`${ref.option_set_seq}:${ref.alternative ?? ""}`]
        : undefined;
  const lines = ref.role === "diff" && view ? view.breakdown : [];

  return (
    <>
      {sheet ? <div aria-hidden="true" className="fixed inset-0 z-40 bg-ink/30" /> : null}
      <div
        ref={box}
        role="dialog"
        aria-label={`מקור המספר ${shown}`}
        tabIndex={-1}
        data-testid="number-popover"
        data-sheet={sheet ? "true" : "false"}
        style={style}
        className={
          sheet
            ? "fixed inset-x-0 bottom-0 z-50 max-h-[75dvh] overflow-y-auto rounded-t-[18px] border-t border-line bg-surface px-4 pt-4 pb-6 text-ink shadow-[0_-8px_30px_rgba(8,35,80,0.18)] outline-none"
            : "fixed z-50 rounded-tile border border-line bg-surface p-4 text-ink shadow-[0_8px_30px_rgba(8,35,80,0.18)] outline-none"
        }
      >
        <div className="flex items-start justify-between gap-3">
          <p className="text-[16px] font-semibold text-navy">
            <bdi>{shown}</bdi>
            {percent ? "" : " ₪"}
            {source.what ? ` · ${source.what}` : ""}
          </p>
          <button
            type="button"
            aria-label="סגירה"
            onClick={() => onClose()}
            className="-m-2 flex min-h-11 min-w-11 items-center justify-center rounded-control text-muted hover:text-navy"
          >
            <Icon name="x" size={18} />
          </button>
        </div>
        <div className="mt-2.5">
          <SourceChip source={source.chip} label={source.label} />
        </div>
        <p data-testid="number-origin" className="mt-2.5 text-[14px] text-muted">
          <BidiText text={originText(source.origin.label, source.origin.at)} />
        </p>
        {lines.length ? (
          <ul aria-label="מרכיבי ההפרש" className="mt-3 border-t border-line-soft">
            {lines.map((line) => {
              const chips = [
                ...new Set(
                  line.inputs
                    .map((id) => view?.inputs.find((input) => input.id === id)?.source)
                    .filter((chip) => chip !== undefined),
                ),
              ];
              return (
                <li
                  key={line.key}
                  data-line={line.key}
                  className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-line-soft py-2 text-[14px]"
                >
                  <span className="min-w-0 flex-1">
                    <BidiText text={line.label} />
                  </span>
                  <Amount
                    value={line.net_effect}
                    signed
                    currency
                    className={`font-semibold ${line.net_effect < 0 ? "text-down" : "text-up"}`}
                  />
                  <span className="flex basis-full flex-wrap gap-1.5">
                    {chips.map((chip) => (
                      <SourceChip key={chip} source={chip} />
                    ))}
                  </span>
                  {line.rules.length ? (
                    <span className="basis-full text-[12px] text-muted">
                      <BidiText text={line.rules.map((rule) => rule.label).join(" · ")} />
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>
    </>
  );
}
