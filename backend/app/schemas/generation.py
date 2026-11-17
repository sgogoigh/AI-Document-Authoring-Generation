from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SuggestOutlineRequest(BaseModel):
    doc_type: Literal["docx", "pptx"]
    main_topic: str = Field(min_length=3, max_length=4000)
    target_count: int | None = Field(default=None, ge=3, le=12)
    project_id: str | None = None


class SuggestOutlineResponse(BaseModel):
    recommended_title: str
    rationale: str
    items: list[str]


class GenerateProjectRequest(BaseModel):
    generate_images: bool = True
    only_missing: bool = False


class RefineSectionRequest(BaseModel):
    refinement_prompt: str = Field(min_length=2, max_length=2000)
    regenerate_image: bool = False


class RegenerateImageRequest(BaseModel):
    image_prompt: str | None = Field(default=None, max_length=1000)
    caption: str | None = Field(default=None, max_length=300)


class FeedbackRequest(BaseModel):
    rating: Literal["like", "dislike", "none"]
    note: str | None = Field(default=None, max_length=1000)


class CommentCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class SectionRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    section_id: str
    project_id: str
    revision_number: int
    project_version: int
    source: str
    refinement_prompt: str | None
    previous_content_json: dict | None
    new_content_json: dict
    diff_summary_json: dict
    llm_metric_id: str | None
    created_by: str
    created_at: datetime
