"""Translation thin routes (W5-L04, gap N2). ALL logic delegates to
``common_lib.modules.audio_processing.translation`` via lazy imports — no
business logic here (thin-router rule). Endpoints:

- ``POST /translate``            — one text via the engine dispatch
- ``POST /translate/segments``   — batch translate (list of texts)
- ``POST /translate/quality``    — auto-glossary context extraction
- ``GET/POST/DELETE /translation/glossary/{project_id}[/term_id]`` — CRUD
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


class TranslateRequest(BaseModel):
    text: str
    source_lang: str = "en"
    target_lang: str = "es"
    provider: str = "google"


class TranslateSegmentsRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=500)
    source_lang: str = "en"
    target_lang: str = "es"
    provider: str = "google"
    cinematic: bool = False
    glossary: list[dict[str, Any]] | None = None


class QualityRequest(BaseModel):
    segment_texts: list[str] = Field(min_length=1, max_length=2000)
    source_lang: str = "en"
    target_lang: str = "es"
    target_name: str | None = None
    max_terms: int = 30


class GlossaryTerm(BaseModel):
    source: str
    target: str
    note: str = ""


@router.post("/translate")
async def translate_text(req: TranslateRequest):
    """One literal translation via the engine dispatch (W5-L02)."""
    from common_lib.modules.audio_processing.translation import translator

    out = translator.translate_text(
        req.text, req.source_lang, req.target_lang, provider=req.provider
    )
    if out.get("error"):
        # A provider-level error (missing key/package) is a client-fixable 400.
        raise HTTPException(status_code=400, detail=out["error"])
    return out


@router.post("/translate/segments")
async def translate_segments(req: TranslateSegmentsRequest):
    """Batch translate; ``cinematic=True`` adds the two-stage LLM refine with
    budget condensation (segments that miss the budget keep their literal)."""
    from common_lib.modules.audio_processing.translation import translator

    literal = [
        translator.translate_text(
            t, req.source_lang, req.target_lang, provider=req.provider
        )
        for t in req.texts
    ]
    failed = [i for i, row in enumerate(literal) if row.get("error")]
    if req.cinematic:
        pairs = [
            (str(i), t, row["text"])
            for i, (t, row) in enumerate(zip(req.texts, literal))
            if not row.get("error")
        ]
        refined = await translator.cinematic_refine_many(
            pairs,
            source_lang=req.source_lang,
            target_lang=req.target_lang,
            glossary=req.glossary,
        )
        by_id = {r["id"]: r for r in refined}
        results = []
        for i, (t, row) in enumerate(zip(req.texts, literal)):
            if row.get("error"):
                results.append({"id": i, "text": t, "error": row["error"]})
            else:
                results.append(by_id[str(i)])
        return {"results": results}
    return {"results": [
        {"id": i, **row} for i, row in enumerate(literal)
    ], "failed_rows": failed}


@router.post("/translate/quality")
async def translation_quality(req: QualityRequest):
    """Stage-1 auto-glossary: theme + terminology map for the transcript.
    Returns {theme, terms} or {context: None} when the LLM pass failed —
    context extraction never fails a request."""
    from common_lib.modules.audio_processing.translation import quality

    import asyncio

    ctx = await asyncio.get_running_loop().run_in_executor(
        None,
        lambda: quality.extract_context_sync(
            req.segment_texts,
            req.source_lang,
            req.target_lang,
            target_name=req.target_name,
            max_terms=req.max_terms,
        ),
    )
    return {"context": ctx}


# ── Glossary CRUD (W5-L03 service) ──────────────────────────────────────────


@router.get("/translation/glossary/{project_id}")
async def glossary_list(project_id: str):
    from common_lib.modules.audio_processing.translation import glossary

    return {"terms": glossary.glossary_list(project_id)}


@router.post("/translation/glossary/{project_id}", status_code=201)
async def glossary_add(project_id: str, term: GlossaryTerm):
    from common_lib.modules.audio_processing.translation import glossary

    try:
        entry = glossary.glossary_upsert(
            project_id, term.source, term.target, term.note
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return entry


@router.delete("/translation/glossary/{project_id}/{term_id}")
async def glossary_delete(project_id: str, term_id: int):
    from common_lib.modules.audio_processing.translation import glossary

    deleted = glossary.glossary_delete(project_id, entry_id=term_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="term not found")
    return {"deleted": True}


@router.delete("/translation/glossary/{project_id}")
async def glossary_clear(project_id: str):
    from common_lib.modules.audio_processing.translation import glossary

    n = len(glossary.glossary_list(project_id))
    for entry in list(glossary.glossary_list(project_id)):
        glossary.glossary_delete(project_id, entry_id=entry["id"])
    return {"deleted": n}
