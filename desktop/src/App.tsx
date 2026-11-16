import { useCallback, useEffect, useState } from "react";
import { API_BASE, studioClient } from "./api/client";
import { AudioStudioView } from "./components/AudioStudioView";
import { BacklotMonitorView } from "./components/BacklotMonitorView";
import { DashboardView } from "./components/DashboardView";
import { DirectorChatView } from "./components/DirectorChatView";
import { ExportCenterView } from "./components/ExportCenterView";
import { NewProjectView, type PendingRefUpload } from "./components/NewProjectView";
import { ProjectHeader } from "./components/ProjectHeader";
import { HypitStudioView } from "./components/HypitStudioView";
import { ScriptRoomView } from "./components/ScriptRoomView";
import { Sidebar } from "./components/Sidebar";
import { StoryboardView } from "./components/StoryboardView";
import { TimelineEditorView } from "./components/TimelineEditorView";
import { VoiceCommandDialog } from "./components/VoiceCommandDialog";
import { isIdle } from "./lib/progress";
import type { HealthResponse, ProjectDetail, ProjectSummary, StudioTab } from "./types/studio";

const PROJECT_TABS: StudioTab[] = ["director", "script_room", "storyboard", "hypit", "backlot", "audio", "editor", "export"];

export function App() {
  const [tab, setTab] = useState<StudioTab>("dashboard");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [engines, setEngines] = useState<Record<string, unknown> | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [storageUsedMb, setStorageUsedMb] = useState(0);
  const [activeProject, setActiveProject] = useState<ProjectDetail | null>(null);
  const [liveEvents, setLiveEvents] = useState<Array<Record<string, unknown>>>([]);
  const [banner, setBanner] = useState<{ kind: "info" | "error"; text: string } | null>(null);
  const [voiceOpen, setVoiceOpen] = useState(false);

  const anyRunning = projects.some((p) => p.status === "running");
  const activeId = activeProject?.project.id;
  const activeRunning = activeProject?.project.status === "running";

  const refreshGlobals = useCallback(async () => {
    try {
      const [h, e, p] = await Promise.all([studioClient.health(), studioClient.engines(), studioClient.listProjects()]);
      setHealth(h); setEngines(e); setProjects(p.projects); setStorageUsedMb(p.storage_used_mb);
    } catch { /* backend still booting; the sidebar shows the engine as starting */ }
  }, []);

  const refreshActiveProject = useCallback(async (id: string) => {
    setActiveProject(await studioClient.getProject(id));
  }, []);

  // Surface failures instead of leaving the user with a button that silently did nothing.
  const act = useCallback(async (fn: () => Promise<unknown>, success?: string) => {
    try {
      await fn();
      if (success) setBanner({ kind: "info", text: success });
    } catch (err) {
      setBanner({ kind: "error", text: err instanceof Error ? err.message : String(err) });
    }
  }, []);

  useEffect(() => {
    refreshGlobals();
    const timer = setInterval(refreshGlobals, anyRunning ? 3000 : 10000);
    return () => clearInterval(timer);
  }, [refreshGlobals, anyRunning]);

  useEffect(() => {
    if (!activeId) return;
    const es = new EventSource(`${API_BASE}/api/projects/${activeId}/events`);
    es.onmessage = (ev) => {
      try {
        const parsed = JSON.parse(ev.data);
        if (parsed.type !== "heartbeat") {
          setLiveEvents((prev) => [parsed, ...prev].slice(0, 50));
          refreshActiveProject(activeId).catch(() => undefined);
        }
      } catch { /* ignore malformed event */ }
    };
    return () => es.close();
  }, [activeId, refreshActiveProject]);

  // Fallback so progress keeps moving even if the event stream drops mid-run.
  useEffect(() => {
    if (!activeId || !activeRunning) return;
    const t = setInterval(() => refreshActiveProject(activeId).catch(() => undefined), 4000);
    return () => clearInterval(t);
  }, [activeId, activeRunning, refreshActiveProject]);

  const openProject = async (id: string) => {
    setLiveEvents([]);
    const detail = await studioClient.getProject(id);
    setActiveProject(detail);
    setTab(isIdle(detail.project.status) ? "script_room" : "backlot");
  };

  const handleCreateProject = async (payload: Record<string, unknown>, runImmediately: boolean, refFiles?: PendingRefUpload[]) => {
    let created = await studioClient.createProject(payload);
    setLiveEvents([]);
    if (refFiles && refFiles.length > 0) {
      for (const rf of refFiles) {
        await studioClient.uploadReferenceFile(created.project.id, rf.file, rf.role, rf.userNotes);
      }
      await studioClient.analyzeReferences(created.project.id);
      created = await studioClient.getProject(created.project.id);
    }
    setActiveProject(created);
    await refreshGlobals();
    if (runImmediately) {
      await studioClient.runProject(created.project.id, false);
      await refreshActiveProject(created.project.id);
      setTab("backlot");
    } else {
      setTab("script_room");
    }
  };

  const handleVoiceCommand = async (transcript: string) => {
    const pid = activeProject?.project.id;
    const res = await studioClient.voiceCommand(transcript, pid, false);
    let reply = res;
    if (res.requires_confirmation) {
      if (!window.confirm(String(res.message || "This command changes or deletes work. Run it?"))) return;
      reply = await studioClient.voiceCommand(transcript, pid, true);
    }
    setBanner({ kind: "info", text: String((reply.result as Record<string, unknown>)?.reply || "Command done.") });
    await refreshGlobals();
    if (pid) await refreshActiveProject(pid);
  };

  const pid = activeProject?.project.id ?? "";
  const refresh = () => refreshActiveProject(pid);
  const inProject = PROJECT_TABS.includes(tab) && Boolean(activeProject);
  const view: StudioTab = !inProject && PROJECT_TABS.includes(tab) ? "dashboard" : tab;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar activeTab={view} onSelectTab={setTab} engineOnline={Boolean(health)} onVoiceCommand={() => setVoiceOpen(true)} />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto px-8 py-7">
          {banner && (
            <div role={banner.kind === "error" ? "alert" : "status"} className={`mb-5 px-4 py-2.5 rounded-lg text-[13px] flex items-center justify-between gap-4 border ${banner.kind === "error" ? "bg-live-soft border-live/40 text-live" : "bg-done-soft border-done/30 text-done"}`}>
              <span className="min-w-0 break-words">{banner.text}</span>
              <button onClick={() => setBanner(null)} className="font-semibold underline shrink-0">Dismiss</button>
            </div>
          )}
          {view === "dashboard" && (
            <DashboardView
              health={health} engines={engines} projects={projects} storageUsedMb={storageUsedMb}
              onOpenProject={(id) => act(() => openProject(id))}
              onNewProject={() => setTab("new_project")}
              onRefreshProjects={refreshGlobals}
              onError={(text) => setBanner({ kind: "error", text })}
            />
          )}
          {view === "new_project" && <NewProjectView onCreate={(p, run, refFiles) => handleCreateProject(p, run, refFiles).catch((err) => { setBanner({ kind: "error", text: err instanceof Error ? err.message : String(err) }); })} />}
          {inProject && activeProject && (
            <>
              <ProjectHeader project={activeProject} tab={tab} onSelectTab={setTab} onBack={() => setTab("dashboard")} />
              {tab === "director" && <DirectorChatView project={activeProject} onSendMessage={async (msg, confirmed) => { const r = await studioClient.chatDirector(pid, msg, "text", confirmed); await refresh(); return r; }} />}
              {tab === "script_room" && <ScriptRoomView project={activeProject} onRefresh={refresh} onStartProduction={() => act(async () => { await studioClient.runProject(pid, false); await refresh(); setTab("backlot"); })} />}
              {tab === "storyboard" && <StoryboardView project={activeProject} onRefresh={refresh} onRegenerateScene={(sceneId, visualStyle, renderEngine) => act(async () => { await studioClient.regenerateScene(pid, { scene_id: sceneId, ...(visualStyle ? { visual_style: visualStyle } : {}), ...(renderEngine ? { render_engine: renderEngine } : {}) }); await refresh(); }, "Scene regenerated. Your manual timeline edits were kept.")} />}
              {tab === "hypit" && <HypitStudioView project={activeProject} onRefresh={refresh} />}
              {tab === "backlot" && (
                <BacklotMonitorView
                  project={activeProject} liveEvents={liveEvents}
                  onRun={() => act(async () => { await studioClient.runProject(pid, false); await refresh(); })}
                  onPause={() => act(async () => { await studioClient.pauseProject(pid); await refresh(); })}
                  onResume={() => act(async () => { await studioClient.resumeProject(pid); await refresh(); })}
                  onGoToScript={() => setTab("script_room")}
                />
              )}
              {tab === "audio" && <AudioStudioView project={activeProject} />}
              {tab === "editor" && <TimelineEditorView project={activeProject} onTimelineOp={(op) => act(async () => { await studioClient.timelineOp(pid, op); await refresh(); })} onUndo={() => act(async () => { await studioClient.timelineUndo(pid); await refresh(); })} onRedo={() => act(async () => { await studioClient.timelineRedo(pid); await refresh(); })} />}
              {tab === "export" && <ExportCenterView project={activeProject} onExport={(body) => studioClient.exportProject(pid, body)} />}
            </>
          )}
        </div>
      </main>
      {voiceOpen && <VoiceCommandDialog onClose={() => setVoiceOpen(false)} onSubmit={(t) => act(() => handleVoiceCommand(t))} />}
    </div>
  );
}
export default App;
