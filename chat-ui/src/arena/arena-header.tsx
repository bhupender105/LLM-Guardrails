import { cn } from "@/lib/utils";
import { useStreamContext } from "@/providers/Stream";
import { Database, PanelLeft, RotateCcw, SquarePen } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { ArenaMode } from "./config";

type Stats = Record<string, { rows: number | null; baseline: number }>;

export function useDbStats(mode: ArenaMode) {
  const { apiUrl, isLoading } = useStreamContext();
  const [stats, setStats] = useState<Stats | null>(null);
  const refresh = useCallback(
    () => fetch(`${apiUrl}/arena/stats`).then((r) => r.json()).then(setStats).catch(() => {}),
    [apiUrl],
  );
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, isLoading ? 1500 : 5000);
    return () => clearInterval(t);
  }, [refresh, isLoading]);
  const reset = async () => {
    const r = await fetch(`${apiUrl}/arena/reset`, { method: "POST" });
    setStats(await r.json());
    toast.success("Both databases restored to 800 students");
  };
  return { db: stats?.[mode], reset };
}

export function ModeBadge({ mode }: { mode: ArenaMode }) {
  return mode === "guarded" ? (
    <span className="flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-sm font-semibold text-emerald-700">
      🛡️ Guarded agent
    </span>
  ) : (
    <span className="flex items-center gap-1.5 rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-sm font-semibold text-rose-700">
      🔓 Unguarded agent
    </span>
  );
}

export function ArenaHeader({
  mode,
  onNewChat,
  sidebarOpen,
  onToggleSidebar,
}: {
  mode: ArenaMode;
  onNewChat: () => void;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}) {
  const { db, reset } = useDbStats(mode);
  const delta = db?.rows != null ? db.rows - db.baseline : 0;
  return (
    <div
      className={cn(
        "flex items-center gap-3 border-b px-4 py-2.5",
        mode === "guarded" ? "border-t-4 border-t-emerald-500" : "border-t-4 border-t-rose-500",
      )}
    >
      {!sidebarOpen && (
        <>
          <button
            onClick={onToggleSidebar}
            title="Open sidebar"
            className="cursor-pointer rounded-lg p-1.5 text-slate-500 hover:bg-slate-100"
          >
            <PanelLeft className="size-5" />
          </button>
          <button onClick={onNewChat} className="flex cursor-pointer items-center gap-2">
            <span className="text-lg font-semibold tracking-tight text-slate-900">Guardrails Arena</span>
          </button>
        </>
      )}
      <ModeBadge mode={mode} />
      <div className="ml-auto flex items-center gap-2">
        {db && (
          <span
            className={cn(
              "flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-semibold",
              delta < 0 || db.rows == null
                ? "border-rose-200 bg-rose-50 text-rose-700"
                : "border-slate-200 bg-slate-50 text-slate-700",
            )}
          >
            <Database className="size-3.5" />
            {db.rows == null ? "table dropped!" : `${db.rows} students`}
            {delta !== 0 && db.rows != null && <span>({delta})</span>}
          </span>
        )}
        <button
          onClick={reset}
          title="Reset both databases"
          className="flex cursor-pointer items-center gap-1 rounded-lg px-2 py-1.5 text-sm text-slate-500 hover:bg-slate-100 hover:text-slate-900"
        >
          <RotateCcw className="size-4" /> Reset DB
        </button>
        <button
          onClick={onNewChat}
          title="New chat"
          className="flex cursor-pointer items-center gap-1 rounded-lg px-2 py-1.5 text-sm text-slate-500 hover:bg-slate-100 hover:text-slate-900"
        >
          <SquarePen className="size-4" /> New chat
        </button>
      </div>
    </div>
  );
}
