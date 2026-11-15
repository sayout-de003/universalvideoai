import { useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronDown, ChevronRight, Lock, MessageSquarePlus, Play, RotateCcw, Save } from "lucide-react";
import { studioClient } from "../api/client";
import { humanDuration, timecode } from "../lib/progress";
import type { ProjectDetail } from "../types/studio";

interface Props {
  project: ProjectDetail;
  onRefresh: () => Promise<void>;
  onStartProduction: () => Promise<void>;
}

type Artifact = Record<string, unknown>;

// The three documents that must be approved before production can start (backend MANDATORY_GATES).
const GATES = [
  { id: "screenplay", label: "Script", file: "screenplay.md" },
  { id: "storyboard", label: "Storyboard", file: "storyboard.json" },
  { id: "production_plan", label: "Production plan", file: "generation_plan.json" },
];

const GROUPS: Array<{ title: string; files: string[] }> = [
  { title: "Script and story", files: ["screenplay.md", "story_treatment.md", "logline_and_synopsis.md", "story_bible.md", "character_bible.md", "world_and_location_bible.md"] },
  { title: "Visual plan", files: ["storyboard.json", "shot_list.json", "scene_breakdown.json", "cinematography_plan.json", "continuity_bible.json"] },
  { title: "Sound and assets", files: ["audio_design_plan.json", "asset_requirements.json", "asset_registry.json"] },
  { title: "Research", files: ["research_dossier.md", "source_registry.json", "fact_check_ledger.json", "reference_analysis.json", "reference_style_guide.md"] },
  { title: "Plan and records", files: ["creative_brief.md", "generation_plan.json", "production_schedule.json", "cost_estimate.json", "runtime_report.json", "format_specification.json", "project_metadata.json", "screenplay_structured.json", "approval_record.json"] },
];

const niceName = (file: string) => {
  const base = file.replace(/\.(md|json)$/, "").replace(/_/g, " ");
  return base.charAt(0).toUpperCase() + base.slice(1);
};
const wordCount = (t: string) => (t.trim() ? t.trim().split(/\s+/).length : 0);
// Same pacing the backend uses when it times narration (about 2.6 words a second).
const NARRATION_WPS = 2.6;

export function ScriptRoomView({ project, onRefresh, onStartProduction }: Props) {
  const pid = project.project.id;
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [missing, setMissing] = useState<string[]>([]);
  const [selected, setSelected] = useState("screenplay.md");
  const [saved, setSaved] = useState("");
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState("");
  const [noteOpen, setNoteOpen] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [openGroup, setOpenGroup] = useState("Script and story");
  const [busy, setBusy] = useState(false);
  const selectedRef = useRef(selected);
  selectedRef.current = selected;

  const dirty = draft !== saved;
  const approvedGate = (id: string) => !missing.some((m) => m.startsWith(id));
  const allApproved = GATES.every((g) => approvedGate(g.id));
  const artifact = artifacts.find((a) => a.artifact_name === selected);
  const gateOfSelected = GATES.find((g) => g.file === selected);
  const isJson = selected.endsWith(".json");

  const load = async (keep = selectedRef.current) => {
    const res = await studioClient.getPackage(pid);
    setArtifacts(res.artifacts);
    setMissing(res.approval_status.missing_gates);
    const found = res.artifacts.find((a) => a.artifact_name === keep) || res.artifacts[0];
    if (found) {
      setSelected(String(found.artifact_name));
      setSaved(String(found.content_text || ""));
      setDraft(String(found.content_text || ""));
    }
  };

  useEffect(() => { load("screenplay.md").catch((e) => setMsg({ kind: "error", text: String(e) })); }, [pid]);

  const choose = (a: Artifact) => {
    if (dirty && !window.confirm("You have unsaved changes in this document. Discard them?")) return;
    setSelected(String(a.artifact_name));
    setSaved(String(a.content_text || ""));
    setDraft(String(a.content_text || ""));
    setMsg(null);
  };

  const guard = async (fn: () => Promise<void>) => {
    setBusy(true);
    try { await fn(); } catch (e) { setMsg({ kind: "error", text: e instanceof Error ? e.message : String(e) }); } finally { setBusy(false); }
  };

  const save = () => guard(async () => {
    if (!dirty) return;
    if (isJson) {
      try { JSON.parse(draft); } catch (e) { setMsg({ kind: "error", text: `This isn't valid JSON, so it wasn't saved: ${e instanceof Error ? e.message : e}` }); return; }
    }
    const r = await studioClient.updateArtifact(pid, selected, draft);
    setMsg({ kind: "ok", text: `Saved as version ${r.version}.${gateOfSelected ? " This document needs to be approved again." : ""}` });
    await load(selected);
    await onRefresh();
  });

  const addNote = () => guard(async () => {
    if (!note.trim()) return;
    await studioClient.addArtifactComment(pid, selected, note.trim());
    setNote("");
    setMsg({ kind: "ok", text: "Note added." });
  });

  const approve = (gate: string) => guard(async () => {
    if (dirty && !window.confirm("Your unsaved edits aren't included in what you're approving. Approve the saved version anyway?")) return;
    await studioClient.approveGates(pid, gate);
    setMsg({ kind: "ok", text: gate === "all" ? "Everything approved. You can start making the video." : "Approved." });
    await load(selected);
    await onRefresh();
  });

  const onKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") { e.preventDefault(); save(); }
  };

  const grouped = useMemo(() => {
    const names = new Set(artifacts.map((a) => String(a.artifact_name)));
    const used = new Set<string>();
    const out = GROUPS.map((g) => {
      const files = g.files.filter((f) => names.has(f));
      files.forEach((f) => used.add(f));
      return { title: g.title, files };
    });
    const rest = [...names].filter((n) => !used.has(n));
    if (rest.length) out.push({ title: "Other", files: rest });
    return out.filter((g) => g.files.length > 0);
  }, [artifacts]);

  const words = wordCount(draft);
  const estSec = words / NARRATION_WPS;
  const target = project.project.target_duration_sec;
  const versionOf = (name: string) => String(artifacts.find((a) => a.artifact_name === name)?.version ?? "");

  return (
    <div className="space-y-5" onKeyDown={onKeyDown}>
      {/* Approval: the only thing standing between the script and production */}
      <section className="card p-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="font-bold">{allApproved ? "Approved. Ready to make the video." : "Review and approve before production"}</div>
            <p className="hint mt-0.5">{allApproved ? "Editing an approved document asks for approval again." : "Read the script, tweak anything you like, then approve the three documents below."}</p>
          </div>
          <div className="flex items-center gap-2">
            {!allApproved && <button disabled={busy} onClick={() => approve("all")} className="btn btn-quiet"><Check className="w-4 h-4" /> Approve all three</button>}
            <button onClick={() => guard(onStartProduction)} disabled={!allApproved || busy} className="btn btn-live" title={allApproved ? "" : "Approve the script, storyboard and plan first"}>
              {allApproved ? <Play className="w-4 h-4" /> : <Lock className="w-4 h-4" />} Make the video
            </button>
          </div>
        </div>
        <ul className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
          {GATES.map((g) => {
            const ok = approvedGate(g.id);
            return (
              <li key={g.id} className={`rounded-lg border px-3 py-2.5 flex items-center justify-between gap-2 ${ok ? "border-done/40 bg-done-soft" : "border-rule bg-sunken"}`}>
                <button onClick={() => { const a = artifacts.find((x) => x.artifact_name === g.file); if (a) choose(a); }} className="text-left min-w-0">
                  <div className="text-[13px] font-semibold">{g.label}</div>
                  <div className="hint">{ok ? "Approved" : "Waiting for you"}{versionOf(g.file) && ` · v${versionOf(g.file)}`}</div>
                </button>
                {ok ? <Check className="w-4 h-4 text-done shrink-0" aria-label="Approved" /> : <button disabled={busy} onClick={() => approve(g.id)} className="btn btn-quiet py-1 px-2.5 text-xs">Approve</button>}
              </li>
            );
          })}
        </ul>
      </section>

      {msg && <div role={msg.kind === "error" ? "alert" : "status"} className={`px-3 py-2 rounded-lg text-[13px] border ${msg.kind === "error" ? "bg-live-soft border-live/40 text-live" : "bg-done-soft border-done/30 text-done"}`}>{msg.text}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-[250px_1fr] gap-5 items-start">
        {/* Left: scene outline, then every other document */}
        <aside className="space-y-4">
          <div className="card p-3">
            <div className="label px-1">Outline · {project.scenes.length} scenes</div>
            <div className="max-h-[280px] overflow-y-auto space-y-3">
              {project.chapters.map((ch) => (
                <div key={ch.id}>
                  <div className="px-1 text-[13px] font-semibold">{ch.title}</div>
                  <ol className="mt-1 space-y-0.5">
                    {project.scenes.filter((s) => s.chapter_id === ch.id).map((s) => (
                      <li key={s.id} className="px-1 py-1 rounded text-[12px] text-slate flex justify-between gap-2" title={s.narration_segment}>
                        <span className="truncate">{s.title}</span><span className="timecode shrink-0">{timecode(s.duration_sec)}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              ))}
              {project.scenes.length === 0 && <div className="hint px-1">Scenes appear once the script is written.</div>}
            </div>
          </div>
          <div className="card p-2">
            <div className="label px-2 pt-1">Documents · {artifacts.length}</div>
            {grouped.map((g) => {
              const open = openGroup === g.title || g.files.includes(selected);
              return (
                <div key={g.title}>
                  <button onClick={() => setOpenGroup(open && openGroup === g.title ? "" : g.title)} className="w-full flex items-center justify-between px-2 py-1.5 text-[13px] font-semibold text-slate hover:text-ink" aria-expanded={open}>
                    {g.title}{open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                  </button>
                  {open && g.files.map((f) => {
                    const a = artifacts.find((x) => x.artifact_name === f)!;
                    return (
                      <button key={f} onClick={() => choose(a)} aria-current={f === selected ? "true" : undefined}
                        className={`w-full text-left px-2 py-1.5 rounded text-[13px] flex justify-between gap-2 ${f === selected ? "bg-ink text-white" : "hover:bg-sunken"}`}>
                        <span className="truncate">{niceName(f)}</span><span className={`text-xs ${f === selected ? "text-[#b9c2cb]" : "text-mute"}`}>v{String(a.version)}</span>
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </aside>

        {/* Right: the document */}
        <section className="card overflow-hidden">
          <div className="px-5 py-3 border-b border-rule flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="font-bold truncate">{niceName(selected)}</div>
              <div className="hint">
                Version {String(artifact?.version ?? "–")}{gateOfSelected && " · needs your approval"}
                {!isJson && words > 0 && ` · ${words.toLocaleString()} words ≈ ${humanDuration(estSec)} spoken`}
                {!isJson && selected === "screenplay.md" && target > 0 && estSec > 0 && Math.abs(estSec - target) / target > 0.25 && ` (target is ${humanDuration(target)})`}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {dirty && <span className="chip chip-hold">Unsaved changes</span>}
              <button className="btn btn-ghost" disabled={!dirty || busy} onClick={() => setDraft(saved)}><RotateCcw className="w-4 h-4" /> Revert</button>
              <button className="btn btn-primary" disabled={!dirty || busy} onClick={save}><Save className="w-4 h-4" /> Save</button>
            </div>
          </div>
          <textarea
            aria-label={`Edit ${niceName(selected)}`}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            spellCheck={!isJson}
            className={`w-full min-h-[560px] block resize-y px-8 py-6 bg-panel focus:outline-none ${isJson ? "font-mono text-[12.5px] leading-relaxed" : "script-paper"}`}
          />
          <div className="border-t border-rule">
            <button onClick={() => setNoteOpen((v) => !v)} className="w-full px-5 py-2.5 flex items-center gap-2 text-[13px] font-semibold text-slate hover:text-ink" aria-expanded={noteOpen}>
              <MessageSquarePlus className="w-4 h-4" /> Leave a review note
            </button>
            {noteOpen && (
              <div className="px-5 pb-4 flex gap-2">
                <input className="field" value={note} onChange={(e) => setNote(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addNote()} placeholder={`A note about ${niceName(selected).toLowerCase()}…`} />
                <button className="btn btn-quiet" disabled={!note.trim() || busy} onClick={addNote}>Add note</button>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
