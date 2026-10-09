import { useThreads } from "@/providers/Thread";
import { useStreamContext } from "@/providers/Stream";
import { Thread } from "@langchain/langgraph-sdk";
import { useEffect, useRef } from "react";
import { getContentString } from "../utils";
import { useQueryState, parseAsBoolean } from "nuqs";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { PanelLeft, SquarePen } from "lucide-react";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { cn } from "@/lib/utils";
import { useArenaMode } from "@/arena/config";

function threadTitle(t: Thread): string {
  const msgs = (t.values as any)?.messages;
  const first = Array.isArray(msgs) ? msgs.find((m: any) => m.type === "human") : undefined;
  return (first && getContentString(first.content)) || "New chat";
}

function ThreadList({ threads, onThreadClick }: { threads: Thread[]; onThreadClick?: () => void }) {
  const [threadId, setThreadId] = useQueryState("threadId");
  return (
    <div className="flex w-full flex-col gap-0.5 px-2">
      {threads.map((t) => (
        <button
          key={t.thread_id}
          onClick={() => {
            onThreadClick?.();
            if (t.thread_id !== threadId) setThreadId(t.thread_id);
          }}
          title={threadTitle(t)}
          className={cn(
            "flex w-full cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-800 hover:bg-slate-200/60",
            t.thread_id === threadId && "bg-slate-200/80 font-medium",
          )}
        >
          <span className="truncate">{threadTitle(t)}</span>
          {t.status === "interrupted" && (
            <span
              title="Waiting for approval"
              className="ml-auto size-2 shrink-0 rounded-full bg-amber-500"
            />
          )}
          {t.status === "busy" && (
            <span className="ml-auto size-2 shrink-0 animate-pulse rounded-full bg-sky-500" />
          )}
        </button>
      ))}
    </div>
  );
}

function SidebarBody({ onPick }: { onPick?: () => void }) {
  const mode = useArenaMode();
  const [, setThreadId] = useQueryState("threadId");
  const [, setChatHistoryOpen] = useQueryState("chatHistoryOpen", parseAsBoolean.withDefault(true));
  const { threads, threadsLoading } = useThreads();
  const chats = threads.filter((t) => Array.isArray((t.values as any)?.messages) && (t.values as any).messages.length);

  return (
    <div className="flex h-full w-full flex-col">
      <div className="flex items-center justify-between px-4 pt-3 pb-2">
        <span className="text-[17px] font-semibold tracking-tight text-slate-900">Guardrails Arena</span>
        <button
          onClick={() => setChatHistoryOpen(false)}
          title="Close sidebar"
          className="hidden cursor-pointer rounded-lg p-1.5 text-slate-500 hover:bg-slate-200/60 lg:block"
        >
          <PanelLeft className="size-5" />
        </button>
      </div>
      <div className="px-2">
        <button
          onClick={() => {
            setThreadId(null);
            onPick?.();
          }}
          className="flex w-full cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-800 hover:bg-slate-200/60"
        >
          <SquarePen className="size-4" /> New chat
        </button>
      </div>
      <div className="mt-4 px-5 pb-1 text-xs font-medium text-slate-500">Recents</div>
      <div className="min-h-0 flex-1 overflow-y-auto pb-2 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300">
        {threadsLoading && !threads.length ? (
          <div className="flex flex-col gap-2 px-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : chats.length ? (
          <ThreadList threads={chats} onThreadClick={onPick} />
        ) : (
          <div className="px-5 py-2 text-sm text-slate-400">No chats yet</div>
        )}
      </div>
      <div className="flex items-center gap-3 border-t border-slate-200 px-4 py-3">
        <div
          className={cn(
            "flex size-8 items-center justify-center rounded-full text-sm",
            mode === "guarded" ? "bg-emerald-100" : "bg-rose-100",
          )}
        >
          {mode === "guarded" ? "🛡️" : "🔓"}
        </div>
        <div className="leading-tight">
          <div className="text-sm font-medium text-slate-900">
            {mode === "guarded" ? "Guarded agent" : "Unguarded agent"}
          </div>
          <div className="text-xs text-slate-500">Nagarro Flo · Gemini + SQL</div>
        </div>
      </div>
    </div>
  );
}

export default function ThreadHistory() {
  const isLargeScreen = useMediaQuery("(min-width: 1024px)");
  const [chatHistoryOpen, setChatHistoryOpen] = useQueryState("chatHistoryOpen", parseAsBoolean.withDefault(true));
  const { getThreads, setThreads, setThreadsLoading } = useThreads();
  const { isLoading } = useStreamContext();
  const wasLoading = useRef(false);

  const refresh = () =>
    getThreads()
      .then(setThreads)
      .catch(console.error)
      .finally(() => setThreadsLoading(false));

  useEffect(() => {
    if (typeof window === "undefined") return;
    setThreadsLoading(true);
    refresh();
  }, []);

  // Refresh titles / status dots whenever a run starts or finishes.
  useEffect(() => {
    if (isLoading !== wasLoading.current) {
      wasLoading.current = isLoading;
      setTimeout(refresh, isLoading ? 800 : 300);
    }
  }, [isLoading]);

  return (
    <>
      <div className="hidden h-screen w-[260px] shrink-0 lg:flex">
        <SidebarBody />
      </div>
      <div className="lg:hidden">
        <Sheet
          open={!!chatHistoryOpen && !isLargeScreen}
          onOpenChange={(open) => {
            if (isLargeScreen) return;
            setChatHistoryOpen(open);
          }}
        >
          <SheetContent side="left" className="flex bg-[#f9f9f9] p-0 lg:hidden">
            <SheetHeader className="sr-only">
              <SheetTitle>Chats</SheetTitle>
            </SheetHeader>
            <SidebarBody onPick={() => setChatHistoryOpen(false)} />
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
}
