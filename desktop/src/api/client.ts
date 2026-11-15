import type { HealthResponse, ProjectDetail, ProjectSummary, SkillOption, VideoFormatOption } from "../types/studio";

export const API_BASE =
  import.meta.env.VITE_API_BASE ||
  (typeof window !== "undefined" &&
  window.location.protocol.startsWith("http") &&
  window.location.port !== "5173"
    ? ""
    : "http://127.0.0.1:8420");

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> =
    init?.body instanceof FormData
      ? { ...((init?.headers as Record<string, string>) || {}) }
      : { "Content-Type": "application/json", ...((init?.headers as Record<string, string>) || {}) };

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) throw new Error((await res.text()) || `HTTP ${res.status}`);
  return res.json();
}

export interface ExtractedFileResult {
  ok: boolean;
  filename: string;
  extension: string;
  size_bytes: number;
  kind: string;
  extracted_text: string;
  is_structured_screenplay?: boolean;
  parsed_title?: string | null;
  parsed_subject?: string | null;
  parsed_duration_sec?: number | null;
  scene_count?: number;
  scenes?: Array<Record<string, unknown>>;
  media_info?: Record<string, unknown>;
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
  listFormats: () => req<{ formats: VideoFormatOption[] }>("/api/formats"),
  listSkills: () => req<{ skills: SkillOption[] }>("/api/skills"),
  interpretPrompt: (body: Record<string, unknown>) => req<Record<string, unknown>>("/api/intake/interpret", { method: "POST", body: JSON.stringify(body) }),
  startIntake: (prompt: string) => req<Record<string, unknown>>("/api/intake/start", { method: "POST", body: JSON.stringify({ prompt }) }),
  answerIntake: (id: string, answers: Record<string, unknown>) => req<Record<string, unknown>>(`/api/intake/${id}/answer`, { method: "POST", body: JSON.stringify(answers) }),
  getPackage: (id: string) => req<{ project_id: string; artifacts: Array<Record<string, unknown>>; approval_status: { approved: boolean; missing_gates: string[] } }>(`/api/projects/${id}/package`),
  updateArtifact: (id: string, artifactName: string, content: string) => req<Record<string, unknown>>(`/api/projects/${id}/package/${encodeURIComponent(artifactName)}`, { method: "PUT", body: JSON.stringify({ content, author: "user" }) }),
  addArtifactComment: (id: string, artifactName: string, commentText: string) => req<Record<string, unknown>>(`/api/projects/${id}/package/${encodeURIComponent(artifactName)}/comments`, { method: "POST", body: JSON.stringify({ comment_text: commentText }) }),
  approveGates: (id: string, gateName = "all") => req<Record<string, unknown>>(`/api/projects/${id}/gates/approve`, { method: "POST", body: JSON.stringify({ gate_name: gateName }) }),
  runResearch: (id: string) => req<Record<string, unknown>>(`/api/projects/${id}/research`, { method: "POST" }),
  approveScene: (projectId: string, sceneId: string, approved = true, notes = "") => req<Record<string, unknown>>(`/api/projects/${projectId}/scenes/${sceneId}/approve`, { method: "POST", body: JSON.stringify({ approved, notes }) }),
  updateVisualStyle: (projectId: string, visualStyle: string) => req<Record<string, unknown>>(`/api/projects/${projectId}/visual-style`, { method: "POST", body: JSON.stringify({ visual_style: visualStyle }) }),
  addReferenceUrl: (projectId: string, url: string, roles?: string[], userNotes?: string) => req<Record<string, unknown>>(`/api/projects/${projectId}/references/url`, { method: "POST", body: JSON.stringify({ url, roles, user_notes: userNotes }) }),
  analyzeReferences: (projectId: string) => req<Record<string, unknown>>(`/api/projects/${projectId}/references/analyze`, { method: "POST" }),
  uploadReferenceFile: (projectId: string, file: File, roles = "visual_style", userNotes = "") => {
    const fd = new FormData();
    fd.append("file", file);
    return req<Record<string, unknown>>(`/api/projects/${projectId}/references/upload?intended_role=${encodeURIComponent(roles.split(",")[0] || "visual_style")}&roles=${encodeURIComponent(roles)}&user_notes=${encodeURIComponent(userNotes)}`, { method: "POST", body: fd });
  },
  extractFile: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return req<ExtractedFileResult>("/api/files/extract", { method: "POST", body: fd });
  },
  uploadProjectFile: (projectId: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return req<Record<string, unknown>>(`/api/projects/${projectId}/upload`, { method: "POST", body: fd });
  },
  hypitAuthor: (script: string) => req<Record<string, unknown>>("/api/v1/hypit/author", { method: "POST", body: JSON.stringify({ script }) }),
  hypitCloneReference: (referenceVideo: string, prompt: string, durationSec?: number) =>
    req<Record<string, unknown>>("/api/v1/hypit/clone-reference", {
      method: "POST",
      body: JSON.stringify({ reference_video: referenceVideo, prompt, target_duration_sec: durationSec }),
    }),
  hypitVariants: (projectId: string, variants: Array<Record<string, unknown>>) =>
    req<Record<string, unknown>>("/api/v1/hypit/variants", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, variants }),
    }),
};
