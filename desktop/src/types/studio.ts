export type StudioTab =
  | "dashboard" | "new_project" | "director" | "script_room" | "storyboard"
  | "backlot" | "audio" | "editor" | "export";

export interface HealthResponse {
  ok: boolean;
  app: string;
  settings: { mode: string; budget_mode: string; budget_usd: number };
  hardware: {
    os_name: string; arch: string; cpu_cores: number; ram_gb: number;
    disk_free_gb: number; disk_total_gb: number; gpu_backend: string;
    binaries: Record<string, boolean>;
  };
  credentials_configured: Record<string, boolean>;
  openmontage_available: boolean;
  openwhispr: { repo_present: boolean; bridge_online: boolean; local_whisper_cli: boolean; privacy_mode: string };
}

export interface ProjectSummary {
  id: string; title: string; prompt: string; category: string; mode: string;
  pipeline_name: string; render_engine: string; target_duration_sec: number;
  aspect_ratio: string; resolution: string; fps: number; status: string;
  current_stage: string; estimated_cost_usd: number; actual_cost_usd: number;
  created_at: string; updated_at: string;
  scenes_total?: number; scenes_done?: number;
}

export interface ProjectDetail {
  project: ProjectSummary & { workspace_dir: string; subtitle_languages: string[] };
  chapters: Array<{ id: string; order_index: number; title: string; summary: string; target_duration_sec: number; status: string }>;
  scenes: Array<{
    id: string; chapter_id: string; order_index: number; title: string;
    narration_segment: string; generation_prompt: string; render_engine: string;
    duration_sec: number; transition: string; quality_status: string; approved: number;
  }>;
  shots: Array<{ id: string; scene_id: string; shot_type: string; camera_angle: string; camera_movement: string; lighting: string }>;
  characters: Array<{ id: string; name: string; role: string; visual_description: string; voice_id: string }>;
  speakers: Array<{ id: string; name: string; role: string; voice_provider: string; voice_id: string; language: string }>;
  assets: Array<{ id: string; scene_id?: string; asset_type: string; provider: string; file_path: string; duration_sec?: number; license: string }>;
  timeline: Array<{ id: string; track: string; scene_id?: string; label: string; start_sec: number; duration_sec: number; in_point_sec: number; manual_edited: number; properties?: Record<string, unknown> }>;
  checkpoints: Array<{ id: string; stage: string; status: string; created_at: string }>;
  qa_reports: Array<{ id: string; passed: number; summary: string; checks: Array<{ name: string; category: string; passed: boolean; details: string }> }>;
  messages: Array<{ id: number; role: string; agent_name: string; content: string; created_at: string }>;
}
