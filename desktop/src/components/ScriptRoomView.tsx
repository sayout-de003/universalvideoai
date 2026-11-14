import { useEffect, useState } from "react";
import { CheckCircle2, FileText, Lock, MessageSquarePlus, Save, ShieldCheck } from "lucide-react";
import { studioClient } from "../api/client";
import type { ProjectDetail } from "../types/studio";

interface Props {
  project: ProjectDetail;
  onRefresh: () => Promise<void>;
  onStartProduction: () => Promise<void>;
}

export function ScriptRoomView({ project, onRefresh, onStartProduction }: Props) {
  const pid = project.project.id;
  const [artifacts, setArtifacts] = useState<Array<Record<string, unknown>>>([]);
  const [approvalStatus, setApprovalStatus] = useState<{ approved: boolean; missing_gates: string[] }>({ approved: false, missing_gates: [] });
  const [selectedName, setSelectedName] = useState<string>("screenplay.md");
  const [draftText, setDraftText] = useState<string>("");
  const [commentText, setCommentText] = useState<string>("");
  const [statusMsg, setStatusMsg] = useState<string>("");

  const loadPackage = async () => {
    const res = await studioClient.getPackage(pid);
    setArtifacts(res.artifacts);
    setApprovalStatus(res.approval_status);
    const found = res.artifacts.find((a) => a.artifact_name === selectedName) || res.artifacts[0];
    if (found) {
      setSelectedName(String(found.artifact_name));
      setDraftText(String(found.content_text || ""));
    }
  };

  useEffect(() => {
    loadPackage();
  }, [pid]);

  const handleSelect = (art: Record<string, unknown>) => {
    setSelectedName(String(art.artifact_name));
    setDraftText(String(art.content_text || ""));
  };

  const handleSaveVersion = async () => {
    const r = await studioClient.updateArtifact(pid, selectedName, draftText);
    setStatusMsg(`Saved ${selectedName} v${r.version} (re-approval required for modified gate).`);
    await loadPackage();
    await onRefresh();
  };

  const handleAddComment = async () => {
    if (!commentText.trim()) return;
    await studioClient.addArtifactComment(pid, selectedName, commentText.trim());
    setCommentText("");
    setStatusMsg(`Added review comment on ${selectedName}.`);
  };

  const handleApproveAll = async () => {
    await studioClient.approveGates(pid, "all");
    setStatusMsg("Approved Screenplay, Storyboard, and Production Plan gates.");
    await loadPackage();
    await onRefresh();
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 bg-zinc-900/90 border border-zinc-800 rounded-xl p-4">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2">
            <FileText className="w-5 h-5 text-amber-400" />
            Script Room & 28-Artifact Production Package
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Review, edit (creates immutable versions), comment, and approve mandatory gates before video generation.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {approvalStatus.approved ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" /> Gates Approved
            </span>
          ) : (
            <button onClick={handleApproveAll} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 text-zinc-950 text-xs font-semibold hover:bg-amber-400">
              <ShieldCheck className="w-3.5 h-3.5" /> Approve Screenplay, Storyboard & Plan
            </button>
          )}
          <button
            onClick={onStartProduction}
            disabled={!approvalStatus.approved}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500 text-zinc-950 text-xs font-semibold disabled:opacity-40 hover:bg-emerald-400"
          >
            {!approvalStatus.approved && <Lock className="w-3.5 h-3.5" />}
            Start Production
          </button>
        </div>
      </div>

      {statusMsg && <div className="px-3 py-2 rounded-lg bg-zinc-900 border border-amber-500/30 text-xs text-amber-300">{statusMsg}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="bg-zinc-900/70 border border-zinc-800 rounded-xl p-3 max-h-[600px] overflow-y-auto space-y-1">
          <div className="text-[11px] uppercase tracking-wider text-zinc-500 px-2 pb-1">Artifacts ({artifacts.length}/28)</div>
          {artifacts.map((art) => {
            const name = String(art.artifact_name);
            const active = name === selectedName;
            return (
              <button
                key={name}
                onClick={() => handleSelect(art)}
                className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs flex items-center justify-between ${active ? "bg-amber-500/15 text-amber-300 border border-amber-500/30" : "text-zinc-300 hover:bg-zinc-800/70"}`}
              >
                <span className="truncate">{name}</span>
                <span className="text-[10px] text-zinc-500 ml-2">v{String(art.version)}</span>
              </button>
            );
          })}
        </div>

        <div className="lg:col-span-3 bg-zinc-900/70 border border-zinc-800 rounded-xl p-4 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium text-zinc-200">{selectedName}</div>
            <button onClick={handleSaveVersion} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-100 border border-zinc-700">
              <Save className="w-3.5 h-3.5" /> Save New Version
            </button>
          </div>
          <textarea
            value={draftText}
            onChange={(e) => setDraftText(e.target.value)}
            rows={18}
            className="w-full rounded-lg bg-zinc-950 border border-zinc-800 p-3 text-xs font-mono text-zinc-200 focus:outline-none focus:border-amber-500/50"
          />
          <div className="flex gap-2">
            <input
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              placeholder={`Add review comment on ${selectedName}...`}
              className="flex-1 rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200"
            />
            <button onClick={handleAddComment} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-200 border border-zinc-700">
              <MessageSquarePlus className="w-3.5 h-3.5" /> Comment
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
