from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ThemeConfigSchema(BaseModel):
    palette: Literal["executive_navy", "emerald_slate", "obsidian_gold", "warm_editorial"] = (
        "executive_navy"
    )
    tone: Literal["executive", "analytical", "persuasive", "technical"] = "executive"
    audience: str = Field(default="Business leadership & stakeholders", max_length=200)
    include_images: bool = True


class OutlineItemInput(BaseModel):
    id: str | None = None
    title: str = Field(min_length=1, max_length=255)


class ProjectCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    doc_type: Literal["docx", "pptx"]
    main_topic: str = Field(min_length=3, max_length=4000)
    theme_config: ThemeConfigSchema = Field(default_factory=ThemeConfigSchema)
    sections: list[OutlineItemInput] = Field(default_factory=list)
    ai_outline_suggested: bool = False


class ProjectUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    main_topic: str | None = Field(default=None, min_length=3, max_length=4000)
    theme_config: ThemeConfigSchema | None = None


class OutlineUpdateRequest(BaseModel):
    sections: list[OutlineItemInput] = Field(min_length=1, max_length=30)
    ai_outline_suggested: bool | None = None


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    section_id: str
    user_id: str
    body: str
    created_at: datetime
    updated_at: datetime


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    section_id: str | None
    asset_type: str
    prompt: str
    mime_type: str
    caption: str
    width: int
    height: int
    is_active: bool
    created_at: datetime


class SectionDetailResponse(BaseModel):
    id: str
    project_id: str
    order_index: int
    title: str
    section_kind: str
    current_revision_id: str | None
    current_content_json: dict | None
    current_content_text: str
    like_status: str
    revision_count: int
    comments: list[CommentResponse]
    assets: list[AssetResponse]
    created_at: datetime
    updated_at: datetime


class ProjectSummaryResponse(BaseModel):
    id: str
    title: str
    doc_type: str
    main_topic: str
    status: str
    theme_config_json: dict
    ai_outline_suggested: bool
    current_version: int
    section_count: int
    like_count: int
    dislike_count: int
    export_count: int
    created_at: datetime
    updated_at: datetime


class ProjectDetailResponse(BaseModel):
    id: str
    user_id: str
    title: str
    doc_type: str
    main_topic: str
    status: str
    theme_config_json: dict
    ai_outline_suggested: bool
    current_version: int
    sections: list[SectionDetailResponse]
    created_at: datetime
    updated_at: datetime
