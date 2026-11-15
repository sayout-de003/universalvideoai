export type StudioTab =
  | "dashboard" | "new_project" | "director" | "script_room" | "storyboard"
  | "hypit" | "backlot" | "audio" | "editor" | "export";

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
  pipeline_name: string; render_engine: string; visual_style?: string;
  production_mode_policy?: string; target_duration_sec: number;
  aspect_ratio: string; resolution: string; fps: number; status: string;
  current_stage: string; estimated_cost_usd: number; actual_cost_usd: number;
  created_at: string; updated_at: string;
  scenes_total?: number; scenes_done?: number;
}

export interface ReferenceAssetItem {
  id: string;
  project_id: string;
  asset_type: string;
  source_type?: string;
  source_url?: string;
  access_status?: string;
  analysis_status?: string;
  file_path: string;
  intended_role: string;
  roles?: string[];
  limitations?: string[];
  attribution?: Record<string, unknown>;
  user_notes?: string;
  analysis?: Record<string, unknown>;
}

export interface BlenderSettings {
  engine?: "auto" | "EEVEE" | "CYCLES" | "WORKBENCH";
  environment?: "room" | "outdoor" | "cyberpunk" | "isometric" | "minimal";
  lighting?: "three_point" | "film_noir" | "golden_hour" | "neon" | "softbox";
  camera_motion?: "push_in" | "orbit" | "pan" | "crane" | "static";
  animation?: "walk" | "run" | "idle" | "talk";
  character_mesh_path?: string;
  samples?: number;
  lip_sync?: boolean;
}

export interface SkillOption {
  id: string;
  name: string;
  tagline: string;
  category: "3d" | "code_art" | "motion_graphics" | "pacing" | "audio" | "style" | "animation" | string;
  technology?: string;
  installed?: boolean;
  ready?: boolean;
  source?: "claude_animation" | "studio_core";
  formats?: string[];
  recommendedWith?: string[];
}

export interface VideoFormatOption {
  key: string;
  label: string;
  category: string;
  writer_type: string;
  pipeline: string;
  aspect_ratio: string;
  resolution: string;
  default_duration_sec: number;
  wpm: number;
  structure?: string[];
}

export interface ProjectDetail {
  project: ProjectSummary & { workspace_dir: string; subtitle_languages: string[]; metadata?: Record<string, unknown> };
  creative_brief?: Record<string, unknown>;
  chapters: Array<{ id: string; order_index: number; title: string; summary: string; target_duration_sec: number; status: string }>;
  scenes: Array<{
    id: string; chapter_id: string; order_index: number; title: string;
    narration_segment: string; visual_description?: string; generation_prompt: string;
    render_engine: string; visual_style?: string; provider?: string;
    duration_sec: number; transition: string; quality_status: string; approved: number;
  }>;
  shots: Array<{ id: string; scene_id: string; shot_type: string; camera_angle: string; camera_movement: string; lighting: string }>;
  characters: Array<{ id: string; name: string; role: string; visual_description: string; voice_id: string }>;
  speakers: Array<{ id: string; name: string; role: string; voice_provider: string; voice_id: string; language: string }>;
  assets: Array<{ id: string; scene_id?: string; asset_type: string; provider: string; file_path: string; duration_sec?: number; license: string }>;
  reference_assets?: ReferenceAssetItem[];
  research_sources?: Array<Record<string, unknown>>;
  research_claims?: Array<Record<string, unknown>>;
  timeline: Array<{ id: string; track: string; scene_id?: string; label: string; start_sec: number; duration_sec: number; in_point_sec: number; manual_edited: number; properties?: Record<string, unknown> }>;
  checkpoints: Array<{ id: string; stage: string; status: string; created_at: string }>;
  qa_reports: Array<{ id: string; passed: number; summary: string; checks: Array<{ name: string; category: string; passed: boolean; details: string }> }>;
  messages: Array<{ id: number; role: string; agent_name: string; content: string; created_at: string }>;
}
