import { motion } from "framer-motion";
import { ArenaMode, SCENARIOS } from "./config";

export function Welcome({ mode, onPick }: { mode: ArenaMode; onPick: (prompt: string) => void }) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col items-center gap-6 pb-6">
      <div className="text-center">
        <div className="text-5xl">{mode === "guarded" ? "🛡️" : "🔓"}</div>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">
          {mode === "guarded" ? "Guarded agent" : "Unguarded agent"}
        </h1>
        <p className="mt-2 text-slate-500">
          {mode === "guarded"
            ? "Gemini + SQL tools, wrapped in a 5-layer Trust Layer with human approval."
            : "The same Gemini + SQL tools. No checks — it executes whatever it decides."}
        </p>
      </div>
      <div className="flex w-full flex-col gap-3">
        {SCENARIOS.map((g, gi) => (
          <div key={g.group} className="flex flex-wrap items-center gap-2">
            <span className="w-36 shrink-0 text-xs font-semibold tracking-wide text-slate-400 uppercase">{g.group}</span>
            {g.items.map(([label, prompt], i) => (
              <motion.button
                key={label}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: gi * 0.05 + i * 0.03 }}
                onClick={() => onPick(prompt)}
                title={prompt}
                className="cursor-pointer rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 shadow-xs transition hover:border-slate-400 hover:shadow-sm"
              >
                {label}
              </motion.button>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
