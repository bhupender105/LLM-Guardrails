import { cn } from "@/lib/utils";
import { useStreamContext } from "@/providers/Stream";
import { motion } from "framer-motion";
import { Check, PencilLine, ShieldAlert, X } from "lucide-react";
import { useState } from "react";

type ActionRequest = {
  name: string;
  args: Record<string, any>;
  impact?: { affected?: number | string; total?: number };
};
type ReviewConfig = { action_name: string; allowed_decisions: string[] };

function sqlPreview(name: string, args: Record<string, any>) {
  if (name === "delete_student_records")
    return `DELETE FROM students\nWHERE ${args.where_clause ?? "?"};`;
  if (name === "update_student_records")
    return `UPDATE students\nSET ${args.set_clause ?? "?"}\nWHERE ${args.where_clause ?? "?"};`;
  return JSON.stringify(args, null, 2);
}

/** Claude-desktop-style permission prompt for the guarded agent's write tools. */
export function ApprovalCard({ value }: { value: { action_requests: ActionRequest[]; review_configs: ReviewConfig[] } }) {
  const stream = useStreamContext();
  const req = value.action_requests[0];
  const allowed = value.review_configs.find((c) => c.action_name === req.name)?.allowed_decisions ?? ["approve", "reject"];
  const [editing, setEditing] = useState(false);
  const [args, setArgs] = useState<Record<string, any>>(req.args);
  const [reason, setReason] = useState("");
  const [sent, setSent] = useState(false);
  const isDelete = req.name === "delete_student_records";
  const affected = req.impact?.affected;
  const total = req.impact?.total;

  const resume = (decision: Record<string, any>) => {
    setSent(true);
    stream.submit({}, { command: { resume: { decisions: [decision] } } });
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      className="overflow-hidden rounded-2xl border border-amber-300 bg-white shadow-lg shadow-amber-100"
    >
      <div className="flex items-center gap-3 border-b border-amber-200 bg-amber-50 px-5 py-3">
        <ShieldAlert className="size-5 text-amber-600" />
        <div className="flex-1">
          <div className="font-semibold text-slate-900">Allow the agent to {isDelete ? "delete" : "update"} student records?</div>
          <div className="text-xs text-slate-500">Human-in-the-loop · the agent is paused until you decide</div>
        </div>
        <span
          className={cn(
            "rounded-full px-2.5 py-1 text-[11px] font-bold tracking-wide uppercase",
            isDelete ? "bg-rose-600 text-white" : "bg-amber-500 text-white",
          )}
        >
          {isDelete ? "Irreversible" : "Write"}
        </span>
      </div>

      <div className="flex flex-col gap-3 px-5 py-4">
        <div className="text-xs font-medium text-slate-500">
          Tool <code className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-800">{req.name}</code>
        </div>
        {editing ? (
          <div className="flex flex-col gap-2">
            {Object.entries(args).map(([k, v]) => (
              <label key={k} className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                {k}
                <input
                  value={String(v)}
                  onChange={(e) => setArgs((a) => ({ ...a, [k]: e.target.value }))}
                  className="rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm text-slate-900 outline-none focus:border-amber-500"
                />
              </label>
            ))}
          </div>
        ) : (
          <pre className="overflow-x-auto rounded-xl bg-slate-900 px-4 py-3 font-mono text-[13px] leading-relaxed text-slate-100">
            {sqlPreview(req.name, args)}
          </pre>
        )}
        {affected !== undefined && (
          <div className="flex items-center gap-2 rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-800">
            ⚠️ <span><b>{affected}</b>{total ? ` of ${total}` : ""} student records will be {isDelete ? "permanently deleted" : "modified"}.</span>
          </div>
        )}
        {allowed.includes("reject") && !editing && (
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Optional: tell the agent why (used if you reject)"
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400"
          />
        )}
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-slate-100 bg-slate-50/60 px-5 py-3">
        {allowed.includes("reject") && !editing && (
          <button
            disabled={sent}
            onClick={() => resume({ type: "reject", message: reason || "Rejected by a human reviewer." })}
            className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
          >
            <X className="size-4" /> Reject
          </button>
        )}
        {allowed.includes("edit") && (
          <button
            disabled={sent}
            onClick={() =>
              editing ? resume({ type: "edit", edited_action: { name: req.name, args } }) : setEditing(true)
            }
            className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-amber-400 bg-white px-4 py-2 text-sm font-medium text-amber-800 hover:bg-amber-50 disabled:opacity-50"
          >
            <PencilLine className="size-4" /> {editing ? "Approve edited action" : "Edit"}
          </button>
        )}
        {allowed.includes("approve") && !editing && (
          <button
            disabled={sent}
            onClick={() => resume({ type: "approve" })}
            className="flex cursor-pointer items-center gap-1.5 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            <Check className="size-4" /> Approve
          </button>
        )}
      </div>
    </motion.div>
  );
}
