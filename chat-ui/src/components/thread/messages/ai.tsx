import { useStreamContext } from "@/providers/Stream";
import { Checkpoint, Message } from "@langchain/langgraph-sdk";
import { useState } from "react";
import { getContentString } from "../utils";
import { BranchSwitcher, CommandBar } from "./shared";
import { MarkdownText } from "../markdown-text";
import { cn } from "@/lib/utils";
import { isAgentInboxInterruptSchema } from "@/lib/agent-inbox-interrupt";
import { GenericInterruptView } from "./generic-interrupt";
import { ANSWER_TOOL, useArenaMode } from "@/arena/config";
import { ToolSteps } from "@/arena/tool-steps";
import { AnswerCardView } from "@/arena/answer-card";
import { ApprovalCard } from "@/arena/approval-card";
import { useTypewriter } from "@/arena/typewriter";

/** Pending human decision (rendered once, below the last message). */
export function ThreadInterrupt() {
  const { interrupt } = useStreamContext();
  if (!interrupt) return null;
  if (isAgentInboxInterruptSchema(interrupt)) {
    const value = (Array.isArray(interrupt) ? interrupt[0] : interrupt).value as any;
    return <ApprovalCard key={JSON.stringify(value.action_requests)} value={value} />;
  }
  const fallback = Array.isArray(interrupt)
    ? (interrupt as Record<string, any>[])
    : (((interrupt as { value?: unknown }).value ?? interrupt) as Record<string, any>);
  return <GenericInterruptView interrupt={fallback} />;
}

export function AssistantMessage({
  message,
  isLoading,
  handleRegenerate,
}: {
  message: Message | undefined;
  isLoading: boolean;
  handleRegenerate: (parentCheckpoint: Checkpoint | null | undefined) => void;
}) {
  const thread = useStreamContext();
  const mode = useArenaMode();
  const [live] = useState(() => isLoading); // arrived while streaming → animate
  const contentString = getContentString(message?.content ?? []);
  const { shown, done } = useTypewriter(contentString, live && contentString.length > 0);

  if (!message || message.type === "tool") return null; // tool results render inside the tool steps

  const toolCalls = ("tool_calls" in message && message.tool_calls) || [];
  const realCalls = toolCalls.filter((tc) => tc.name !== ANSWER_TOOL);
  const card = thread.values.ui?.find(
    (u) => u.name === "answer_card" && u.metadata?.message_id === message.id,
  );
  if (!contentString && !realCalls.length && !card) return null;

  const meta = thread.getMessagesMetadata(message);
  const parentCheckpoint = meta?.firstSeenState?.parent_checkpoint;

  return (
    <div className="group mr-auto flex w-full items-start gap-3">
      <div
        className={cn(
          "mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full text-xs",
          contentString ? "bg-slate-900" : "invisible",
        )}
      >
        {mode === "guarded" ? "🛡️" : "🔓"}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        {realCalls.length > 0 && (
          <ToolSteps toolCalls={realCalls} messages={thread.messages} mode={mode} isLoading={isLoading} />
        )}
        {contentString.length > 0 && (
          <div className="text-[15px] leading-relaxed text-slate-800">
            <MarkdownText>{shown}</MarkdownText>
          </div>
        )}
        {card && done && <AnswerCardView card={card.props as any} />}
        {contentString.length > 0 && (
          <div
            className={cn(
              "mr-auto flex items-center gap-2 transition-opacity",
              "opacity-0 group-focus-within:opacity-100 group-hover:opacity-100",
            )}
          >
            <BranchSwitcher
              branch={meta?.branch}
              branchOptions={meta?.branchOptions}
              onSelect={(branch) => thread.setBranch(branch)}
              isLoading={isLoading}
            />
            <CommandBar
              content={contentString}
              isLoading={isLoading}
              isAiMessage={true}
              handleRegenerate={() => handleRegenerate(parentCheckpoint)}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export function AssistantMessageLoading({ label = "Thinking" }: { label?: string }) {
  return (
    <div className="mr-auto flex items-center gap-3">
      <div className="flex size-7 items-center justify-center rounded-full bg-slate-100">
        <div className="size-2.5 animate-ping rounded-full bg-slate-400" />
      </div>
      <span className="animate-pulse text-sm font-medium text-slate-500">{label}…</span>
    </div>
  );
}
