import { cn } from "@/lib/utils";
import { AIMessage, Message } from "@langchain/langgraph-sdk";
import { ChevronRight, Database, LoaderCircle, PencilLine, Trash2 } from "lucide-react";
import { useState } from "react";
import { ANSWER_TOOL, ArenaMode, isWriteCall } from "./config";

type ToolCall = NonNullable<AIMessage["tool_calls"]>[number];

function argText(tc: ToolCall) {
  const a = tc.args as Record<string, any>;
  if (a.query) return String(a.query).replace(/\s+/g, " ").trim();
  return Object.entries(a)
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(", ");
}

function Step({
  tc,
  result,
  mode,
  pending,
}: {
  tc: ToolCall;
  result?: Message;
  mode: ArenaMode;
  pending: boolean;
}) {
  const write = isWriteCall(tc.name, tc.args as Record<string, any>);
  const out = result ? String(typeof result.content === "string" ? result.content : JSON.stringify(result.content)) : "";
  const rejected = out.startsWith("User rejected");
  const [open, setOpen] = useState(write);

  let tag: [string, string] | null = null;
  if (write && result) {
    if (rejected) tag = ["rejected by human", "bg-slate-200 text-slate-700"];
    else if (mode === "guarded") tag = ["human-approved", "bg-amber-200 text-amber-900"];
    else tag = ["no approval", "bg-rose-600 text-white"];
  } else if (write && !result && mode === "guarded") {
    tag = ["awaiting approval", "bg-amber-100 text-amber-800"];
  }

  const Icon = tc.name === "delete_student_records" ? Trash2 : tc.name === "update_student_records" ? PencilLine : Database;

  return (
    <div
      className={cn(
        "rounded-xl border bg-white text-sm",
        write && result && !rejected && mode === "unguarded" && "border-rose-300 bg-rose-50/60",
        write && result && !rejected && mode === "guarded" && "border-amber-300 bg-amber-50/60",
        (!write || !result || rejected) && "border-slate-200",
      )}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-left"
      >
        <ChevronRight className={cn("size-3.5 shrink-0 text-slate-400 transition-transform", open && "rotate-90")} />
        <Icon className="size-4 shrink-0 text-slate-500" />
        <span className="font-medium text-slate-800">{tc.name}</span>
        {tag && <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", tag[1])}>{tag[0]}</span>}
        <span className="truncate font-mono text-xs text-slate-500">{argText(tc)}</span>
        {!result && pending && <LoaderCircle className="ml-auto size-4 shrink-0 animate-spin text-slate-400" />}
      </button>
      {open && (
        <div className="border-t border-slate-100 px-3 py-2">
          <pre className="font-mono text-xs whitespace-pre-wrap text-slate-700">{argText(tc)}</pre>
          {result && (
            <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-slate-50 p-2 font-mono text-[11px] whitespace-pre-wrap text-slate-600">
              → {out.slice(0, 1200)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export function ToolSteps({
  toolCalls,
  messages,
  mode,
  isLoading,
}: {
  toolCalls: ToolCall[];
  messages: Message[];
  mode: ArenaMode;
  isLoading: boolean;
}) {
  const calls = toolCalls.filter((tc) => tc.name !== ANSWER_TOOL);
  if (!calls.length) return null;
  const results = new Map(
    messages.filter((m) => m.type === "tool").map((m) => [(m as any).tool_call_id, m]),
  );
  return (
    <div className="flex flex-col gap-1.5">
      {calls.map((tc, i) => (
        <Step key={tc.id ?? i} tc={tc} result={results.get(tc.id)} mode={mode} pending={isLoading} />
      ))}
    </div>
  );
}
