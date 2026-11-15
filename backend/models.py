"""Structured Pydantic data models for Universal AI Video Production Studio."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProductionMode(str, Enum):
    AUTOMATIC = "automatic"
    PROFESSIONAL = "professional"
    FREE_OPEN_SOURCE = "free_open_source"
    HYBRID = "hybrid"


class VisualStyleProfile(str, Enum):
    AUTO = "auto"
    PIXEL_ART = "pixel_art"
    TWO_D_ILLUSTRATED = "2d_illustrated"
    THREE_D_STYLIZED = "3d_stylized"
    HAND_DRAWN_STORYBOOK = "hand_drawn_storybook"
    CUSTOM = "custom"


class ReferenceType(str, Enum):
    YOUTUBE_VIDEO = "youtube_video"
    YOUTUBE_CHANNEL = "youtube_channel"
    INSTAGRAM_POST = "instagram_post"
    INSTAGRAM_REEL = "instagram_reel"
    INSTAGRAM_PROFILE = "instagram_profile"
    WEBSITE = "website"
    DIRECT_MEDIA = "direct_media"
    UPLOADED_IMAGE = "uploaded_image"
    UPLOADED_VIDEO = "uploaded_video"
    UPLOADED_AUDIO = "uploaded_audio"
    UPLOADED_DOCUMENT = "uploaded_document"
    UNKNOWN = "unknown"


class ReferenceRole(str, Enum):
    VISUAL_STYLE = "VISUAL_STYLE"
    CHARACTER_REFERENCE = "CHARACTER_REFERENCE"
    ENVIRONMENT_REFERENCE = "ENVIRONMENT_REFERENCE"
    CAMERA_REFERENCE = "CAMERA_REFERENCE"
    ANIMATION_REFERENCE = "ANIMATION_REFERENCE"
    STORY_REFERENCE = "STORY_REFERENCE"
    FACTUAL_SOURCE = "FACTUAL_SOURCE"
    VOICE_REFERENCE = "VOICE_REFERENCE"
    MUSIC_REFERENCE = "MUSIC_REFERENCE"
    SOUND_REFERENCE = "SOUND_REFERENCE"
    BRAND_REFERENCE = "BRAND_REFERENCE"


class VideoCategory(str, Enum):
    SOCIAL_MEDIA = "social_media"
    CINEMATIC = "cinematic"
    ANIMATION = "animation"
    EDUCATIONAL = "educational"
    DOCUMENTARY = "documentary"
    COMMERCIAL = "commercial"
    AUDIO_LED = "audio_led"
    CUSTOM = "custom"


class ProductionStage(str, Enum):
    IDEA = "idea"
    RESEARCH = "research"
    CREATIVE_PROPOSAL = "creative_proposal"
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    ASSET_PLAN = "asset_plan"
    AUDIO_PLAN = "audio_plan"
    GENERATION = "generation"
    REVIEW = "review"
    EDITING = "editing"
    AUDIO_SYNC = "audio_sync"
    RENDERING = "rendering"
    QUALITY_ASSURANCE = "quality_assurance"
    DELIVERY = "delivery"


STAGE_ORDER = list(ProductionStage)


class TimelineTrackType(str, Enum):
    MAIN_VIDEO = "main_video"
    SECONDARY_VIDEO = "secondary_video"
    OVERLAY_VIDEO = "overlay_video"
    BACKGROUND = "background"
    NARRATION = "narration"
    DIALOGUE = "dialogue"
    MUSIC = "music"
    SFX = "sfx"
    AMBIENCE = "ambience"
    CAPTIONS = "captions"
    TITLES = "titles"
    GRAPHICS = "graphics"


class ProjectCreateRequest(BaseModel):
    title: str | None = None
    prompt: str = Field(..., min_length=3)
    mode: ProductionMode = ProductionMode.AUTOMATIC
    production_mode: str | None = None
    video_format: str | None = None
    visual_style: str | None = None
    voice_mode: str | None = "auto"
    target_duration_sec: float | None = Field(default=None, gt=0)
    aspect_ratio: str = "16:9"
    resolution: str = "1920x1080"
    fps: int = 30
    language: str = "en"
    subtitle_languages: list[str] = Field(default_factory=lambda: ["en"])
    preferred_render_engine: str | None = None
    uploaded_script: str | None = None
    reference_video_url: str | None = None
    references: list[dict[str, Any]] = Field(default_factory=list)
    uploads: list[dict[str, Any]] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    budget_limit_usd: float = 10.0


class DirectorChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    source: str = "text"
    confirmed_destructive: bool = False


class SceneRegenerateRequest(BaseModel):
    scene_id: str
    visual_prompt: str | None = None
    narration_text: str | None = None
    render_engine: str | None = None
    visual_style: str | None = None
    preserve_manual_edits: bool = True


class TimelineClipOp(BaseModel):
    operation: str
    clip_id: str | None = None
    track: TimelineTrackType | None = None
    scene_id: str | None = None
    asset_id: str | None = None
    label: str | None = None
    start_sec: float | None = None
    duration_sec: float | None = None
    in_point_sec: float | None = None
    split_at_sec: float | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class ExportRequest(BaseModel):
    format: str = "mp4"
    codec: str = "h264"
    resolution: str = "1920x1080"
    aspect_ratio: str = "16:9"
    fps: int = 30
    bitrate: str = "8M"
    include_subtitles: bool = True
    subtitle_languages: list[str] = Field(default_factory=lambda: ["en"])
    export_stems: bool = True
    include_chapters: bool = True


class VoiceCommandRequest(BaseModel):
    transcript: str = Field(..., min_length=1)
    project_id: str | None = None
    confirmed: bool = False


class QualityCheckItem(BaseModel):
    name: str
    category: str
    passed: bool
    severity: str = "error"
    details: str
    measured_value: Any = None
