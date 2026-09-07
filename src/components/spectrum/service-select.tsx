import { useEffect, useId, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

type Props = {
  options: readonly string[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  name?: string;
  className?: string;
};

export function ServiceSelect({
  options,
  value,
  onChange,
  placeholder = "Services",
  name,
  className,
}: Props) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [open]);

  const choose = (v: string) => {
    onChange(v);
    setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setOpen(false);
      return;
    }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        setActive(Math.max(0, options.indexOf(value)));
        return;
      }
      const dir = e.key === "ArrowDown" ? 1 : -1;
      setActive((i) => (i + dir + options.length) % options.length);
      return;
    }
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (open && active >= 0 && options[active] !== undefined) choose(options[active]);
      else setOpen((o) => !o);
    }
  };

  return (
    <div ref={rootRef} className={cn("relative", className)} onKeyDown={onKeyDown}>
      {name && <input type="hidden" name={name} value={value} />}
      <button
        type="button"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-haspopup="listbox"
        onClick={() => {
          setOpen((o) => !o);
          setActive(Math.max(0, options.indexOf(value)));
        }}
        className={cn(
          "flex w-full items-center justify-between rounded-xl border border-border bg-background/60 px-4 py-3 text-left text-sm transition-colors focus:border-transparent focus:outline-none focus:ring-2 focus:ring-violet",
          value ? "text-foreground" : "text-muted-foreground",
          open && "border-transparent ring-2 ring-violet",
        )}
      >
        <span className="truncate">{value || placeholder}</span>
        <ChevronDown
          className={cn(
            "ml-3 h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200",
            open && "rotate-180",
          )}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.16, ease: "easeOut" }}
            className="spectrum-border absolute left-0 right-0 top-[calc(100%+8px)] z-30 overflow-hidden rounded-2xl shadow-[0_24px_60px_-20px_rgba(0,0,0,0.7)]"
          >
            <div className="bg-[color-mix(in_oklab,var(--color-background)_82%,white_6%)] backdrop-blur-2xl backdrop-saturate-150">
              <div className="spectrum-hairline opacity-70" />
              <ul
                id={listId}
                role="listbox"
                className="glass-scrollbar max-h-72 overflow-y-auto p-1.5 pr-2"
                onMouseLeave={() => setActive(-1)}
              >
                {options.map((opt, i) => {
                  const selected = opt === value;
                  const highlighted = i === active;
                  return (
                    <li
                      key={opt}
                      role="option"
                      aria-selected={selected}
                      onMouseEnter={() => setActive(i)}
                      onClick={() => choose(opt)}
                      className={cn(
                        "relative flex cursor-pointer items-center justify-between rounded-lg px-3 py-2.5 text-sm transition-colors",
                        highlighted
                          ? "bg-[linear-gradient(90deg,color-mix(in_oklab,var(--sp-teal)_18%,transparent),color-mix(in_oklab,var(--sp-violet)_18%,transparent))] text-foreground"
                          : "text-muted-foreground",
                        selected && !highlighted && "text-foreground",
                      )}
                    >
                      <span>{opt}</span>
                      {selected && <Check className="h-4 w-4 text-violet" />}
                    </li>
                  );
                })}
              </ul>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
