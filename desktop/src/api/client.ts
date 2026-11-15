import type { HealthResponse, ProjectDetail, ProjectSummary } from "../types/studio";

export const API_BASE =
  typeof window !== "undefined" && window.location.protocol.startsWith("http")
    ? ""
    : "http://127.0.0.1:8420";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) throw new Error((await res.text()) || `HTTP ${res.status}`);
  return res.json();
}

export const studioClient = {
  health: () => req<HealthResponse>("/api/health"),
  engines: () => req<Record<string, unknown>>("/api/engines"),
  listProjects: () => req<{ projects: ProjectSummary[]; storage_used_mb: number }>("/api/projects"),
  getProject: (id: string) => req<ProjectDetail>(`/api/projects/${id}`),
  deleteProject: (id: string) => req<Record<string, unknown>>(`/api/projects/${id}`, { method: "DELETE" }),
  listProjectFiles: (id: string) => req<{ project_id: string; workspace_dir: string; folders: Record<string, Array<{ name: string; subpath: string; size_bytes: number; is_video: boolean }>> }>(`/api/projects/${id}/files`),
  deleteProjectFile: (id: string, subpath: string) => req<Record<string, unknown>>(`/api/projects/${id}/media/${subpath}`, { method: "DELETE" }),
  createProject: (body: Record<string, unknown>) => req<ProjectDetail>("/api/projects", { method: "POST", body: JSON.stringify(body) }),
  runProject: (id: string, sync = false) => req<Record<string, unknown>>(`/api/projects/${id}/run?sync=${sync}`, { method: "POST" }),
  pauseProject: (id: string) => req<Record<string, unknown>>(`/api/projects/${id}/pause`, { method: "POST" }),
  resumeProject: (id: string) => req<Record<string, unknown>>(`/api/projects/${id}/resume`, { method: "POST" }),
  regenerateScene: (id: string, body: Record<string, unknown>) => req<Record<string, unknown>>(`/api/projects/${id}/scenes/regenerate`, { method: "POST", body: JSON.stringify(body) }),
  chatDirector: (id: string, message: string, source = "text", confirmed = false) => req<Record<string, unknown>>(`/api/projects/${id}/chat`, { method: "POST", body: JSON.stringify({ message, source, confirmed_destructive: confirmed }) }),
  timelineOp: (id: string, body: Record<string, unknown>) => req<Record<string, unknown>>(`/api/projects/${id}/timeline/op`, { method: "POST", body: JSON.stringify(body) }),
  timelineUndo: (id: string) => req<Record<string, unknown>>(`/api/projects/${id}/timeline/undo`, { method: "POST" }),
  timelineRedo: (id: string) => req<Record<string, unknown>>(`/api/projects/${id}/timeline/redo`, { method: "POST" }),
  exportProject: (id: string, body: Record<string, unknown>) => req<Record<string, unknown>>(`/api/projects/${id}/export`, { method: "POST", body: JSON.stringify(body) }),
  voiceCommand: (transcript: string, projectId?: string, confirmed = false) => req<Record<string, unknown>>("/api/voice/command", { method: "POST", body: JSON.stringify({ transcript, project_id: projectId, confirmed }) }),
  listFormats: () => req<{ formats: Array<Record<string, unknown>> }>("/api/formats"),
  startIntake: (prompt: string) => req<Record<string, unknown>>("/api/intake/start", { method: "POST", body: JSON.stringify({ prompt }) }),
  answerIntake: (id: string, answers: Record<string, unknown>) => req<Record<string, unknown>>(`/api/intake/${id}/answer`, { method: "POST", body: JSON.stringify(answers) }),
  getPackage: (id: string) => req<{ project_id: string; artifacts: Array<Record<string, unknown>>; approval_status: { approved: boolean; missing_gates: string[] } }>(`/api/projects/${id}/package`),
  updateArtifact: (id: string, artifactName: string, content: string) => req<Record<string, unknown>>(`/api/projects/${id}/package/${encodeURIComponent(artifactName)}`, { method: "PUT", body: JSON.stringify({ content, author: "user" }) }),
  addArtifactComment: (id: string, artifactName: string, commentText: string) => req<Record<string, unknown>>(`/api/projects/${id}/package/${encodeURIComponent(artifactName)}/comments`, { method: "POST", body: JSON.stringify({ comment_text: commentText }) }),
  approveGates: (id: string, gateName = "all") => req<Record<string, unknown>>(`/api/projects/${id}/gates/approve`, { method: "POST", body: JSON.stringify({ gate_name: gateName }) }),
  runResearch: (id: string) => req<Record<string, unknown>>(`/api/projects/${id}/research`, { method: "POST" }),
};
