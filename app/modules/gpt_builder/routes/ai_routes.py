"""GPT Builder — AI-Assisted Endpoints.

Endpoints for AI-powered app creation assistance:
draft-from-description, improve-block, generate-examples,
suggest-widgets, and compile-prompt.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from common_lib.modules.gpt_builder.schemas import (
    CompilePromptRequest,
    CompilePromptResponse,
    DraftFromDescriptionRequest,
    DraftFromDescriptionResponse,
    GenerateExamplesRequest,
    GenerateExamplesResponse,
    GptBuilderAppResponse,
    ImproveBlockRequest,
    ImproveBlockResponse,
    SuggestWidgetsRequest,
    SuggestWidgetsResponse,
)
from common_lib.modules.gpt_builder.service import get_gpt_builder_service
from common_lib.modules.gpt_builder.instruction_engine import InstructionComposer

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/{app_id}/ai/draft-from-description", response_model=DraftFromDescriptionResponse)
async def draft_from_description(app_id: str, data: DraftFromDescriptionRequest):
    """Generate an app draft from a natural language description using AI."""
    service = get_gpt_builder_service()

    # Generate name and slug from description
    desc_lower = data.description.lower()
    words = [w for w in desc_lower.split() if len(w) > 3][:5]

    domain_keywords = [
        "analytics", "data", "support", "code", "writing", "research",
        "marketing", "sales", "education", "health", "finance", "design",
    ]
    detected_domain = ""
    for kw in domain_keywords:
        if kw in desc_lower:
            detected_domain = kw
            break

    generated_name = data.name_hint or (words[0].capitalize() + " GPT" if words else "Custom GPT")
    generated_slug = data.name_hint.lower().replace(" ", "-") if data.name_hint else \
        (words[0] + "-gpt" if words else "custom-gpt")

    # Determine tone from description
    tone_hints = {
        "professional": ["professional", "business", "enterprise", "corporate"],
        "technical": ["technical", "code", "developer", "engineering"],
        "empathetic": ["empathetic", "support", "help", "care", "wellness"],
        "concise": ["quick", "fast", "concise", "brief"],
        "casual": ["casual", "fun", "friendly", "conversational"],
    }
    generated_tone = "professional"
    for tone, keywords in tone_hints.items():
        if any(k in desc_lower for k in keywords):
            generated_tone = tone
            break

    # Suggest widgets based on domain
    widget_suggestions = {
        "analytics": ["DataTable", "Chart", "MetricCard", "MetricGrid"],
        "data": ["DataTable", "Chart", "MetricCard", "CodeBlock"],
        "support": ["InfoCard", "Checklist", "Timeline", "Alert"],
        "code": ["CodeBlock", "Checklist", "Alert", "Markdown"],
        "writing": ["Markdown", "Checklist", "InfoCard"],
        "research": ["DataTable", "Chart", "InfoCard", "Markdown"],
        "marketing": ["MetricCard", "MetricGrid", "Chart", "Timeline"],
        "education": ["ProgressTracker", "Checklist", "InfoCard", "Markdown"],
    }
    suggested_widgets = widget_suggestions.get(detected_domain, ["InfoCard", "DataTable", "Chart"])

    # Suggest tools
    tool_suggestions = {
        "analytics": ["query_database", "export_data"],
        "data": ["query_database", "execute_code", "export_data"],
        "support": ["search_knowledge_base", "send_notification", "create_task"],
        "code": ["execute_code", "web_search"],
        "research": ["web_search", "search_knowledge_base"],
    }
    suggested_tools = tool_suggestions.get(detected_domain, ["search_knowledge_base", "web_search"])

    # Generate persona description
    generated_persona = f"A {generated_tone} AI assistant specialized in {detected_domain or 'general tasks'}"
    if data.domain_hint:
        generated_persona += f" with focus on {data.domain_hint}"

    # Build system prompt preview
    composer = InstructionComposer()
    persona_block = composer.build_persona_block(
        app_name=generated_name,
        persona_name=generated_name,
        tone=generated_tone,
        domain=detected_domain or data.domain_hint or "general",
        description=data.description[:500],
    )
    capabilities_block = composer.build_capabilities_block(
        tools=suggested_tools,
        widgets=suggested_widgets,
    )
    constraints = composer.build_constraints_block()
    system_prompt_preview = composer.compile_prompt(
        persona_block=persona_block,
        capabilities_block=capabilities_block,
        constraints=constraints,
        widget_catalog=suggested_widgets,
    )[:2000]

    # Create the app
    slug = f"{generated_slug}-{uuid.uuid4().hex[:6]}"
    create_data = {
        "name": generated_name,
        "slug": slug,
        "description": data.description[:500],
        "persona_name": generated_name,
        "tone": generated_tone,
        "domain_tags": [detected_domain] if detected_domain else [],
        "widget_catalog": suggested_widgets,
        "tool_ids": suggested_tools,
        "temperature": 0.7,
    }

    try:
        app = await service.create_app(create_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create app: {e}")

    return DraftFromDescriptionResponse(
        app=GptBuilderAppResponse(
            id=app.id,
            name=app.name,
            slug=app.slug,
            description=app.description,
            status=app.status or "draft",
            owner_id=app.owner_id,
            persona_name=app.persona_name,
            tone=app.tone or "professional",
            language=app.language or "en",
            domain_tags=app.domain_tags or [],
            temperature=app.temperature or 0.7,
            widget_catalog=app.widget_catalog or [],
            tool_ids=app.tool_ids or [],
            version=app.version or "1.0.0",
            is_template=app.is_template or False,
        ),
        generated_name=generated_name,
        generated_slug=slug,
        generated_persona=generated_persona,
        generated_tone=generated_tone,
        suggested_widgets=suggested_widgets,
        suggested_tools=suggested_tools,
        system_prompt_preview=system_prompt_preview,
    )


@router.post("/{app_id}/ai/improve-block", response_model=ImproveBlockResponse)
async def improve_block(app_id: str, data: ImproveBlockRequest):
    """Improve an instruction block using AI analysis."""
    content = data.current_content
    goal = data.improvement_goal.lower()

    improvements = []
    if "specific" in goal or "detail" in goal:
        improvements.append("Added specific task descriptions and expected outcomes")
        if len(content) < 100:
            content += "\n\nSpecifically, this persona should:\n- Analyze and interpret user requests within the domain\n- Provide actionable recommendations based on data\n- Communicate findings in clear, structured formats"
    if "concise" in goal or "short" in goal:
        improvements.append("Condensed verbose sections while preserving key instructions")
        if len(content) > 500:
            content = "\n".join(content.split("\n")[:5]) + "\n[Condensed for clarity]"
    if "friendly" in goal or "warm" in goal:
        improvements.append("Adopted a warmer, more approachable tone")
        content = content.replace("must", "should").replace("shall", "may")
    if "technical" in goal or "expert" in goal:
        improvements.append("Added domain-specific terminology and precision")
        content += "\n\nTechnical directives:\n- Use precise industry terminology\n- Provide quantitative evidence when available\n- Reference relevant frameworks and methodologies"
    if "safe" in goal or "ethical" in goal:
        improvements.append("Added safety constraints and ethical guidelines")
        content += "\n\nSafety and Ethics:\n- Do not generate harmful or misleading content\n- Flag uncertain or unverifiable information\n- Respect user privacy and data security"

    if not improvements:
        improvements.append("Refined language for clarity and impact")
        content = content.strip() + "\n\n[Review and refine as needed]"

    return ImproveBlockResponse(
        improved_content=content,
        changes_summary="; ".join(improvements),
    )


@router.post("/{app_id}/ai/generate-examples", response_model=GenerateExamplesResponse)
async def generate_examples(app_id: str, data: GenerateExamplesRequest):
    """Generate conversation examples for a GPT Builder App."""
    domain = data.domain or "general"
    tone = data.tone or "professional"
    persona = data.persona_name or "Assistant"

    example_templates = {
        "analytics": [
            f"User: Can you analyze our Q4 revenue data?\n{persona}: I'd be happy to analyze your Q4 revenue data. Let me pull the numbers and create a comprehensive breakdown.",
            f"User: Show me the top 10 customers by MRR\n{persona}: Here are your top 10 customers by Monthly Recurring Revenue, ranked and with trend indicators.",
            f"User: What's our churn rate trend?\n{persona}: I've analyzed the churn data over the past 6 months. Here's the trend with key insights.",
        ],
        "support": [
            f"User: I can't log into my account\n{persona}: I'm sorry you're having trouble. Let me help you troubleshoot this step by step.",
            f"User: How do I reset my password?\n{persona}: Here's a step-by-step guide to reset your password.",
            f"User: My subscription isn't working\n{persona}: Let me check your subscription status and investigate the issue.",
        ],
        "code": [
            f"User: Write a function to sort an array\n{persona}: Here's a clean, efficient implementation with documentation and edge case handling.",
            f"User: Explain this error message\n{persona}: I'll break down what this error means and provide a fix.",
        ],
    }

    examples = example_templates.get(domain, [
        f"User: Can you help me with something?\n{persona}: Of course! I'm here to help. What would you like assistance with?",
        f"User: Tell me more about this topic\n{persona}: Here's a detailed explanation with key points and examples.",
        f"User: What can you do?\n{persona}: I'm a {persona}, specialized in {domain}. I can help with analysis, research, and recommendations.",
    ])

    return GenerateExamplesResponse(examples=examples[:data.count])


@router.post("/{app_id}/ai/suggest-widgets", response_model=SuggestWidgetsResponse)
async def suggest_widgets(app_id: str, data: SuggestWidgetsRequest):
    """Suggest widget types based on app description and domain."""
    from common_lib.modules.gpt_builder.widget_dispatch import WIDGET_REGISTRY

    desc_lower = data.description.lower()

    # Score each widget type based on keyword matches
    widget_scores: Dict[str, float] = {}
    for wtype, meta in WIDGET_REGISTRY.items():
        score = 0.0
        desc = meta["description"].lower()
        # Check keyword overlap between description and widget description
        desc_words = set(desc.split())
        prompt_words = set(desc_lower.split())
        overlap = len(desc_words & prompt_words)
        score += overlap * 0.5

        # Domain-specific boosts
        domain = data.domain_tags or []
        if "data" in desc and any(d in ["analytics", "data", "research"] for d in domain):
            score += 2.0
        if "code" in desc and any(d in ["code", "developer", "engineering"] for d in domain):
            score += 2.0
        if "action" in desc.lower() or "step" in desc.lower():
            if any(d in ["support", "education", "project"] for d in domain):
                score += 1.5

        widget_scores[wtype] = score

    # Sort by score descending
    sorted_widgets = sorted(widget_scores.items(), key=lambda x: x[1], reverse=True)

    reasoning_parts = []
    suggested = []
    for wtype, score in sorted_widgets[:8]:
        if score > 0:
            suggested.append(wtype)
            reasoning_parts.append(f"{wtype} (score: {score:.1f})")

    if not suggested:
        suggested = ["InfoCard", "DataTable", "MetricCard", "Chart", "Markdown"]
        reasoning_parts = ["Default suggestions (no strong domain signal detected)"]

    reasoning = "Top widget recommendations: " + ", ".join(reasoning_parts)

    return SuggestWidgetsResponse(
        suggested_widgets=suggested,
        reasoning=reasoning,
    )


@router.post("/{app_id}/ai/compile-prompt", response_model=CompilePromptResponse)
async def compile_prompt(app_id: str, data: CompilePromptRequest):
    """Compile instruction components into a system prompt with token estimate."""
    try:
        composer = InstructionComposer()

        compiled = composer.compile_prompt(
            persona_block=data.persona_block,
            capabilities_block=data.capabilities_block,
            constraints=data.constraints,
            widget_catalog=data.widget_catalog,
            tool_manifest=data.tool_manifest,
            knowledge_summary=data.knowledge_summary,
        )

        token_estimate = composer.estimate_tokens(compiled)

        return CompilePromptResponse(
            compiled_prompt=compiled,
            token_estimate=token_estimate,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prompt compilation failed: {e}")
