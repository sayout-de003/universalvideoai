import { useCallback, useEffect, useState } from "react";
import { API_BASE, studioClient } from "./api/client";
import { AudioStudioView } from "./components/AudioStudioView";
import { BacklotMonitorView } from "./components/BacklotMonitorView";
import { DashboardView } from "./components/DashboardView";
import { DirectorChatView } from "./components/DirectorChatView";
import { ExportCenterView } from "./components/ExportCenterView";
import { NewProjectView } from "./components/NewProjectView";
import { Sidebar } from "./components/Sidebar";
import { ScriptRoomView } from "./components/ScriptRoomView";
import { StoryboardView } from "./components/StoryboardView";
import { TimelineEditorView } from "./components/TimelineEditorView";
import type { HealthResponse, ProjectDetail, ProjectSummary, StudioTab } from "./types/studio";

export function App() {
  const [tab, setTab] = useState<StudioTab>("dashboard");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [engines, setEngines] = useState<Record<string, unknown> | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [storageUsedMb, setStorageUsedMb] = useState(0);
  const [activeProject, setActiveProject] = useState<ProjectDetail | null>(null);
  const [liveEvents, setLiveEvents] = useState<Array<Record<string, unknown>>>([]);
  const [banner, setBanner] = useState<string | null>(null);

  const refreshGlobals = useCallback(async () => {
    try {
      const [h, e, p] = await Promise.all([studioClient.health(), studioClient.engines(), studioClient.listProjects()]);
      setHealth(h); setEngines(e); setProjects(p.projects); setStorageUsedMb(p.storage_used_mb);
    } catch { /* backend booting */ }
  }, []);

  const refreshActiveProject = useCallback(async (id: string) => {
    setActiveProject(await studioClient.getProject(id));
  }, []);

  useEffect(() => {
    refreshGlobals();
    const timer = setInterval(refreshGlobals, 10000);
    return () => clearInterval(timer);
  }, [refreshGlobals]);

  useEffect(() => {
    if (!activeProject) return;
    const pid = activeProject.project.id;
    const es = new EventSource(`${API_BASE}/api/projects/${pid}/events`);
    es.onmessage = (ev) => {
      try {
        const parsed = JSON.parse(ev.data);
        if (parsed.type !== "heartbeat") {
          setLiveEvents((prev) => [parsed, ...prev].slice(0, 50));
          refreshActiveProject(pid);
        }
      } catch { /* ignore */ }
    };
    return () => es.close();
  }, [activeProject?.project.id, refreshActiveProject]);

  const handleOpenProject = async (id: string) => {
    setLiveEvents([]);
    await refreshActiveProject(id);
    setTab("storyboard");
  };

  const handleCreateProject = async (payload: Record<string, unknown>, runImmediately: boolean) => {
    const created = await studioClient.createProject(payload);
    setActiveProject(created);
    await refreshGlobals();
    if (runImmediately) {
      await studioClient.runProject(created.project.id, false);
      setTab("backlot");
    } else {
      setTab("storyboard");
    }
  };

  const handleVoiceCommand = async (transcript: string) => {
    const pid = activeProject?.project.id;
    const res = await studioClient.voiceCommand(transcript, pid, false);
    if (res.requires_confirmation) {
      if (!window.confirm(String(res.message || "Confirm destructive voice command?"))) return;
      const confirmedRes = await studioClient.voiceCommand(transcript, pid, true);
      setBanner(String((confirmedRes.result as Record<string, unknown>)?.reply || "Voice command executed."));
    } else {
      setBanner(String((res.result as Record<string, unknown>)?.reply || "Voice command executed."));
    }
    await refreshGlobals();
    if (pid) await refreshActiveProject(pid);
  };

  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-100 overflow-hidden">
      <Sidebar activeTab={tab} onSelectTab={setTab} hasActiveProject={Boolean(activeProject)} activeTitle={activeProject?.project.title} onVoiceCommand={handleVoiceCommand} />
      <main className="flex-1 overflow-y-auto p-6">
        {banner && (
          <div className="mb-4 px-4 py-2.5 rounded-lg bg-amber-500/15 border border-amber-500/30 text-xs text-amber-200 flex items-center justify-between">
            <span>{banner}</span>
            <button onClick={() => setBanner(null)} className="text-amber-400 hover:underline">Dismiss</button>
          </div>
        )}
        {tab === "dashboard" && <DashboardView health={health} engines={engines} projects={projects} storageUsedMb={storageUsedMb} onOpenProject={handleOpenProject} onNewProject={() => setTab("new_project")} onRefreshProjects={refreshGlobals} />}
        {tab === "new_project" && <NewProjectView onCreate={handleCreateProject} />}
        {tab === "director" && activeProject && <DirectorChatView project={activeProject} onSendMessage={async (msg, confirmed) => { const r = await studioClient.chatDirector(activeProject.project.id, msg, "text", confirmed); await refreshActiveProject(activeProject.project.id); return r; }} />}
        {tab === "script_room" && activeProject && <ScriptRoomView project={activeProject} onRefresh={() => refreshActiveProject(activeProject.project.id)} onStartProduction={async () => { await studioClient.runProject(activeProject.project.id, false); setTab("backlot"); }} />}
        {tab === "storyboard" && activeProject && <StoryboardView project={activeProject} onRegenerateScene={async (sceneId) => { await studioClient.regenerateScene(activeProject.project.id, { scene_id: sceneId }); await refreshActiveProject(activeProject.project.id); setBanner("Regenerated scene in isolation; manual timeline edits preserved."); }} />}
        {tab === "backlot" && activeProject && <BacklotMonitorView project={activeProject} liveEvents={liveEvents} onRun={async () => { await studioClient.runProject(activeProject.project.id, false); await refreshActiveProject(activeProject.project.id); }} onPause={async () => { await studioClient.pauseProject(activeProject.project.id); await refreshActiveProject(activeProject.project.id); }} onResume={async () => { await studioClient.resumeProject(activeProject.project.id); await refreshActiveProject(activeProject.project.id); }} />}
        {tab === "audio" && activeProject && <AudioStudioView project={activeProject} />}
        {tab === "editor" && activeProject && <TimelineEditorView project={activeProject} onTimelineOp={async (op) => { await studioClient.timelineOp(activeProject.project.id, op); await refreshActiveProject(activeProject.project.id); }} onUndo={async () => { await studioClient.timelineUndo(activeProject.project.id); await refreshActiveProject(activeProject.project.id); }} onRedo={async () => { await studioClient.timelineRedo(activeProject.project.id); await refreshActiveProject(activeProject.project.id); }} />}
        {tab === "export" && activeProject && <ExportCenterView project={activeProject} onExport={(body) => studioClient.exportProject(activeProject.project.id, body)} />}
      </main>
    </div>
  );
}
export default App;
