import { useEffect, useMemo, useRef, useState } from "react";
import {
  Box,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  FileText,
  Film,
  Layers,
  Play,
  Plus,
  Search,
  ShieldCheck,
  Sliders,
  Sparkles,
  Trash2,
  Upload,
  Video,
  Wand2,
} from "lucide-react";
import { studioClient, type ExtractedFileResult } from "../api/client";
import type { SkillOption, VideoFormatOption } from "../types/studio";

export interface PendingRefUpload {
  file: File;
  role: string;
  userNotes: string;
}

interface Props {
  onCreate: (payload: Record<string, unknown>, runImmediately: boolean, refFiles?: PendingRefUpload[]) => Promise<void>;
}

const VISUAL_STYLES = [
  { id: "", label: "Let AI decide", note: "Matches visual style from your prompt & references" },
  { id: "anime", label: "Anime / Manga", note: "Cel-shaded characters, dramatic eyes & hair, speed lines, cinematic anime lighting" },
  { id: "cartoon_2d", label: "Classic 2D Cartoon", note: "Bold ink outlines, squash & stretch bounce, expressive cartoon eyes & gloves" },
  { id: "3d_stylized", label: "3D Stylized (Blender)", note: "Rigged 3D characters, PBR lighting, Headless Blender / Three.js" },
  { id: "2d_illustrated", label: "2D Illustrated", note: "Vector & cel-shaded character animation, HyperFrames / Remotion" },
  { id: "pixel_art", label: "Pixel Art", note: "Crisp 16-bit sprites, stepped palette, LibreSprite / Canvas" },
  { id: "hand_drawn_storybook", label: "Hand-Drawn Storybook", note: "Watercolor parchment, sketchy ink contours, OpenToonz / Canvas" },
];

const REFERENCE_ROLES = [
  { id: "visual_style", label: "Visual Style" },
  { id: "character_reference", label: "Character Design" },
  { id: "environment_reference", label: "Environment / World" },
  { id: "camera_reference", label: "Camera & Framing" },
  { id: "animation_reference", label: "Animation & Motion" },
  { id: "story_reference", label: "Story & Pacing" },
  { id: "factual_source", label: "Factual Source / Research" },
  { id: "voice_reference", label: "Voice Reference" },
  { id: "music_reference", label: "Music Reference" },
  { id: "sound_reference", label: "Sound Design" },
  { id: "brand_reference", label: "Brand / Logo" },
];

const FALLBACK_SKILLS: SkillOption[] = [
  { id: "blender", name: "Headless Blender 3D", tagline: "Rigged 3D humanoid character, PBR lighting & custom 3D sets", category: "3d", technology: "Blender EEVEE / Cycles", installed: true, ready: true, source: "studio_core" },
  { id: "animated-short-film", name: "Animated Short Film", tagline: "Painterly cinematic style-lock & shot-by-shot causal planning", category: "style", technology: "Causal Shot Planner", installed: true, ready: true, source: "studio_core" },
  { id: "lemo-opuscar", name: "Lemo-Opuscar Code Films", tagline: "99 code-driven film aesthetics (Impasto, Watercolor, Ukiyo-e, Neon)", category: "code_art", technology: "HTML5 / Shader", installed: true, ready: true, source: "studio_core" },
  { id: "anatomy", name: "Anatomy Isometric Explainer", tagline: "Isometric precision technical schematics & physical exploded teardowns", category: "3d", technology: "Isometric SVG + WebGL", installed: true, ready: true, source: "studio_core" },
  { id: "remotion", name: "Remotion Kinetic HUD", tagline: "Code-driven motion graphics, dynamic charts & animated typography", category: "motion_graphics", technology: "React + Remotion", installed: true, ready: true, source: "studio_core" },
  { id: "openmontage", name: "OpenMontage Pacing", tagline: "Fast rhythmic cuts, multi-clip speed ramps & pacing", category: "pacing", technology: "OpenMontage + FFmpeg", installed: true, ready: true, source: "studio_core" },
  { id: "voicestudio", name: "VoiceStudio & OpenWhispr", tagline: "Dual neural conversational actors & word-level subtitle sync", category: "audio", technology: "Edge TTS + OpenWhispr", installed: true, ready: true, source: "studio_core" },
  { id: "hyperframes", name: "HyperFrames Vector Cel", tagline: "2D character animation & multiplane depth parallax", category: "motion_graphics", technology: "SVG + Multiplane", installed: true, ready: true, source: "studio_core" },
  { id: "hypit", name: "Hypit Semantic Composition", tagline: "Narrative semantic timeline alignment & adaptive beat ranking", category: "pacing", technology: "Semantic Beat Engine", installed: true, ready: true, source: "studio_core" },
  { id: "handdraw-skill", name: "HandDraw Skill", tagline: "Deterministic hand-drawn whiteboard animation via SVG, Remotion & Edge TTS", category: "animation", technology: "SVG + Remotion", installed: true, ready: true, source: "claude_animation" },
  { id: "claude-animation-base", name: "Claude Animation Base", tagline: "Hand-painted cartoon character acting with p5.brush & Clawd (31 emotions)", category: "animation", technology: "p5.js + p5.brush", installed: true, ready: true, source: "claude_animation" },
  { id: "claude-drawing-skill", name: "Claude Drawing Skill", tagline: "Procedural illustration in 83 artistic styles (ink wash, watercolor, ukiyo-e)", category: "animation", technology: "NumPy + Pillow CPU", installed: true, ready: true, source: "claude_animation" },
  { id: "anidoodle", name: "AniDoodle", tagline: "Code-drawn films & interactive animations in 32 styles with acoustic scores", category: "animation", technology: "Canvas / WebGL", installed: true, ready: true, source: "claude_animation" },
  { id: "motion-skill", name: "Motion Skill", tagline: "Retro collage animated video pipeline with paper textures & halftone cutouts", category: "animation", technology: "Prompt Compiler", installed: true, ready: true, source: "claude_animation" },
  { id: "motion-design", name: "Motion Design Skill", tagline: "Timing, easing, choreography & 12 Disney animation principles linting", category: "animation", technology: "Motion Rules Engine", installed: true, ready: true, source: "claude_animation" },
  { id: "manim-skill", name: "Manim Skill", tagline: "3Blue1Brown-inspired mathematical & educational animations", category: "animation", technology: "Manim CE / Python", installed: true, ready: true, source: "claude_animation" },
  { id: "javascript-animation", name: "JavaScript Animation Skills", tagline: "Zero-asset hand-drawn canvas films with Web Audio synthesis", category: "animation", technology: "HTML5 Canvas + Web Audio", installed: true, ready: true, source: "claude_animation" },
  { id: "huashu-art-motion", name: "Huashu Art Motion", tagline: "Artistic motion synthesis with 36 art styles & 9 explainer grammars", category: "animation", technology: "Procedural Canvas / SVG", installed: true, ready: true, source: "claude_animation" },
];

const FALLBACK_FORMATS: VideoFormatOption[] = [
  { key: "instagram_reels", label: "Instagram Reels", category: "social_media", writer_type: "short_form", pipeline: "short-form", aspect_ratio: "9:16", resolution: "1080x1920", default_duration_sec: 30, wpm: 165 },
  { key: "instagram_stories", label: "Instagram Stories", category: "social_media", writer_type: "short_form", pipeline: "short-form", aspect_ratio: "9:16", resolution: "1080x1920", default_duration_sec: 15, wpm: 160 },
  { key: "youtube_shorts", label: "YouTube Shorts", category: "social_media", writer_type: "short_form", pipeline: "short-form", aspect_ratio: "9:16", resolution: "1080x1920", default_duration_sec: 45, wpm: 170 },
  { key: "youtube_longform", label: "YouTube Long-Form", category: "educational", writer_type: "documentary", pipeline: "documentary", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 300, wpm: 150 },
  { key: "cinematic_trailers", label: "Cinematic Trailers", category: "cinematic", writer_type: "fiction", pipeline: "cinematic", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 60, wpm: 120 },
  { key: "short_films", label: "Short Films", category: "cinematic", writer_type: "fiction", pipeline: "cinematic", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 180, wpm: 130 },
  { key: "feature_films", label: "Feature-Length Films", category: "cinematic", writer_type: "fiction", pipeline: "cinematic", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 600, wpm: 130 },
  { key: "documentaries", label: "Documentaries", category: "documentary", writer_type: "documentary", pipeline: "documentary", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 180, wpm: 145 },
  { key: "historical_documentaries", label: "Historical Documentaries", category: "documentary", writer_type: "documentary", pipeline: "documentary", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 240, wpm: 140 },
  { key: "investigative_documentaries", label: "Investigative Documentaries", category: "documentary", writer_type: "documentary", pipeline: "documentary", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 240, wpm: 145 },
  { key: "advertisements", label: "Advertisements & Commercials", category: "commercial", writer_type: "commercial", pipeline: "commercial", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 30, wpm: 155 },
  { key: "product_launch_films", label: "Product Launch Films", category: "commercial", writer_type: "commercial", pipeline: "commercial", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 60, wpm: 150 },
  { key: "corporate_films", label: "Corporate Films", category: "commercial", writer_type: "commercial", pipeline: "commercial", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 90, wpm: 145 },
  { key: "brand_films", label: "Brand Films", category: "commercial", writer_type: "commercial", pipeline: "commercial", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 90, wpm: 135 },
  { key: "saas_explainers", label: "SaaS & Software Explainers", category: "educational", writer_type: "commercial", pipeline: "animated-explainer", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 75, wpm: 155 },
  { key: "educational_videos", label: "Educational Videos", category: "educational", writer_type: "documentary", pipeline: "animated-explainer", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 120, wpm: 145 },
  { key: "tutorials_demos", label: "Tutorials & Demonstrations", category: "educational", writer_type: "commercial", pipeline: "animated-explainer", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 120, wpm: 145 },
  { key: "interviews_podcasts", label: "Interviews & Podcasts", category: "audio_led", writer_type: "documentary", pipeline: "podcast-repurpose", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 180, wpm: 155 },
  { key: "music_videos", label: "Music Videos", category: "music_video", writer_type: "fiction", pipeline: "music-video", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 150, wpm: 110 },
  { key: "animation_motion_graphics", label: "Animation & Motion Graphics", category: "animation", writer_type: "fiction", pipeline: "animated-explainer", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 60, wpm: 145 },
  { key: "fictional_storytelling", label: "Fictional Storytelling", category: "cinematic", writer_type: "fiction", pipeline: "cinematic", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 120, wpm: 135 },
  { key: "travel_films", label: "Travel Films", category: "documentary", writer_type: "documentary", pipeline: "documentary", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 120, wpm: 130 },
  { key: "news_explainers", label: "News & Current-Affairs Explainers", category: "documentary", writer_type: "documentary", pipeline: "news-explainer", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 90, wpm: 160 },
  { key: "user_footage_editing", label: "User-Footage-Based Editing", category: "custom", writer_type: "documentary", pipeline: "hybrid", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 90, wpm: 145 },
  { key: "hybrid_live_ai", label: "Hybrid Live-Action & AI Productions", category: "custom", writer_type: "fiction", pipeline: "hybrid", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 90, wpm: 140 },
  { key: "handdrawn_whiteboard", label: "Hand-Drawn Whiteboard Explainer", category: "animation", writer_type: "handdrawn_explainer", pipeline: "handdraw-svg", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 60, wpm: 150 },
  { key: "character_p5_cartoon", label: "Hand-Painted Cartoon (p5.brush Clawd)", category: "animation", writer_type: "fiction", pipeline: "p5-brush-cartoon", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 45, wpm: 135 },
  { key: "procedural_art_drawing", label: "Procedural Art Drawing (83 Styles)", category: "animation", writer_type: "documentary", pipeline: "claude-drawing", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 45, wpm: 140 },
  { key: "anidoodle_code_film", label: "AniDoodle Code Art Film", category: "animation", writer_type: "fiction", pipeline: "anidoodle", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 60, wpm: 130 },
  { key: "retro_collage_motion", label: "Retro Collage Animated Motion", category: "animation", writer_type: "short_form", pipeline: "motion-skill-collage", aspect_ratio: "9:16", resolution: "1080x1920", default_duration_sec: 30, wpm: 155 },
  { key: "manim_math_explainer", label: "Manim Mathematical Animation (3Blue1Brown)", category: "educational", writer_type: "documentary", pipeline: "manim-ce", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 90, wpm: 140 },
  { key: "javascript_canvas_story", label: "JavaScript Canvas Zero-Asset Film", category: "animation", writer_type: "fiction", pipeline: "js-canvas-film", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 60, wpm: 135 },
  { key: "huashu_art_motion", label: "Huashu Artistic Motion", category: "animation", writer_type: "documentary", pipeline: "huashu-motion", aspect_ratio: "16:9", resolution: "1920x1080", default_duration_sec: 60, wpm: 140 },
];

const BLENDER_ENGINES = [
  { id: "auto", label: "Auto (EEVEE-Next with Cycles fallback)" },
  { id: "EEVEE", label: "EEVEE-Next (Real-time PBR, Ultra Fast)" },
  { id: "CYCLES", label: "Cycles (Photorealistic Ray-Tracing / Global Illumination)" },
  { id: "WORKBENCH", label: "Workbench (Clean Technical Clay Draft)" },
];

const BLENDER_ENVIRONMENTS = [
  { id: "room", label: "Studio Room (Architectural walls & pillars)" },
  { id: "outdoor", label: "Outdoor Nature (Stylized trees & landscape)" },
  { id: "cyberpunk", label: "Cyberpunk Corridor (Neon strips & dark metallic)" },
  { id: "isometric", label: "Isometric Stage (Elevated platform & grid)" },
  { id: "minimal", label: "Minimal Void (Clean infinite studio cyclorama)" },
];

const BLENDER_LIGHTING = [
  { id: "three_point", label: "3-Point Studio Pro (Key, Fill, Rim)" },
  { id: "film_noir", label: "Cinematic Film Noir (High contrast moody spot)" },
  { id: "golden_hour", label: "Golden Hour Sun (Warm low-angle sun)" },
  { id: "neon", label: "Cyberpunk Neon (Cyan & Magenta dual-tone)" },
  { id: "softbox", label: "High-Key Softbox (Evenly diffused softbox)" },
];

const BLENDER_CAMERAS = [
  { id: "push_in", label: "Cinematic Dolly Push-In" },
  { id: "orbit", label: "Tracking Arc / Orbit" },
  { id: "pan", label: "Horizontal Tracking Pan" },
  { id: "crane", label: "Ascending Crane / Low Angle" },
  { id: "static", label: "Static Hero Framing" },
];

const BLENDER_ANIMATIONS = [
  { id: "walk", label: "Walk Cycle across set" },
  { id: "run", label: "Sprint / Run" },
  { id: "idle", label: "Hero Idle Stance" },
  { id: "talk", label: "Talking & Conversational Gestures" },
];

const PACING_OPTIONS = [
  { id: "fast", label: "Fast & Dynamic (~2-3s / shot)", secPerShot: 2.5 },
  { id: "balanced", label: "Balanced Narrative (~4-6s / shot)", secPerShot: 5.0 },
  { id: "cinematic", label: "Cinematic Slow Paced (~7-10s / shot)", secPerShot: 8.0 },
];

const LENGTH_PRESETS = [
  { label: "Let AI decide", sec: "" },
  { label: "15s Short", sec: "15" },
  { label: "30s Ad", sec: "30" },
  { label: "60s Reel", sec: "60" },
  { label: "2 min Explainer", sec: "120" },
  { label: "5 min Story", sec: "300" },
  { label: "10 min Deep Dive", sec: "600" },
];

const SHAPES = [
  { id: "16:9", label: "Widescreen 16:9", note: "YouTube / Cinema", res: "1920x1080" },
  { id: "9:16", label: "Vertical 9:16", note: "Shorts / Reels / TikTok", res: "1080x1920" },
  { id: "1:1", label: "Square 1:1", note: "Instagram / Feed", res: "1080x1080" },
  { id: "2.39:1", label: "Anamorphic 2.39:1", note: "Hollywood Cinema", res: "2560x1080" },
  { id: "4:5", label: "Portrait 4:5", note: "Social Portrait Feed", res: "1080x1350" },
];

const RESOLUTIONS = [
  { id: "1280x720", label: "720p HD (Draft / Fast)" },
  { id: "1920x1080", label: "1080p Full HD (Standard)" },
  { id: "2560x1440", label: "1440p 2K (Crisp)" },
  { id: "3840x2160", label: "4K UHD (Master)" },
];

const FRAME_RATES = [
  { id: 24, label: "24 fps (Hollywood Cinema)" },
  { id: 30, label: "30 fps (Web & Social Standard)" },
  { id: 60, label: "60 fps (Ultra Smooth Motion)" },
];

const COLOR_GRADES = [
  { id: "natural", label: "Natural / Neutral" },
  { id: "teal_orange", label: "Cinematic Teal & Orange" },
  { id: "film_noir", label: "Moody Film Noir B&W" },
  { id: "vibrant_anime", label: "Vibrant Anime" },
  { id: "vintage_warm", label: "Vintage Warm Film" },
];

const VOICES = [
  { id: "auto", label: "Let AI decide (Dual Human Male + Female Neural Voices)" },
  { id: "dual", label: "Dual Male & Female Conversational Voices" },
  { id: "male", label: "Male Human Voice Only (ChristopherNeural / GuyNeural)" },
  { id: "female", label: "Female Human Voice Only (AriaNeural / JennyNeural)" },
];

const ENGINES = [
  { id: "", label: "Let AI decide (Pixar 2D/3D + Remotion Motion Graphics + xfade)" },
  { id: "blender", label: "3D Rigged Character Animation (Headless Blender)" },
  { id: "hyperframes", label: "Pixar 2D/3D Character & Parallax Animation (HyperFrames)" },
  { id: "remotion", label: "Kinetic Motion Graphics & Data HUD (Remotion)" },
  { id: "threejs", label: "3D WebGL Scenes (Three.js)" },
  { id: "libresprite", label: "Pixel Art Sprite & Tilemap Pipeline (LibreSprite / Canvas)" },
  { id: "opentoonz", label: "Hand-Drawn Storybook & Watercolor Pipeline (OpenToonz / Canvas)" },
  { id: "ffmpeg", label: "Cinematic Slideshow & Footage (FFmpeg)" },
];

export function NewProjectView({ onCreate }: Props) {
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [availableFormats, setAvailableFormats] = useState<VideoFormatOption[]>(FALLBACK_FORMATS);
  const [availableSkills, setAvailableSkills] = useState<SkillOption[]>(FALLBACK_SKILLS);
  const [selectedFormats, setSelectedFormats] = useState<string[]>([]);
  const [formatCategoryFilter, setFormatCategoryFilter] = useState<string>("all");
  const [formatSearch, setFormatSearch] = useState("");
  const [skillFilter, setSkillFilter] = useState<string>("all");
  const [skillSearch, setSkillSearch] = useState("");
  const [visualStyle, setVisualStyle] = useState("");
  const [productionMode, setProductionMode] = useState<"free_open_source" | "hybrid" | "professional">("free_open_source");
  const [voiceMode, setVoiceMode] = useState("auto");
  const [shape, setShape] = useState(SHAPES[0]);

  useEffect(() => {
    let active = true;
    studioClient.listFormats().then((res) => {
      if (active && Array.isArray(res.formats) && res.formats.length > 0) {
        setAvailableFormats(res.formats);
      }
    }).catch(() => {});
    studioClient.listSkills().then((res) => {
      if (active && Array.isArray(res.skills) && res.skills.length > 0) {
        setAvailableSkills(res.skills);
      }
    }).catch(() => {});
    return () => { active = false; };
  }, []);

  // Duration & Pacing
  const [lengthSec, setLengthSec] = useState("");
  const [durationInputVal, setDurationInputVal] = useState("");
  const [durationUnit, setDurationUnit] = useState<"sec" | "min">("sec");
  const [pacing, setPacing] = useState<"fast" | "balanced" | "cinematic">("balanced");

  // Multi-Skill Orchestration
  const [selectedSkills, setSelectedSkills] = useState<string[]>(["blender", "remotion"]);

  // Blender 3D Studio Settings
  const [blenderEngine, setBlenderEngine] = useState<"auto" | "EEVEE" | "CYCLES" | "WORKBENCH">("auto");
  const [blenderEnv, setBlenderEnv] = useState<"room" | "outdoor" | "cyberpunk" | "isometric" | "minimal">("room");
  const [blenderLight, setBlenderLight] = useState<"three_point" | "film_noir" | "golden_hour" | "neon" | "softbox">("three_point");
  const [blenderCamera, setBlenderCamera] = useState<"push_in" | "orbit" | "pan" | "crane" | "static">("push_in");
  const [blenderAnim, setBlenderAnim] = useState<"walk" | "run" | "idle" | "talk">("walk");
  const [blenderMeshPath, setBlenderMeshPath] = useState("");
  const [blenderSamples, setBlenderSamples] = useState(32);
  const [blenderLipSync, setBlenderLipSync] = useState(true);

  // Advanced Cinematic Output Settings
  const [resolution, setResolution] = useState(SHAPES[0].res);
  const [fps, setFps] = useState(30);
  const [colorGrade, setColorGrade] = useState("natural");
  const [qualityPreset, setQualityPreset] = useState<"draft" | "high" | "master">("high");

  const [more, setMore] = useState(true);
  const [mode, setMode] = useState<"automatic" | "professional">("automatic");
  const [language, setLanguage] = useState("en");
  const [subLangs, setSubLangs] = useState("en");
  const [uploadedScript, setUploadedScript] = useState("");
  const [refUrl, setRefUrl] = useState("");
  const [refRole, setRefRole] = useState("visual_style");
  const [refNotes, setRefNotes] = useState("");
  const [refLinks, setRefLinks] = useState<Array<{ url: string; role: string; user_notes: string }>>([]);
  const [refFiles, setRefFiles] = useState<PendingRefUpload[]>([]);
  const [refFileRole, setRefFileRole] = useState("visual_style");
  const [refFileNotes, setRefFileNotes] = useState("");
  const [engine, setEngine] = useState("");
  const [loading, setLoading] = useState<"plan" | "run" | "interpret" | null>(null);
  const [briefPreview, setBriefPreview] = useState<Record<string, unknown> | null>(null);
  const [fileBusy, setFileBusy] = useState(false);
  const [fileInfo, setFileInfo] = useState<ExtractedFileResult | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const refMediaInputRef = useRef<HTMLInputElement | null>(null);

  // Toggle video formats in multi-select
  const toggleFormat = (formatKey: string) => {
    setSelectedFormats((prev) =>
      prev.includes(formatKey) ? prev.filter((f) => f !== formatKey) : [...prev, formatKey]
    );
  };

  // Toggle skills in multi-select
  const toggleSkill = (skillId: string) => {
    setSelectedSkills((prev) =>
      prev.includes(skillId) ? prev.filter((s) => s !== skillId) : [...prev, skillId]
    );
  };

  const formatCategories = useMemo(() => {
    const cats = Array.from(new Set(availableFormats.map((f) => f.category)));
    return ["all", ...cats];
  }, [availableFormats]);

  const filteredFormats = useMemo(() => {
    const q = formatSearch.trim().toLowerCase();
    return availableFormats.filter((f) => {
      const catOk = formatCategoryFilter === "all" || f.category === formatCategoryFilter;
      const qOk = !q || f.label.toLowerCase().includes(q) || f.key.toLowerCase().includes(q) || f.category.toLowerCase().includes(q) || (f.pipeline || "").toLowerCase().includes(q);
      return catOk && qOk;
    });
  }, [availableFormats, formatCategoryFilter, formatSearch]);

  const filteredSkills = useMemo(() => {
    const q = skillSearch.trim().toLowerCase();
    return availableSkills.filter((s) => {
      const filterOk =
        skillFilter === "all" ||
        (skillFilter === "claude_animation" && s.source === "claude_animation") ||
        (skillFilter === "studio_core" && s.source === "studio_core") ||
        s.category === skillFilter;
      const qOk = !q || s.name.toLowerCase().includes(q) || s.tagline.toLowerCase().includes(q) || (s.technology || "").toLowerCase().includes(q) || s.id.toLowerCase().includes(q);
      return filterOk && qOk;
    });
  }, [availableSkills, skillFilter, skillSearch]);

  // Sync custom duration input
  const handleDurationChange = (val: string, unit: "sec" | "min") => {
    setDurationInputVal(val);
    setDurationUnit(unit);
    const num = parseFloat(val);
    if (!isNaN(num) && num > 0) {
      const calculatedSec = unit === "min" ? Math.round(num * 60) : Math.round(num);
      setLengthSec(String(calculatedSec));
    } else if (!val) {
      setLengthSec("");
    }
  };

  // Select quick duration preset
  const selectLengthPreset = (sec: string) => {
    setLengthSec(sec);
    if (!sec) {
      setDurationInputVal("");
    } else {
      const numSec = parseInt(sec, 10);
      if (numSec >= 60 && numSec % 60 === 0) {
        setDurationInputVal(String(numSec / 60));
        setDurationUnit("min");
      } else {
        setDurationInputVal(sec);
        setDurationUnit("sec");
      }
    }
  };

  // Calculate estimated scenes
  const effectiveSec = lengthSec ? parseFloat(lengthSec) : 60;
  const currentPacingObj = PACING_OPTIONS.find((p) => p.id === pacing) || PACING_OPTIONS[1];
  const estimatedScenes = Math.max(1, Math.round(effectiveSec / currentPacingObj.secPerShot));

  const addRefLink = () => {
    const trimmed = refUrl.trim();
    if (!trimmed) return;
    setRefLinks((prev) => [...prev, { url: trimmed, role: refRole, user_notes: refNotes.trim() }]);
    setRefUrl("");
    setRefNotes("");
  };

  const addRefFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const next: PendingRefUpload[] = [];
    Array.from(files).forEach((f) => {
      next.push({ file: f, role: refFileRole, userNotes: refFileNotes.trim() });
    });
    setRefFiles((prev) => [...prev, ...next]);
    setRefFileNotes("");
  };

  const handleInterpret = async () => {
    const effectivePrompt = prompt.trim() || uploadedScript.trim();
    if (!effectivePrompt) return;
    setLoading("interpret");
    try {
      const allRefs = [
        ...refLinks.map((r) => ({ url: r.url, roles: [r.role], user_notes: r.user_notes })),
        ...(refUrl.trim() ? [{ url: refUrl.trim(), roles: [refRole], user_notes: refNotes.trim() }] : []),
      ];
      const res = await studioClient.interpretPrompt({
        prompt: effectivePrompt,
        production_mode: productionMode,
        preferences: {
          video_format: selectedFormats[0] || undefined,
          video_formats: selectedFormats.length > 0 ? selectedFormats : undefined,
          video_type: selectedFormats[0] || undefined,
          visual_style: visualStyle || undefined,
          target_duration_sec: lengthSec ? Number(lengthSec) : undefined,
          skills: selectedSkills,
          blender_settings: {
            engine: blenderEngine,
            environment: blenderEnv,
            lighting: blenderLight,
            camera_motion: blenderCamera,
            animation: blenderAnim,
            samples: blenderSamples,
            lip_sync: blenderLipSync,
          },
          pacing,
          color_grade: colorGrade,
        },
        references: allRefs,
        uploads: refFiles.map((f) => ({ filename: f.file.name, roles: [f.role], user_notes: f.userNotes })),
      });
      setBriefPreview(res);
    } catch (err) {
      setFileError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(null);
    }
  };

  const handleFileUpload = async (file: File) => {
    setFileBusy(true);
    setFileError(null);
    try {
      const res = await studioClient.extractFile(file);
      setFileInfo(res);
      if (res.parsed_title && !title.trim()) {
        setTitle(res.parsed_title);
      }
      if (res.parsed_duration_sec && !lengthSec) {
        selectLengthPreset(String(Math.round(res.parsed_duration_sec)));
      }
      if (res.extracted_text) {
        setUploadedScript(res.extracted_text);
        if (!prompt.trim()) {
          setPrompt(
            res.parsed_title
              ? `${res.parsed_title} — ${res.parsed_subject || "Cinematic production from uploaded file"}`
              : res.extracted_text.slice(0, 600)
          );
        }
      }
    } catch (err) {
      try {
        const rawText = await file.text();
        setUploadedScript(rawText);
        if (!prompt.trim()) setPrompt(rawText.slice(0, 600));
        setFileInfo({
          ok: true,
          filename: file.name,
          extension: file.name.split(".").pop() || "",
          size_bytes: file.size,
          kind: "text_fallback",
          extracted_text: rawText,
        });
      } catch {
        setFileError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setFileBusy(false);
    }
  };

  const submit = async (runNow: boolean) => {
    const effectivePrompt = prompt.trim() || uploadedScript.trim();
    if (!effectivePrompt) return;
    setLoading(runNow ? "run" : "plan");
    try {
      const allRefs = [
        ...refLinks.map((r) => ({ url: r.url, roles: [r.role], user_notes: r.user_notes })),
        ...(refUrl.trim() ? [{ url: refUrl.trim(), roles: [refRole], user_notes: refNotes.trim() }] : []),
      ];

      await onCreate(
        {
          title: title.trim() || null,
          prompt: effectivePrompt,
          mode,
          production_mode: productionMode,
          video_format: selectedFormats[0] || null,
          video_formats: selectedFormats,
          video_type: selectedFormats[0] || null,
          visual_style: visualStyle || null,
          voice_mode: voiceMode || "auto",
          aspect_ratio: shape.id,
          resolution: resolution || shape.res,
          fps,
          target_duration_sec: lengthSec ? Number(lengthSec) : null,
          language,
          subtitle_languages: subLangs.split(",").map((s) => s.trim()).filter(Boolean),
          uploaded_script: uploadedScript.trim() || null,
          reference_video_url: refUrl.trim() || null,
          references: allRefs,
          preferred_render_engine: engine || null,
          skills: selectedSkills,
          blender_settings: {
            engine: blenderEngine,
            environment: blenderEnv,
            lighting: blenderLight,
            camera_motion: blenderCamera,
            animation: blenderAnim,
            character_mesh_path: blenderMeshPath.trim() || undefined,
            samples: blenderSamples,
            lip_sync: blenderLipSync,
          },
          pacing,
          color_grade: colorGrade,
          quality_preset: qualityPreset,
        },
        runNow,
        refFiles
      );
    } finally {
      setLoading(null);
    }
  };

  const isBlenderActive = selectedSkills.includes("blender") || engine === "blender" || visualStyle === "3d_stylized";

  return (
    <div className="max-w-4xl space-y-7">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">New video production</h1>
        <p className="text-slate mt-1">
          Configure advanced Blender 3D, multi-skill orchestration, duration, pacing, and visual delivery settings — or let the AI Director orchestrate automatically.
        </p>
      </div>

      <div className="card p-6 space-y-6">
        {/* Title and Upload Header */}
        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3 items-end">
          <div>
            <label htmlFor="title" className="label">Project title (optional — auto-extracted if left blank)</label>
            <input
              id="title"
              className="field"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Cyberpunk Odyssey: The Quantum Frontier"
            />
          </div>
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept="*/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFileUpload(f);
              }}
            />
            <button
              type="button"
              disabled={fileBusy}
              onClick={() => fileInputRef.current?.click()}
              className="btn btn-quiet w-full"
            >
              <Upload className="w-4 h-4" /> {fileBusy ? "Reading file…" : "Upload Script / File (.pdf, .docx, .md, .srt)"}
            </button>
          </div>
        </div>

        {fileInfo && (
          <div className="rounded-lg border border-done/40 bg-done-soft px-3.5 py-2.5 text-[13px] flex flex-wrap items-center justify-between gap-2">
            <div>
              <span className="font-semibold text-done">Loaded file: {fileInfo.filename}</span>
              <span className="text-slate ml-2">
                ({fileInfo.kind}{fileInfo.scene_count ? ` · ${fileInfo.scene_count} scenes parsed` : ""}{fileInfo.parsed_duration_sec ? ` · ${fileInfo.parsed_duration_sec}s` : ""})
              </span>
            </div>
            <button
              type="button"
              onClick={() => { setFileInfo(null); setUploadedScript(""); }}
              className="text-xs underline text-slate hover:text-ink"
            >
              Clear file
            </button>
          </div>
        )}
        {fileError && (
          <div className="rounded-lg border border-live/40 bg-live-soft px-3.5 py-2 text-[13px] text-live">
            Could not read file: {fileError}
          </div>
        )}

        {/* Prompt / Screenplay */}
        <div>
          <label htmlFor="prompt" className="label">What should the video be about? (Or paste screenplay / scene outline)</label>
          <textarea
            id="prompt"
            rows={4}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            className="field text-[15px]"
            placeholder="A sci-fi action sequence with a rigged 3D hero walking through a neon cyberpunk corridor, dynamic camera tracking, dual neural voice narration, and Remotion motion graphics HUD..."
          />
        </div>

        {/* Multi-Skill Orchestration Matrix */}
        <fieldset className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <legend className="label flex items-center gap-2">
              <Layers className="w-4 h-4 text-ink" /> AI Production Skills & Animation Suite ({availableSkills.length} Available — Multi-Select)
            </legend>
            <div className="flex items-center gap-2 text-xs text-slate font-medium">
              <span className="chip text-[11px] font-mono">{selectedSkills.length} selected</span>
              <button
                type="button"
                onClick={() => {
                  const visibleIds = filteredSkills.map((s) => s.id);
                  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedSkills.includes(id));
                  if (allVisibleSelected) {
                    setSelectedSkills((prev) => prev.filter((id) => !visibleIds.includes(id)));
                  } else {
                    setSelectedSkills((prev) => Array.from(new Set([...prev, ...visibleIds])));
                  }
                }}
                className="text-xs text-accent hover:underline"
              >
                {filteredSkills.length > 0 && filteredSkills.every((s) => selectedSkills.includes(s.id)) ? "Deselect Visible" : "Select All Visible"}
              </button>
              <button
                type="button"
                onClick={() => setSelectedSkills(["blender", "remotion"])}
                className="text-xs text-slate hover:text-ink hover:underline"
              >
                Recommended
              </button>
              {selectedSkills.length > 0 && (
                <button
                  type="button"
                  onClick={() => setSelectedSkills([])}
                  className="text-xs text-slate hover:text-ink hover:underline"
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap gap-1.5">
              {[
                { id: "all", label: `All (${availableSkills.length})` },
                { id: "claude_animation", label: `Claude Animation (${availableSkills.filter((s) => s.source === "claude_animation").length})` },
                { id: "studio_core", label: `Studio Core & 3D (${availableSkills.filter((s) => s.source === "studio_core").length})` },
              ].map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setSkillFilter(tab.id)}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                    skillFilter === tab.id ? "bg-ink text-white border-ink" : "bg-panel text-slate border-rule hover:border-ink/50"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="relative min-w-[200px]">
              <Search className="w-3.5 h-3.5 text-mute absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={skillSearch}
                onChange={(e) => setSkillSearch(e.target.value)}
                placeholder="Filter skills..."
                className="field py-1 pl-8 pr-2.5 text-xs"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 max-h-[340px] overflow-y-auto pr-1">
            {filteredSkills.map((skill) => {
              const active = selectedSkills.includes(skill.id);
              return (
                <button
                  key={skill.id}
                  type="button"
                  onClick={() => toggleSkill(skill.id)}
                  aria-pressed={active}
                  className={`text-left rounded-lg border p-3 transition-all relative flex flex-col justify-between ${
                    active ? "border-ink bg-ink text-white shadow-sm" : "border-rule bg-panel hover:border-ink/50"
                  }`}
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-semibold text-[13px] leading-snug">
                        {skill.name}
                      </span>
                      <span
                        className={`w-4 h-4 shrink-0 rounded flex items-center justify-center border text-[10px] ${
                          active ? "border-white bg-white text-ink font-bold" : "border-rule text-transparent"
                        }`}
                      >
                        ✓
                      </span>
                    </div>
                    <div className={`text-xs mt-1 leading-snug line-clamp-2 ${active ? "text-[#c2cbd4]" : "text-mute"}`}>
                      {skill.tagline}
                    </div>
                  </div>
                  <div className="flex items-center justify-between gap-1.5 mt-2.5 pt-2 border-t border-current/10 text-[10px]">
                    <span className={`font-mono truncate ${active ? "text-[#d5dce3]" : "text-slate"}`}>
                      {skill.technology || skill.category}
                    </span>
                    <span className={`shrink-0 flex items-center gap-1 font-medium ${active ? "text-emerald-300" : skill.ready !== false ? "text-done" : "text-mute"}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${skill.ready !== false ? "bg-emerald-400" : "bg-slate-400"}`} />
                      {skill.ready !== false ? "Ready" : "Optional"}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </fieldset>

        {/* Dedicated Headless Blender 3D Studio Settings */}
        {isBlenderActive && (
          <div className="rounded-xl border border-accent/40 bg-sunken/60 p-4 space-y-4">
            <div className="flex items-center justify-between border-b border-rule pb-2.5">
              <div className="flex items-center gap-2">
                <Box className="w-5 h-5 text-accent" />
                <span className="font-bold text-[14px]">Headless Blender 3D Studio Configuration</span>
              </div>
              <span className="chip text-[11px] bg-accent/15 text-accent font-semibold">Active Engine</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 text-[13px]">
              <div>
                <label className="label">Render Engine</label>
                <select
                  className="field py-1.5 text-xs"
                  value={blenderEngine}
                  onChange={(e) => setBlenderEngine(e.target.value as "auto" | "EEVEE" | "CYCLES" | "WORKBENCH")}
                >
                  {BLENDER_ENGINES.map((be) => <option key={be.id} value={be.id}>{be.label}</option>)}
                </select>
              </div>

              <div>
                <label className="label">3D Environment Set</label>
                <select
                  className="field py-1.5 text-xs"
                  value={blenderEnv}
                  onChange={(e) => setBlenderEnv(e.target.value as "room" | "outdoor" | "cyberpunk" | "isometric" | "minimal")}
                >
                  {BLENDER_ENVIRONMENTS.map((env) => <option key={env.id} value={env.id}>{env.label}</option>)}
                </select>
              </div>

              <div>
                <label className="label">Lighting Preset</label>
                <select
                  className="field py-1.5 text-xs"
                  value={blenderLight}
                  onChange={(e) => setBlenderLight(e.target.value as "three_point" | "film_noir" | "golden_hour" | "neon" | "softbox")}
                >
                  {BLENDER_LIGHTING.map((bl) => <option key={bl.id} value={bl.id}>{bl.label}</option>)}
                </select>
              </div>

              <div>
                <label className="label">Camera Choreography</label>
                <select
                  className="field py-1.5 text-xs"
                  value={blenderCamera}
                  onChange={(e) => setBlenderCamera(e.target.value as "push_in" | "orbit" | "pan" | "crane" | "static")}
                >
                  {BLENDER_CAMERAS.map((cam) => <option key={cam.id} value={cam.id}>{cam.label}</option>)}
                </select>
              </div>

              <div>
                <label className="label">Character Action</label>
                <select
                  className="field py-1.5 text-xs"
                  value={blenderAnim}
                  onChange={(e) => setBlenderAnim(e.target.value as "walk" | "run" | "idle" | "talk")}
                >
                  {BLENDER_ANIMATIONS.map((an) => <option key={an.id} value={an.id}>{an.label}</option>)}
                </select>
              </div>

              <div>
                <label className="label">Render Samples ({blenderSamples} samples)</label>
                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="range"
                    min={8}
                    max={128}
                    step={8}
                    value={blenderSamples}
                    onChange={(e) => setBlenderSamples(Number(e.target.value))}
                    className="w-full accent-ink"
                  />
                  <span className="font-mono text-xs w-8 text-right">{blenderSamples}</span>
                </div>
              </div>

              <div className="md:col-span-2">
                <label className="label">Custom 3D Mesh / Rig Path (Optional .glb / .fbx / .blend)</label>
                <input
                  type="text"
                  className="field py-1.5 text-xs font-mono"
                  placeholder="e.g. media_library/characters/soldier_rigged.glb or absolute path"
                  value={blenderMeshPath}
                  onChange={(e) => setBlenderMeshPath(e.target.value)}
                />
              </div>

              <div className="flex items-center gap-2 pt-4">
                <input
                  id="lipsync"
                  type="checkbox"
                  checked={blenderLipSync}
                  onChange={(e) => setBlenderLipSync(e.target.checked)}
                  className="w-4 h-4 accent-ink rounded cursor-pointer"
                />
                <label htmlFor="lipsync" className="text-xs font-medium cursor-pointer">
                  Facial Shape-Key Lip-Sync (Viseme audio sync)
                </label>
              </div>
            </div>
          </div>
        )}

        {/* Video Creation Types / Formats (Multi-Select) */}
        <fieldset className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <legend className="label flex items-center gap-1.5">
              <Film className="w-4 h-4 text-ink" /> Video Creation Types & Formats ({availableFormats.length} Available — Multi-Select)
            </legend>
            <div className="flex items-center gap-2 text-xs text-slate font-medium">
              <span className="chip text-[11px] font-mono">
                {selectedFormats.length === 0 ? "Auto (AI Decides)" : `${selectedFormats.length} selected`}
              </span>
              <button
                type="button"
                onClick={() => {
                  const visibleKeys = filteredFormats.map((f) => f.key);
                  const allVisibleSelected = visibleKeys.length > 0 && visibleKeys.every((k) => selectedFormats.includes(k));
                  if (allVisibleSelected) {
                    setSelectedFormats((prev) => prev.filter((k) => !visibleKeys.includes(k)));
                  } else {
                    setSelectedFormats((prev) => Array.from(new Set([...prev, ...visibleKeys])));
                  }
                }}
                className="text-xs text-accent hover:underline"
              >
                {filteredFormats.length > 0 && filteredFormats.every((f) => selectedFormats.includes(f.key)) ? "Deselect Visible" : "Select All Visible"}
              </button>
              {selectedFormats.length > 0 && (
                <button
                  type="button"
                  onClick={() => setSelectedFormats([])}
                  className="text-xs text-slate hover:text-ink hover:underline"
                >
                  Let AI Decide
                </button>
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap gap-1.5">
              {formatCategories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setFormatCategoryFilter(cat)}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors capitalize ${
                    formatCategoryFilter === cat ? "bg-ink text-white border-ink" : "bg-panel text-slate border-rule hover:border-ink/50"
                  }`}
                >
                  {cat.replace(/_/g, " ")}
                </button>
              ))}
            </div>
            <div className="relative min-w-[200px]">
              <Search className="w-3.5 h-3.5 text-mute absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={formatSearch}
                onChange={(e) => setFormatSearch(e.target.value)}
                placeholder="Search video types..."
                className="field py-1 pl-8 pr-2.5 text-xs"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 max-h-[300px] overflow-y-auto pr-1">
            {filteredFormats.map((fmt) => {
              const active = selectedFormats.includes(fmt.key);
              return (
                <button
                  key={fmt.key}
                  type="button"
                  onClick={() => toggleFormat(fmt.key)}
                  aria-pressed={active}
                  className={`text-left rounded-lg border px-3 py-2.5 transition-all flex flex-col justify-between ${
                    active ? "border-ink bg-ink text-white shadow-sm" : "border-rule bg-panel hover:border-ink/50"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-semibold text-[13px] leading-snug">{fmt.label}</span>
                    <span
                      className={`w-4 h-4 shrink-0 rounded flex items-center justify-center border text-[10px] ${
                        active ? "border-white bg-white text-ink font-bold" : "border-rule text-transparent"
                      }`}
                    >
                      ✓
                    </span>
                  </div>
                  <div className={`flex items-center gap-2 mt-2 text-[10px] font-mono ${active ? "text-[#c2cbd4]" : "text-mute"}`}>
                    <span className="capitalize">{fmt.category.replace(/_/g, " ")}</span>
                    <span>·</span>
                    <span>{fmt.aspect_ratio}</span>
                    <span>·</span>
                    <span>{fmt.default_duration_sec}s</span>
                  </div>
                </button>
              );
            })}
          </div>
        </fieldset>

        {/* Human Voice Casting */}
        <div>
          <label htmlFor="voice" className="label">Human voice casting</label>
          <select id="voice" className="field" value={voiceMode} onChange={(e) => setVoiceMode(e.target.value)}>
            {VOICES.map((v) => <option key={v.id} value={v.id}>{v.label}</option>)}
          </select>
        </div>

        {/* Visual Style */}
        <fieldset>
          <legend className="label">Visual style & aesthetic direction</legend>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {VISUAL_STYLES.map((st) => (
              <button
                key={st.id || "auto"}
                type="button"
                onClick={() => setVisualStyle(st.id)}
                aria-pressed={visualStyle === st.id}
                className={`text-left rounded-lg border px-3 py-2.5 ${visualStyle === st.id ? "border-ink bg-ink text-white" : "border-rule bg-panel hover:border-ink"}`}
              >
                <div className="font-semibold text-[13px]">{st.label}</div>
                <div className={`text-xs mt-0.5 ${visualStyle === st.id ? "text-[#b9c2cb]" : "text-mute"}`}>{st.note}</div>
              </button>
            ))}
          </div>
        </fieldset>

        {/* Duration, Pacing & Time Inputs */}
        <fieldset className="space-y-3">
          <div className="flex items-center justify-between">
            <legend className="label flex items-center gap-1.5">
              <Clock className="w-4 h-4 text-ink" /> Target Duration & Shot Pacing
            </legend>
            <span className="text-xs text-slate font-medium">
              Live estimate: <strong className="text-ink">~{estimatedScenes} scenes</strong> ({effectiveSec}s total @ {currentPacingObj.secPerShot}s/shot)
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {LENGTH_PRESETS.map((l) => (
              <button
                key={l.label}
                type="button"
                onClick={() => selectLengthPreset(l.sec)}
                aria-pressed={lengthSec === l.sec}
                className={`btn text-xs py-1.5 px-3 ${lengthSec === l.sec ? "btn-primary" : "btn-quiet"}`}
              >
                {l.label}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={5}
                max={14400}
                step={durationUnit === "min" ? "0.1" : "1"}
                value={durationInputVal || (lengthSec ? (durationUnit === "min" ? (Number(lengthSec) / 60).toFixed(1) : lengthSec) : "")}
                onChange={(e) => handleDurationChange(e.target.value, durationUnit)}
                placeholder={durationUnit === "min" ? "Duration (e.g. 2.5)" : "Duration in sec (e.g. 90)"}
                className="field text-[13px]"
              />
              <div className="flex rounded-md border border-rule overflow-hidden shrink-0">
                <button
                  type="button"
                  onClick={() => handleDurationChange(durationInputVal || lengthSec, "sec")}
                  className={`px-3 py-1.5 text-xs font-semibold ${durationUnit === "sec" ? "bg-ink text-white" : "bg-panel text-slate hover:text-ink"}`}
                >
                  Sec
                </button>
                <button
                  type="button"
                  onClick={() => {
                    const secVal = lengthSec ? Number(lengthSec) : (parseFloat(durationInputVal) || 60);
                    handleDurationChange((secVal / 60).toFixed(1), "min");
                  }}
                  className={`px-3 py-1.5 text-xs font-semibold ${durationUnit === "min" ? "bg-ink text-white" : "bg-panel text-slate hover:text-ink"}`}
                >
                  Min
                </button>
              </div>
            </div>

            <div>
              <select
                className="field text-[13px]"
                value={pacing}
                onChange={(e) => setPacing(e.target.value as "fast" | "balanced" | "cinematic")}
              >
                {PACING_OPTIONS.map((po) => <option key={po.id} value={po.id}>{po.label}</option>)}
              </select>
            </div>
          </div>
        </fieldset>

        {/* Aspect Ratio Shape */}
        <fieldset>
          <legend className="label">Aspect Ratio & Framing</legend>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
            {SHAPES.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => {
                  setShape(s);
                  setResolution(s.res);
                }}
                aria-pressed={shape.id === s.id}
                className={`text-left rounded-lg border px-3 py-2 ${shape.id === s.id ? "border-ink bg-ink text-white" : "border-rule bg-panel hover:border-ink"}`}
              >
                <div className="font-semibold text-[12px]">{s.label}</div>
                <div className={`text-[11px] truncate ${shape.id === s.id ? "text-[#b9c2cb]" : "text-mute"}`}>{s.note}</div>
              </button>
            ))}
          </div>
        </fieldset>

        {/* Reference Links & Uploaded Reference Media */}
        <div className="rounded-lg border border-rule p-4 space-y-3 bg-sunken/50">
          <div className="flex items-center justify-between">
            <span className="label mb-0">Visual & Character References (URLs, Images, Clips)</span>
            <span className="text-xs text-mute font-mono">{refLinks.length + refFiles.length} attached</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[160px_1fr_1fr_auto] gap-2 items-center">
            <select className="field text-[13px]" value={refRole} onChange={(e) => setRefRole(e.target.value)}>
              {REFERENCE_ROLES.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
            </select>
            <input
              className="field text-[13px]"
              value={refUrl}
              onChange={(e) => setRefUrl(e.target.value)}
              placeholder="https://youtube.com/watch?v=… or https://instagram.com/…"
            />
            <input
              className="field text-[13px]"
              value={refNotes}
              onChange={(e) => setRefNotes(e.target.value)}
              placeholder="Notes (e.g. 'use this color palette & pacing')"
            />
            <button type="button" onClick={addRefLink} className="btn btn-quiet text-xs py-2 px-3">
              <Plus className="w-3.5 h-3.5" /> Add URL
            </button>
          </div>

          {refLinks.length > 0 && (
            <ul className="space-y-1.5">
              {refLinks.map((item, idx) => (
                <li key={idx} className="rounded border border-rule bg-panel px-3 py-1.5 text-xs flex items-center justify-between gap-2">
                  <div className="min-w-0 truncate">
                    <span className="chip mr-2">{item.role}</span>
                    <span className="font-mono text-ink">{item.url}</span>
                    {item.user_notes && <span className="text-slate ml-2">— “{item.user_notes}”</span>}
                  </div>
                  <button type="button" onClick={() => setRefLinks((prev) => prev.filter((_, i) => i !== idx))} className="text-slate hover:text-live">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="grid grid-cols-1 md:grid-cols-[160px_1fr_auto] gap-2 items-center pt-2 border-t border-rule">
            <select className="field text-[13px]" value={refFileRole} onChange={(e) => setRefFileRole(e.target.value)}>
              {REFERENCE_ROLES.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
            </select>
            <input
              className="field text-[13px]"
              value={refFileNotes}
              onChange={(e) => setRefFileNotes(e.target.value)}
              placeholder="Notes for uploaded reference files (optional)…"
            />
            <div>
              <input
                ref={refMediaInputRef}
                type="file"
                multiple
                accept="image/*,video/*,audio/*,.pdf,.docx,.txt,.md"
                className="hidden"
                onChange={(e) => addRefFiles(e.target.files)}
              />
              <button type="button" onClick={() => refMediaInputRef.current?.click()} className="btn btn-quiet text-xs py-2 px-3">
                <Upload className="w-3.5 h-3.5" /> Attach Images / Videos / Docs
              </button>
            </div>
          </div>

          {refFiles.length > 0 && (
            <ul className="space-y-1.5">
              {refFiles.map((rf, idx) => (
                <li key={idx} className="rounded border border-rule bg-panel px-3 py-1.5 text-xs flex items-center justify-between gap-2">
                  <div className="min-w-0 truncate">
                    <span className="chip mr-2">{rf.role}</span>
                    <span className="font-semibold">{rf.file.name}</span>
                    <span className="text-mute ml-1.5">({Math.round(rf.file.size / 1024)} KB)</span>
                    {rf.userNotes && <span className="text-slate ml-2">— “{rf.userNotes}”</span>}
                  </div>
                  <button type="button" onClick={() => setRefFiles((prev) => prev.filter((_, i) => i !== idx))} className="text-slate hover:text-live">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Collapsible Advanced Master Settings */}
        <div>
          <button type="button" onClick={() => setMore((v) => !v)} className="btn btn-ghost -ml-2" aria-expanded={more}>
            {more ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />} Advanced Video Delivery, Color Grade & Engine Options
          </button>
          {more && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-3 pt-3 border-t border-rule">
              <div>
                <label htmlFor="mode" className="label">Who drives?</label>
                <select id="mode" className="field" value={mode} onChange={(e) => setMode(e.target.value as "automatic" | "professional")}>
                  <option value="automatic">The AI team decides (logs reasoning live)</option>
                  <option value="professional">I want manual control at each step</option>
                </select>
              </div>

              <div>
                <label htmlFor="engine" className="label">Primary render engine override</label>
                <select id="engine" className="field" value={engine} onChange={(e) => setEngine(e.target.value)}>
                  {ENGINES.map((e) => <option key={e.id} value={e.id}>{e.label}</option>)}
                </select>
              </div>

              <div>
                <label htmlFor="res" className="label">Master Resolution</label>
                <select id="res" className="field" value={resolution} onChange={(e) => setResolution(e.target.value)}>
                  {RESOLUTIONS.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
                </select>
              </div>

              <div>
                <label htmlFor="fps" className="label">Target Frame Rate</label>
                <select id="fps" className="field" value={fps} onChange={(e) => setFps(Number(e.target.value))}>
                  {FRAME_RATES.map((fr) => <option key={fr.id} value={fr.id}>{fr.label}</option>)}
                </select>
              </div>

              <div>
                <label htmlFor="colorGrade" className="label">Color Grade / LUT Preset</label>
                <select id="colorGrade" className="field" value={colorGrade} onChange={(e) => setColorGrade(e.target.value)}>
                  {COLOR_GRADES.map((cg) => <option key={cg.id} value={cg.id}>{cg.label}</option>)}
                </select>
              </div>

              <div>
                <label htmlFor="qualityPreset" className="label">Export Quality Profile</label>
                <select id="qualityPreset" className="field" value={qualityPreset} onChange={(e) => setQualityPreset(e.target.value as "draft" | "high" | "master")}>
                  <option value="draft">Draft (Fast render, lower bitrate)</option>
                  <option value="high">High Quality (Production 10 Mbps H.264)</option>
                  <option value="master">Master ProRes / Max Bitrate</option>
                </select>
              </div>

              <div>
                <label htmlFor="lang" className="label">Narration language</label>
                <input id="lang" className="field" value={language} onChange={(e) => setLanguage(e.target.value)} placeholder="en" />
              </div>

              <div>
                <label htmlFor="subs" className="label">Subtitle languages</label>
                <input id="subs" className="field" value={subLangs} onChange={(e) => setSubLangs(e.target.value)} placeholder="en, hi" />
              </div>

              <div className="md:col-span-3">
                <label htmlFor="script" className="label">Uploaded or pasted script / screenplay content</label>
                <textarea
                  id="script"
                  rows={4}
                  className="field font-mono text-[12.5px]"
                  value={uploadedScript}
                  onChange={(e) => setUploadedScript(e.target.value)}
                  placeholder="Paste a structured # SCREENPLAY: ... or leave blank for Hollywood Screenplay Architect."
                />
              </div>
            </div>
          )}
        </div>

        <div className="rounded-lg bg-sunken px-3.5 py-2.5 text-[12.5px] text-slate flex items-start gap-2">
          <Sparkles className="w-4 h-4 text-ink shrink-0 mt-0.5" />
          <span>
            Selected skills (<strong>{selectedSkills.join(", ")}</strong>) and Blender configurations will be synthesized by the AI Director with live streaming reasoning logs in the Backlot view.
          </span>
        </div>

        {briefPreview && (
          <div className="rounded-lg border border-ink/30 bg-panel p-4 space-y-2 text-[13px]">
            <div className="font-bold flex items-center justify-between">
              <span>AI Production Summary Preview</span>
              <span className="chip text-xs">{String((briefPreview.production_summary as Record<string, unknown>)?.visual_direction || visualStyle || "Auto")}</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              <div className="p-2 rounded bg-sunken">
                <div className="text-mute">Format</div>
                <div className="font-semibold">{String((briefPreview.production_summary as Record<string, unknown>)?.format || "Auto")}</div>
              </div>
              <div className="p-2 rounded bg-sunken">
                <div className="text-mute">Duration</div>
                <div className="font-semibold">{String((briefPreview.production_summary as Record<string, unknown>)?.duration || "Auto")}</div>
              </div>
              <div className="p-2 rounded bg-sunken">
                <div className="text-mute">Visual Direction</div>
                <div className="font-semibold">{String((briefPreview.production_summary as Record<string, unknown>)?.visual_direction || "Auto")}</div>
              </div>
              <div className="p-2 rounded bg-sunken">
                <div className="text-mute">References</div>
                <div className="font-semibold">{String((briefPreview.production_summary as Record<string, unknown>)?.reference_material || "0")}</div>
              </div>
            </div>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3 pt-1 border-t border-rule">
          <button
            disabled={loading !== null || (!prompt.trim() && !uploadedScript.trim())}
            onClick={() => submit(false)}
            className="btn btn-primary mt-5"
          >
            <FileText className="w-4 h-4" /> {loading === "plan" ? "Researching & writing script…" : "Write the script first"}
          </button>
          <button
            disabled={loading !== null || (!prompt.trim() && !uploadedScript.trim())}
            onClick={() => submit(true)}
            className="btn btn-quiet mt-5"
          >
            <Play className="w-4 h-4" /> {loading === "run" ? "Starting…" : "Skip review and make the video"}
          </button>
          <button
            type="button"
            disabled={loading !== null || (!prompt.trim() && !uploadedScript.trim())}
            onClick={handleInterpret}
            className="btn btn-ghost mt-5"
          >
            <Sparkles className="w-4 h-4" /> {loading === "interpret" ? "Analyzing brief…" : "Preview AI interpretation"}
          </button>
        </div>
      </div>
    </div>
  );
}
