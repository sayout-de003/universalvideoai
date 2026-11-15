import { Film, Mic, PlusCircle, Video } from "lucide-react";
import type { StudioTab } from "../types/studio";

interface Props {
  activeTab: StudioTab;
  onSelectTab: (tab: StudioTab) => void;
  engineOnline: boolean;
  onVoiceCommand: () => void;
}

export function Sidebar({ activeTab, onSelectTab, engineOnline, onVoiceCommand }: Props) {
  const item = (id: StudioTab, label: string, Icon: typeof Video, active: boolean) => (
    <button
      onClick={() => onSelectTab(id)}
      aria-current={active ? "page" : undefined}
      className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[13px] font-semibold text-left transition ${active ? "bg-white text-ink" : "text-[#b9c2cb] hover:text-white hover:bg-white/10"}`}
    >
      <Icon className="w-4 h-4" /> {label}
    </button>
  );
  const onHome = activeTab !== "new_project";
  return (
    <aside className="w-56 shrink-0 bg-ink text-white flex flex-col justify-between p-4">
      <div>
        <div className="flex items-center gap-2.5 px-1 py-2 mb-6">
          <div className="w-8 h-8 rounded-md bg-live flex items-center justify-center"><Film className="w-4 h-4" /></div>
          <div className="text-[15px] font-bold leading-tight">AI Video<br />Studio</div>
        </div>
        <nav className="space-y-1">
          {item("dashboard", "My videos", Video, onHome)}
          {item("new_project", "New video", PlusCircle, !onHome)}
        </nav>
      </div>
      <div className="space-y-3">
        <button onClick={onVoiceCommand} className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border border-white/20 text-[13px] font-semibold hover:bg-white/10">
          <Mic className="w-4 h-4" /> Voice command
        </button>
        <div className="flex items-center gap-2 px-1 text-xs text-[#b9c2cb]">
          <span className={`w-2 h-2 rounded-full ${engineOnline ? "bg-[#3ec9b4]" : "bg-live tally"}`} />
          {engineOnline ? "Studio engine connected" : "Studio engine starting…"}
        </div>
      </div>
    </aside>
  );
}
