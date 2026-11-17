import io
import json
import time
import uuid
from pathlib import Path

from fastapi import HTTPException, status
from google import genai
from google.genai import types
from PIL import Image
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.project import DocumentAsset, Project
from app.models.section import DocumentSection
from app.schemas.llm_structured import (
    DocxSectionSchema,
    OutlineSuggestionSchema,
    PptxSlideSchema,
)
from app.services.audit_service import AuditService


class GeminiService:
    """Orchestrates structured Gemini text generation, refinement, outline suggestion, and images."""

    def __init__(self, client: genai.Client | None = None):
        self._client = client

    def _get_client(self) -> genai.Client:
        if self._client is not None:
            return self._client
        settings = get_settings()
        if not settings.gemini_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GEMINI_API_KEY is not configured.",
            )
        self._client = genai.Client(api_key=settings.gemini_api_key)
        return self._client

    @staticmethod
    def _extract_token_usage(response) -> tuple[int, int, int]:
        usage = getattr(response, "usage_metadata", None)
        if not usage:
            return 0, 0, 0
        prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0
        total_tokens = getattr(usage, "total_token_count", 0) or (prompt_tokens + output_tokens)
        return int(prompt_tokens), int(output_tokens), int(total_tokens)

    def _generate_structured(
        self,
        db: Session,
        *,
        operation: str,
        prompt: str,
        schema_cls: type[BaseModel],
        user_id: str | None = None,
        project_id: str | None = None,
        section_id: str | None = None,
        temperature: float = 0.5,
    ) -> tuple[BaseModel, str]:
        settings = get_settings()
        model_name = settings.gemini_text_model
        client = self._get_client()
        started = time.perf_counter()

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema_cls,
                    temperature=temperature,
                ),
            )
            latency_ms = (time.perf_counter() - started) * 1000.0
            in_tok, out_tok, tot_tok = self._extract_token_usage(response)

            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, schema_cls):
                result = parsed
            else:
                raw_text = (getattr(response, "text", None) or "").strip()
                result = schema_cls.model_validate_json(raw_text)

            metric = AuditService.record_llm_metric(
                db,
                operation=operation,
                model_name=model_name,
                user_id=user_id,
                project_id=project_id,
                section_id=section_id,
                input_tokens=in_tok,
                output_tokens=out_tok,
                total_tokens=tot_tok,
                latency_ms=latency_ms,
                status="success",
                prompt_preview=prompt[:450],
            )
            return result, metric.id
        except HTTPException:
            raise
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000.0
            AuditService.record_llm_metric(
                db,
                operation=operation,
                model_name=model_name,
                user_id=user_id,
                project_id=project_id,
                section_id=section_id,
                latency_ms=latency_ms,
                status="error",
                error_message=str(exc)[:1000],
                prompt_preview=prompt[:450],
            )
            db.flush()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Gemini {operation} call failed: {exc}",
            ) from exc

    def suggest_outline(
        self,
        db: Session,
        *,
        doc_type: str,
        main_topic: str,
        target_count: int | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> tuple[OutlineSuggestionSchema, str]:
        """Bonus feature: generate structured Word section headers or PowerPoint slide titles."""
        kind_label = (
            "PowerPoint presentation slide titles"
            if doc_type == "pptx"
            else "Microsoft Word report section headers"
        )
        count_hint = (
            f"Provide exactly {target_count} items."
            if target_count
            else ("Provide 6-8 cohesive slides." if doc_type == "pptx" else "Provide 5-7 structured sections.")
        )
        prompt = (
            f"You are an expert business document architect.\n"
            f"Task: Propose {kind_label} for the following topic:\n"
            f"Topic: {main_topic}\n"
            f"{count_hint}\n"
            f"Requirements:\n"
            f"- Titles must be logical, non-overlapping, executive-ready, and ordered smoothly "
            f"from executive framing to actionable recommendations.\n"
            f"- Keep each header/slide title concise (3-9 words)."
        )
        result, metric_id = self._generate_structured(
            db,
            operation="outline_suggest",
            prompt=prompt,
            schema_cls=OutlineSuggestionSchema,
            user_id=user_id,
            project_id=project_id,
            temperature=0.6,
        )
        assert isinstance(result, OutlineSuggestionSchema)
        return result, metric_id

    def generate_section_content(
        self,
        db: Session,
        *,
        project: Project,
        section: DocumentSection,
        sibling_titles: list[str],
        user_id: str,
    ) -> tuple[dict, str]:
        """Generate context-aware structured content for one Word section or PowerPoint slide."""
        theme = project.theme_config_json or {}
        tone = theme.get("tone", "executive")
        audience = theme.get("audience", "Business leadership & stakeholders")
        include_images = bool(theme.get("include_images", True))
        palette = theme.get("palette", "executive_navy")

        outline_str = "\n".join(
            f"{idx + 1}. {title}" + ("  <-- TARGET" if idx == section.order_index else "")
            for idx, title in enumerate(sibling_titles)
        )

        image_instruction = (
            f"Set should_generate_image=true for key conceptual/strategic sections where a clean "
            f"bespoke illustration improves clarity (avoid generating an image on every single "
            f"section—roughly 1 in 2 sections/slides, or when visual framing shines). Write "
            f"image_prompt describing a clean minimalist modern editorial/business graphic in "
            f"'{palette}' tones with NO text, NO words, and NO labels inside the image."
            if include_images
            else "Set should_generate_image=false and leave image_prompt empty."
        )

        if project.doc_type == "pptx":
            prompt = (
                f"You are an executive presentation strategist creating Slide "
                f"{section.order_index + 1} of {len(sibling_titles)}.\n"
                f"Deck Title: {project.title}\n"
                f"Main Topic: {project.main_topic}\n"
                f"Target Audience: {audience}\n"
                f"Tone: {tone}\n\n"
                f"Full Deck Structure:\n{outline_str}\n\n"
                f"Target Slide Title: {section.title}\n\n"
                f"Strict Slide Quality Rules:\n"
                f"- Write ONLY for this slide without repeating other slides.\n"
                f"- Keep bullets punchy and presentation-ready (max 15-18 words per bullet, "
                f"3-5 bullets) so text never overflows.\n"
                f"- Pick the best layout_variant: 'bullets_with_visual' if an image helps, "
                f"'two_column' for comparisons/before-after, 'metrics_cards' for KPIs/numbers, "
                f"or 'bullets_only'.\n"
                f"- Provide crisp presenter speaker_notes.\n"
                f"- {image_instruction}"
            )
            schema_cls: type[BaseModel] = PptxSlideSchema
        else:
            prompt = (
                f"You are a senior management consultant authoring Section "
                f"{section.order_index + 1} of {len(sibling_titles)} in a Word business report.\n"
                f"Document Title: {project.title}\n"
                f"Main Topic: {project.main_topic}\n"
                f"Target Audience: {audience}\n"
                f"Tone: {tone}\n\n"
                f"Full Document Outline:\n{outline_str}\n\n"
                f"Target Section Header: {section.title}\n\n"
                f"Strict Report Quality Rules:\n"
                f"- Author insightful, specific content for THIS section only without "
                f"duplicating other sections.\n"
                f"- Include a sharp 1-2 sentence summary_callout, 2-3 substantive paragraphs, "
                f"and 3-5 structured bullet_points with bold lead-in labels.\n"
                f"- Include a compact data_table (2-4 columns, 2-5 rows) ONLY if structured "
                f"data/comparisons genuinely elevate this section; otherwise set data_table=null.\n"
                f"- {image_instruction}"
            )
            schema_cls = DocxSectionSchema

        parsed, metric_id = self._generate_structured(
            db,
            operation="section_generate",
            prompt=prompt,
            schema_cls=schema_cls,
            user_id=user_id,
            project_id=project.id,
            section_id=section.id,
            temperature=0.55,
        )
        return parsed.model_dump(), metric_id

    def refine_section_content(
        self,
        db: Session,
        *,
        project: Project,
        section: DocumentSection,
        current_content_json: dict,
        refinement_prompt: str,
        user_id: str,
    ) -> tuple[dict, str]:
        """Iteratively refine a single section/slide based on user instructions."""
        schema_cls: type[BaseModel] = (
            PptxSlideSchema if project.doc_type == "pptx" else DocxSectionSchema
        )
        target_kind = "PowerPoint slide" if project.doc_type == "pptx" else "Word report section"
        prompt = (
            f"You are refining a single {target_kind}.\n"
            f"Project Title: {project.title}\n"
            f"Main Topic: {project.main_topic}\n"
            f"Section/Slide Title: {section.title}\n\n"
            f"Current Structured Content JSON:\n{json.dumps(current_content_json, indent=2)}\n\n"
            f"User Refinement Request:\n\"{refinement_prompt}\"\n\n"
            f"Instructions:\n"
            f"- Apply the user's refinement request faithfully and accurately.\n"
            f"- Preserve structural integrity and schema constraints.\n"
            f"- Keep should_generate_image/image_prompt/image_caption intact unless the user "
            f"asks to change visuals."
        )
        parsed, metric_id = self._generate_structured(
            db,
            operation="section_refine",
            prompt=prompt,
            schema_cls=schema_cls,
            user_id=user_id,
            project_id=project.id,
            section_id=section.id,
            temperature=0.45,
        )
        return parsed.model_dump(), metric_id

    def generate_section_image(
        self,
        db: Session,
        *,
        image_prompt: str,
        caption: str,
        project_id: str,
        section_id: str,
        user_id: str,
    ) -> DocumentAsset | None:
        """Generate a custom editorial visual using Gemini Image Generation and persist asset."""
        settings = get_settings()
        if not settings.enable_image_generation or not image_prompt.strip():
            return None

        model_name = settings.gemini_image_model
        client = self._get_client()
        started = time.perf_counter()

        enhanced_prompt = (
            f"{image_prompt.strip()}. High-craft clean modern corporate editorial graphic, "
            f"crisp vector/3D studio aesthetic, balanced composition, absolutely no embedded "
            f"text, no letters, no watermarks."
        )

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=enhanced_prompt,
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            )
            latency_ms = (time.perf_counter() - started) * 1000.0
            in_tok, out_tok, tot_tok = self._extract_token_usage(response)

            image_bytes: bytes | None = None
            mime_type = "image/png"
            for cand in getattr(response, "candidates", []) or []:
                content = getattr(cand, "content", None)
                for part in getattr(content, "parts", []) or []:
                    inline = getattr(part, "inline_data", None)
                    if inline and getattr(inline, "data", None):
                        image_bytes = inline.data
                        mime_type = getattr(inline, "mime_type", None) or "image/png"
                        break
                if image_bytes:
                    break

            if not image_bytes:
                raise RuntimeError("No image bytes returned from Gemini image model.")

            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size

            file_name = f"{project_id}_{section_id}_{uuid.uuid4().hex[:8]}.png"
            out_path: Path = settings.assets_dir / file_name
            img.save(out_path, format="PNG")

            metric = AuditService.record_llm_metric(
                db,
                operation="image_generate",
                model_name=model_name,
                user_id=user_id,
                project_id=project_id,
                section_id=section_id,
                input_tokens=in_tok,
                output_tokens=out_tok,
                total_tokens=tot_tok,
                latency_ms=latency_ms,
                status="success",
                prompt_preview=enhanced_prompt[:450],
            )

            asset = DocumentAsset(
                project_id=project_id,
                section_id=section_id,
                asset_type="generated_image",
                prompt=image_prompt.strip(),
                mime_type="image/png" if mime_type else "image/png",
                storage_path=f"assets/{file_name}",
                caption=caption.strip(),
                width=width,
                height=height,
                is_active=True,
                llm_metric_id=metric.id,
            )
            db.add(asset)
            db.flush()
            return asset
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000.0
            AuditService.record_llm_metric(
                db,
                operation="image_generate",
                model_name=model_name,
                user_id=user_id,
                project_id=project_id,
                section_id=section_id,
                latency_ms=latency_ms,
                status="error",
                error_message=str(exc)[:1000],
                prompt_preview=enhanced_prompt[:450],
            )
            db.flush()
            return None
