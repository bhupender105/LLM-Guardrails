import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChevronDown } from "lucide-react";
import { piiKind } from "./config";

/** Inline **bold** / `code` for model-written one-liners (insights). */
function Inline({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) =>
        part.startsWith("**") && part.endsWith("**") ? (
          <b key={i} className="font-semibold text-slate-900">{part.slice(2, -2)}</b>
        ) : part.startsWith("`") && part.endsWith("`") ? (
          <code key={i} className="rounded bg-slate-200/70 px-1 text-[13px]">{part.slice(1, -1)}</code>
        ) : (
          part
        ),
      )}
    </>
  );
}

type Card = {
  title: string;
  emoji: string;
  status: "info" | "success" | "warning" | "danger";
  summary: string;
  kpis?: { label: string; value: string; icon?: string }[];
  chart?: {
    type: string;
    title: string;
    labels: string[];
    series: { name: string; values: number[] }[];
    x_label?: string;
    y_label?: string;
  } | null;
  table?: { columns: string[]; rows: string[][] } | null;
  insights?: string[];
  sql_used?: string;
};

const PALETTE = ["#2a78d6", "#14b8a6", "#f59e0b", "#8b5cf6", "#ef4444", "#64748b"];
const ACCENT: Record<string, string> = {
  info: "before:bg-sky-500",
  success: "before:bg-emerald-500",
  warning: "before:bg-amber-500",
  danger: "before:bg-rose-500",
};
const EYEBROW: Record<string, [string, string]> = {
  info: ["Insight", "text-sky-600"],
  success: ["Done", "text-emerald-600"],
  warning: ["Needs attention", "text-amber-600"],
  danger: ["Blocked", "text-rose-600"],
};

function ChartView({ chart }: { chart: NonNullable<Card["chart"]> }) {
  const data = chart.labels.map((label, i) => {
    const row: Record<string, string | number> = { label };
    chart.series.forEach((s) => (row[s.name] = s.values[i] ?? 0));
    return row;
  });
  const horizontal = chart.type === "horizontal_bar";
  const tilt = chart.labels.length > 6 || chart.labels.length * Math.max(...chart.labels.map((l) => l.length)) > 60;
  const axis = { fontSize: 11, fill: "#64748b" };

  let body: React.ReactElement;
  if (chart.type === "pie" || chart.type === "donut") {
    const s = chart.series[0];
    body = (
      <PieChart>
        <Pie
          data={chart.labels.map((l, i) => ({ name: l, value: s?.values[i] ?? 0 }))}
          dataKey="value"
          nameKey="name"
          innerRadius={chart.type === "donut" ? 55 : 0}
          outerRadius={95}
          paddingAngle={2}
        >
          {chart.labels.map((_, i) => (
            <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Pie>
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 12 }} />
      </PieChart>
    );
  } else if (chart.type === "line") {
    body = (
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="label" tick={axis} />
        <YAxis tick={axis} />
        <Tooltip />
        {chart.series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
        {chart.series.map((s, i) => (
          <Line key={s.name} dataKey={s.name} stroke={PALETTE[i]} strokeWidth={2.5} dot={{ r: 3 }} />
        ))}
      </LineChart>
    );
  } else {
    body = (
      <BarChart data={data} layout={horizontal ? "vertical" : "horizontal"}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        {horizontal ? (
          <>
            <XAxis type="number" tick={axis} />
            <YAxis type="category" dataKey="label" width={130} tick={axis} />
          </>
        ) : (
          <>
            <XAxis dataKey="label" tick={axis} interval={0} angle={tilt ? -25 : 0} textAnchor={tilt ? "end" : "middle"} height={tilt ? 80 : 30} />
            <YAxis tick={axis} />
          </>
        )}
        <Tooltip cursor={{ fill: "#f1f5f9" }} />
        {chart.series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
        {chart.series.map((s, i) => (
          <Bar key={s.name} dataKey={s.name} fill={PALETTE[i]} radius={horizontal ? [0, 6, 6, 0] : [6, 6, 0, 0]} />
        ))}
      </BarChart>
    );
  }

  return (
    <div className="rounded-xl border border-slate-100 bg-white p-3">
      <div className="mb-2 text-sm font-semibold text-slate-700">{chart.title}</div>
      <div style={{ height: horizontal ? Math.max(220, data.length * 32) : tilt ? 310 : 260 }}>
        <ResponsiveContainer width="100%" height="100%">
          {body}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Cellv({ value }: { value: string }) {
  const kind = piiKind(value);
  if (!kind) return <>{value}</>;
  return (
    <span
      className={cn(
        "rounded-md px-1.5 py-0.5 font-mono text-[12px]",
        kind === "leak" ? "bg-rose-100 text-rose-700" : "bg-emerald-100 text-emerald-700",
      )}
    >
      {value}
    </span>
  );
}

export function AnswerCardView({ card }: { card: Card }) {
  const [showSql, setShowSql] = useState(false);
  const [eyebrow, eyebrowTone] = EYEBROW[card.status] ?? EYEBROW.info;
  const hasBody =
    !!card.kpis?.length || !!card.chart || !!card.table || !!card.insights?.length || !!card.sql_used;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-5 shadow-sm",
        "before:absolute before:inset-x-0 before:top-0 before:h-1",
        ACCENT[card.status] ?? ACCENT.info,
      )}
    >
      <div className="flex items-center gap-3">
        <div className="flex size-11 items-center justify-center rounded-xl bg-slate-50 text-2xl">
          {card.emoji}
        </div>
        <div>
          <div className={cn("text-[11px] font-bold tracking-wider uppercase", eyebrowTone)}>{eyebrow}</div>
          <div className="text-lg font-semibold text-slate-900">{card.title}</div>
        </div>
      </div>

      {hasBody && <div className="mt-4 flex flex-col gap-4">
        {!!card.kpis?.length && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {card.kpis.slice(0, 4).map((k) => (
              <div key={k.label} className="rounded-xl border border-slate-100 bg-slate-50/70 p-3">
                <div className="flex items-center gap-1 text-xs text-slate-500">
                  <span>{k.icon}</span>
                  {k.label}
                </div>
                <div className="mt-1 text-xl font-bold text-slate-900">{k.value}</div>
              </div>
            ))}
          </div>
        )}

        {card.chart && card.chart.labels?.length > 0 && <ChartView chart={card.chart} />}

        {card.table && card.table.rows?.length > 0 && (
          <div className="overflow-x-auto rounded-xl border border-slate-100">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs text-slate-500 uppercase">
                <tr>
                  {card.table.columns.map((c) => (
                    <th key={c} className="px-3 py-2 font-semibold whitespace-nowrap">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {card.table.rows.map((r, i) => (
                  <tr key={i} className="hover:bg-slate-50/60">
                    {r.map((v, j) => (
                      <td key={j} className="px-3 py-2 whitespace-nowrap text-slate-700">
                        <Cellv value={String(v)} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!!card.insights?.length && (
          <ul className="flex flex-col gap-1.5">
            {card.insights.map((t, i) => (
              <li key={i} className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700"><Inline text={t} /></li>
            ))}
          </ul>
        )}

        {card.sql_used && (
          <div>
            <button
              onClick={() => setShowSql((s) => !s)}
              className="flex cursor-pointer items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-800"
            >
              <ChevronDown className={cn("size-3.5 transition-transform", showSql && "rotate-180")} />
              SQL used
            </button>
            {showSql && (
              <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                {card.sql_used}
              </pre>
            )}
          </div>
        )}
      </div>}
    </motion.div>
  );
}
