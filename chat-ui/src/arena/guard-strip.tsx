import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

type GuardEvent = {
  layer: string;
  status: string;
  detail?: string;
  ms?: number | null;
};

const LAYERS: [string, string, string][] = [
  ["keyword", "⚡", "Keyword"],
  ["jev_input", "🧠", "Jev input"],
  ["pii", "🔏", "PII"],
  ["hitl", "🧑‍⚖️", "Approval"],
  ["grounding", "🔍", "Grounding"],
];
const PRIORITY = ["blocked", "flagged", "pending", "redacted", "error", "info", "pass"];
const LABEL: Record<string, string> = {
  pass: "✓ pass",
  blocked: "✕ blocked",
  redacted: "✎ redacted",
  flagged: "⚠ flagged",
  pending: "⏸ waiting",
  info: "armed",
  error: "offline",
  skipped: "skipped",
  running: "checking…",
};
const TONE: Record<string, string> = {
  pass: "border-emerald-200 bg-emerald-50/70 text-emerald-700",
  redacted: "border-sky-200 bg-sky-50 text-sky-700",
  blocked: "border-rose-300 bg-rose-50 text-rose-700",
  flagged: "border-amber-300 bg-amber-50 text-amber-700",
  pending: "border-amber-300 bg-amber-50 text-amber-700",
  error: "border-slate-200 bg-slate-50 text-slate-500",
  info: "border-slate-200 bg-slate-50 text-slate-500",
  skipped: "border-dashed border-slate-200 bg-white text-slate-400",
  running: "border-slate-200 bg-white text-slate-400",
};

export function GuardStrip({
  events,
  stage,
  running,
  interrupted = false,
}: {
  events: GuardEvent[];
  stage: string;
  running: boolean;
  interrupted?: boolean;
}) {
  const byLayer: Record<string, GuardEvent[]> = {};
  events.forEach((e) => (byLayer[e.layer] ||= []).push(e));
  const blockedAt = LAYERS.findIndex(([l]) =>
    (byLayer[l] || []).some((e) => e.status === "blocked" && l !== "hitl"),
  );
  const finished = !interrupted && (stage === "done" || stage === "blocked" || !running);

  const chips = LAYERS.map(([layer, icon, name], i) => {
    const evs = byLayer[layer] || [];
    let status: string;
    let detail = "";
    if (blockedAt >= 0 && i > blockedAt) {
      status = "skipped";
      detail = "not reached";
    } else if (evs.length) {
      status = evs
        .map((e) => e.status)
        .sort((a, b) => PRIORITY.indexOf(a) - PRIORITY.indexOf(b))[0];
      detail = [...new Set(evs.map((e) => e.detail).filter(Boolean))].join(" · ");
      const ms = evs.reduce((s, e) => s + (e.ms || 0), 0);
      if (ms) detail += ` · ${ms} ms`;
    } else if (layer === "hitl" && interrupted) {
      status = "pending";
      detail = "waiting for a human";
    } else if (layer === "pii" && (finished || interrupted || stage !== "input")) {
      status = "pass";
      detail = "no PII found";
    } else if (layer === "grounding" && interrupted) {
      status = "skipped";
      detail = "runs after approval";
    } else if (layer === "hitl" && finished) {
      status = "pass";
      detail = "no write tools used";
    } else if (finished) {
      status = "skipped";
      detail = "—";
    } else {
      status = "running";
    }
    return { layer, icon, name, status, detail };
  });

  return (
    <div className="flex flex-wrap gap-2">
      {chips.map((c, i) => (
        <motion.div
          key={c.layer}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.04 }}
          title={c.detail}
          className={cn(
            "min-w-[118px] flex-1 rounded-xl border px-3 py-2 text-xs transition-colors",
            TONE[c.status] || TONE.info,
          )}
        >
          <div className="flex items-center gap-1.5 font-semibold text-slate-800">
            <span>{c.icon}</span>
            {c.name}
          </div>
          <div
            className={cn(
              "mt-1 font-medium",
              c.status === "running" && "animate-pulse",
            )}
          >
            {LABEL[c.status] || c.status}
          </div>
          {c.detail && (
            <div className="mt-0.5 line-clamp-2 text-[11px] text-slate-500">
              {c.detail}
            </div>
          )}
        </motion.div>
      ))}
    </div>
  );
}

export function GuardsOff() {
  return (
    <div className="flex flex-wrap gap-2">
      {["⚡ Input filter", "🔏 PII", "🧑‍⚖️ Approval", "🔍 Fact check"].map((n) => (
        <div
          key={n}
          className="min-w-[118px] flex-1 rounded-xl border border-dashed border-rose-200 bg-rose-50/40 px-3 py-2 text-xs"
        >
          <div className="font-semibold text-slate-700">{n}</div>
          <div className="mt-1 font-medium text-rose-500">off</div>
        </div>
      ))}
    </div>
  );
}
