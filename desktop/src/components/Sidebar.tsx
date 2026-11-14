import { Clapperboard, Download, FileText, Film, LayoutDashboard, MessageSquare, Mic, Music, PlusCircle, Radio, Scissors } from "lucide-react";
import type { StudioTab } from "../types/studio";

interface Props {
  activeTab: StudioTab;
  onSelectTab: (tab: StudioTab) => void;
  hasActiveProject: boolean;
  activeTitle?: string;
  onVoiceCommand: (transcript: string) => void;
}

const NAV_ITEMS: Array<{ id: StudioTab; label: string; icon: typeof LayoutDashboard; needsProject?: boolean }> = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "new_project", label: "New Production", icon: PlusCircle },
  { id: "director", label: "AI Director", icon: MessageSquare, needsProject: true },
  { id: "script_room", label: "Script & Package", icon: FileText, needsProject: true },
  { id: "storyboard", label: "Storyboard", icon: Clapperboard, needsProject: true },
  { id: "backlot", label: "Backlot Monitor", icon: Radio, needsProject: true },
  { id: "audio", label: "Audio Studio", icon: Music, needsProject: true },
  { id: "editor", label: "Timeline Editor", icon: Scissors, needsProject: true },
  { id: "export", label: "Export Center", icon: Download, needsProject: true },
];

export function Sidebar({ activeTab, onSelectTab, hasActiveProject, activeTitle, onVoiceCommand }: Props) {
  const handleQuickVoice = () => {
    const cmd = window.prompt(
      "OpenWhispr Voice Command (type or dictate via OpenWhispr global hotkey):\nExamples: 'Regenerate scene 2', 'Make the background music quieter', 'Export the final film in 4K'"
    );
    if (cmd && cmd.trim()) onVoiceCommand(cmd.trim());
  };

  return (
    <aside className="w-64 shrink-0 border-r border-zinc-800 bg-zinc-950 flex flex-col justify-between p-4">
      <div>
        <div className="flex items-center gap-2.5 px-2 py-2 mb-6">
          <div className="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-500/40 flex items-center justify-center text-amber-400">
            <Film className="w-4 h-4" />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight text-zinc-100">Universal AI Studio</div>
            <div className="text-[11px] text-zinc-500">OpenMontage + OpenWhispr</div>
          </div>
        </div>
        {activeTitle && (
          <div className="mb-4 px-3 py-2 rounded-lg bg-zinc-900/90 border border-zinc-800">
            <div className="text-[10px] uppercase tracking-wider text-zinc-500">Active Production</div>
            <div className="text-xs font-medium text-amber-300 truncate mt-0.5">{activeTitle}</div>
          </div>
        )}
        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const disabled = Boolean(item.needsProject && !hasActiveProject);
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                disabled={disabled}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition ${
                  active ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                    : disabled ? "text-zinc-600 cursor-not-allowed" : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900"
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
      <button onClick={handleQuickVoice} className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-xs font-medium text-zinc-200 transition">
        <Mic className="w-3.5 h-3.5 text-amber-400" />
        <span>OpenWhispr Voice Command</span>
      </button>
    </aside>
  );
}
