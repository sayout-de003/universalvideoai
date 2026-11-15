import { Download, FileText, Clapperboard, Radio, Music, Scissors, MessageSquare, ArrowLeft } from "lucide-react";
import { progressOfDetail, timecode, generatedSeconds } from "../lib/progress";
import type { ProjectDetail, StudioTab } from "../types/studio";

interface Props {
  project: ProjectDetail;
  tab: StudioTab;
  onSelectTab: (tab: StudioTab) => void;
  onBack: () => void;
}

const STEPS: Array<{ id: StudioTab; label: string; icon: typeof FileText }> = [
  { id: "script_room", label: "Script", icon: FileText },
  { id: "storyboard", label: "Storyboard", icon: Clapperboard },
  { id: "backlot", label: "Produce", icon: Radio },
  { id: "audio", label: "Audio", icon: Music },
  { id: "editor", label: "Edit", icon: Scissors },
  { id: "export", label: "Export", icon: Download },
];

const chipClass = { idle: "chip", live: "chip chip-live", done: "chip chip-done", hold: "chip chip-hold" } as const;

export function ProjectHeader({ project, tab, onSelectTab, onBack }: Props) {
  const pr = progressOfDetail(project);
  const { done, total } = generatedSeconds(project);
  const tabBtn = (id: StudioTab, label: string, Icon: typeof FileText) => (
    <button
      key={id}
      onClick={() => onSelectTab(id)}
      aria-current={tab === id ? "page" : undefined}
      className={`inline-flex items-center gap-1.5 px-3 py-2 text-[13px] font-semibold border-b-2 -mb-px transition ${tab === id ? "border-ink text-ink" : "border-transparent text-slate hover:text-ink"}`}
    >
      <Icon className="w-4 h-4" /> {label}
    </button>
  );
  return (
    <header className="mb-6">
      <button onClick={onBack} className="btn btn-ghost -ml-2 mb-1"><ArrowLeft className="w-4 h-4" /> My videos</button>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold tracking-tight truncate max-w-[60ch]">{project.project.title}</h1>
          <div className="flex items-center gap-2 mt-1.5">
            <span className={chipClass[pr.tone]}>{pr.tone === "live" && <span className="w-1.5 h-1.5 rounded-full bg-live tally" />}{pr.label}</span>
            <span className="hint">{pr.headline}</span>
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="timecode text-lg font-semibold">{timecode(done)} <span className="text-mute">/ {timecode(total)}</span></div>
          <div className="hint">video generated · {pr.percent}% complete</div>
        </div>
      </div>
      <div className="h-1.5 rounded-full bg-rule mt-4 overflow-hidden" role="progressbar" aria-valuenow={pr.percent} aria-valuemin={0} aria-valuemax={100} aria-label="Overall progress">
        <div className={`h-full rounded-full transition-all duration-700 ${pr.tone === "done" ? "bg-done" : pr.tone === "hold" ? "bg-hold" : "bg-live"}`} style={{ width: `${pr.percent}%` }} />
      </div>
      <nav className="flex items-center justify-between border-b border-rule mt-4 overflow-x-auto">
        <div className="flex">{STEPS.map((s) => tabBtn(s.id, s.label, s.icon))}</div>
        {tabBtn("director", "Ask the director", MessageSquare)}
      </nav>
    </header>
  );
}
