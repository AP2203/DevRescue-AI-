import { useCallback, useEffect, useRef, useState } from "react";
import { analysisApi } from "../../api/analysis";
import { useToast } from "../../hooks/useToast";
import { extractApiError } from "../../api/client";
import { relativeTime } from "../../lib/format";
import { Button } from "../ui/Button";
import { Icon } from "../ui/Icon";
import type { EditHistoryEntry, EditResult, EditVersionEntry, EditVersionsResponse } from "../../types/analysis";

const EXAMPLE_COMMANDS = [
  "Make it red",
  "Change to metallic material",
  "Reduce polygon count by 50%",
  "Make it matte white",
  "Prepare for 3D printing",
];

const operationTypeLabel: Record<string, string> = {
  ai_edit: "AI Edit",
  repair: "Auto Repair",
  optimization: "Optimization",
};

function operationSummary(entry: EditHistoryEntry): string {
  const ops = entry.parsed_command?.operations;
  if (ops && ops.length > 0) {
    return ops.map((op) => op.type.replace(/_/g, " ")).join(", ");
  }
  if (entry.parsed_command?.operation) {
    return entry.parsed_command.operation.replace(/_/g, " ");
  }
  return "";
}

function HistoryItem({ entry }: { entry: EditHistoryEntry }) {
  const beforeFaces = entry.before_stats?.faces ?? 0;
  const afterFaces = entry.after_stats?.faces ?? 0;
  const opLabel = operationSummary(entry);

  return (
    <div className="flex items-start gap-3 rounded-xl border border-white/8 bg-white/[0.02] p-3">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand-500/20 text-brand-300">
        <Icon name="settings" className="h-3.5 w-3.5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-200">
            {operationTypeLabel[entry.operation_type] ?? entry.operation_type}
          </span>
          {entry.version > 0 && (
            <span className="rounded-full border border-brand-400/20 bg-brand-500/10 px-1.5 py-0.5 font-mono text-[9px] text-brand-300">
              v{entry.version}
            </span>
          )}
          {opLabel && (
            <span className="rounded-full border border-white/10 bg-white/[0.04] px-1.5 py-0.5 font-mono text-[9px] text-slate-500">
              {opLabel}
            </span>
          )}
        </div>
        {entry.user_command && (
          <p className="mt-0.5 truncate text-[11px] text-slate-500 italic">"{entry.user_command}"</p>
        )}
        <div className="mt-1 flex items-center gap-2 text-[10px] text-slate-600">
          <span>{relativeTime(entry.created_at)}</span>
          {beforeFaces > 0 && (
            <>
              <span>·</span>
              <span>{beforeFaces.toLocaleString()} → {afterFaces.toLocaleString()} faces</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export function AIEditPanel({
  projectId,
  onModelUpdated,
}: {
  projectId: string;
  onModelUpdated?: () => void;
}) {
  const { toast } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [command, setCommand] = useState("");
  const [loading, setLoading] = useState(false);
  const [navLoading, setNavLoading] = useState<"undo" | "redo" | null>(null);
  const [result, setResult] = useState<EditResult | null>(null);
  const [history, setHistory] = useState<EditHistoryEntry[]>([]);
  const [versions, setVersions] = useState<EditVersionsResponse | null>(null);
  const [historyLoading, setHistoryLoading] = useState(true);

  const fetchHistory = useCallback(async () => {
    try {
      const data = await analysisApi.getEditHistory(projectId, 10);
      setHistory(data);
    } catch {
      // no history yet
    } finally {
      setHistoryLoading(false);
    }
  }, [projectId]);

  const fetchVersions = useCallback(async () => {
    try {
      const data = await analysisApi.getEditVersions(projectId);
      setVersions(data);
    } catch {
      setVersions(null);
    }
  }, [projectId]);

  useEffect(() => {
    void fetchHistory();
    void fetchVersions();
  }, [fetchHistory, fetchVersions]);

  const handleSubmit = async (cmd = command) => {
    if (!cmd.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const data = await analysisApi.applyEdit(projectId, cmd);
      setResult(data);
      setCommand("");
      toast("success", `Edit applied (v${data.version})`);
      void fetchHistory();
      void fetchVersions();
      onModelUpdated?.();
    } catch (err) {
      toast("error", "Edit failed", { description: extractApiError(err) });
    } finally {
      setLoading(false);
    }
  };

  const handleUndo = async () => {
    if (navLoading) return;
    setNavLoading("undo");
    try {
      const data = await analysisApi.undoEdit(projectId);
      toast("success", `Undo — now showing v${data.version}`);
      void fetchHistory();
      void fetchVersions();
      onModelUpdated?.();
    } catch (err) {
      toast("error", "Undo failed", { description: extractApiError(err) });
    } finally {
      setNavLoading(null);
    }
  };

  const handleRedo = async () => {
    if (navLoading) return;
    setNavLoading("redo");
    try {
      const data = await analysisApi.redoEdit(projectId);
      toast("success", `Redo — now showing v${data.version}`);
      void fetchHistory();
      void fetchVersions();
      onModelUpdated?.();
    } catch (err) {
      toast("error", "Redo failed", { description: extractApiError(err) });
    } finally {
      setNavLoading(null);
    }
  };

  const currentVersion = versions?.current_version ?? 0;
  const canUndo = versions?.can_undo ?? false;
  const canRedo = versions?.can_redo ?? false;

  return (
    <div className="panel p-5 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 font-display text-base font-semibold text-white">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-purple-500 to-brand-400 shadow-glow">
            <Icon name="generate" className="h-4 w-4 text-white" />
          </span>
          AI 3D Editor
        </h2>

        {/* Undo / Redo */}
        <div className="flex gap-1.5">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void handleUndo()}
            disabled={!canUndo}
            loading={navLoading === "undo"}
            title="Undo last edit"
            id="btn-undo-edit"
          >
            <Icon name="chevronLeft" className="h-3.5 w-3.5" /> Undo
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void handleRedo()}
            disabled={!canRedo}
            loading={navLoading === "redo"}
            title="Redo undone edit"
            id="btn-redo-edit"
          >
            Redo <Icon name="chevronRight" className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Input */}
      <div className="space-y-2">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            id="ai-edit-input"
            type="text"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !loading) void handleSubmit();
            }}
            placeholder='e.g. "Make the car red" or "Reduce polygons by 50%"'
            className="min-w-0 flex-1 rounded-xl border border-white/10 bg-ink-800/70 px-3 py-2.5 text-sm text-white placeholder-slate-500 outline-none transition-all focus:border-brand-400/60 focus:ring-2 focus:ring-brand-500/20"
          />
          <Button
            size="sm"
            onClick={() => void handleSubmit()}
            loading={loading}
            disabled={!command.trim()}
            id="btn-apply-edit"
          >
            Apply
          </Button>
        </div>

        {/* Example commands */}
        <div className="flex flex-wrap gap-1.5">
          {EXAMPLE_COMMANDS.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => {
                setCommand(ex);
                inputRef.current?.focus();
              }}
              className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[10px] text-slate-400 transition-colors hover:border-brand-400/30 hover:text-brand-300"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {/* Version timeline */}
      {versions && versions.versions.length > 0 && (
        <div className="space-y-2 rounded-xl border border-white/8 bg-white/[0.02] p-3">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">Versions</p>
            <p className="font-mono text-[10px] text-slate-600">
              v{currentVersion} / v{versions.max_version}
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {versions.versions.map((v: EditVersionEntry) => (
              <span
                key={v.version}
                className={`rounded-full px-2 py-0.5 font-mono text-[10px] transition-colors ${
                  v.version === currentVersion
                    ? "bg-brand-500/20 text-brand-300 ring-1 ring-brand-400/40"
                    : "bg-white/[0.03] text-slate-500"
                }`}
                title={v.user_command ?? undefined}
              >
                {v.label}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3">
          <div className="flex items-center gap-2">
            <Icon name="check" className="h-4 w-4 text-emerald-400" />
            <p className="text-xs font-medium text-emerald-300">{result.message}</p>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] text-slate-400">
            <span>
              Version: <strong className="text-slate-200">v{result.version}</strong>
            </span>
            <span>
              Quality: <strong className="text-slate-200">{result.quality_score}/100</strong>
            </span>
            {result.parsed_command.operations?.map((op, i) => (
              <span key={i}>
                {i === 0 ? "Ops: " : "· "}
                <strong className="text-slate-200">{op.type.replace(/_/g, " ")}</strong>
                {op.value !== undefined && ` ${String(op.value)}`}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* History */}
      {!historyLoading && history.length > 0 && (
        <div className="space-y-2 border-t border-white/8 pt-4">
          <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Edit History</p>
          <div className="space-y-2">
            {history.slice(0, 5).map((entry) => (
              <HistoryItem key={entry.id} entry={entry} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}