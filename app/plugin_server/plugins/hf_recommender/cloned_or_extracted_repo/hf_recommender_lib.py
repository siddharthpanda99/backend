"""3rd-party HuggingFace model recommender (untouched).

This is what `git clone https://github.com/RashAlbainy/huggingface_model_recommender`
would produce. The vendor has never heard of common_lib, BaseToolPlugin,
or any of our platform. This file is 100% portable.

We wrap this in our adapter with zero modifications to this file.
"""

from __future__ import annotations

from typing import Any


# This is a SIMPLIFIED version of the recommender — enough to demo
# the pattern. The real one hits the HF Hub API and uses Ollama.

# A static catalog of model categories for demo purposes.
# In reality this would be a live search.
HF_MODEL_CATALOG: dict[str, list[dict[str, Any]]] = {
    "text-generation": [
        {
            "id": "gpt2",
            "downloads": 25_000_000,
            "likes": 4500,
            "tags": ["text-generation", "pytorch", "transformers"],
            "params": "124M",
            "description": "Classic GPT-2 124M for text generation.",
        },
        {
            "id": "meta-llama/Llama-2-7b-hf",
            "downloads": 5_000_000,
            "likes": 3200,
            "tags": ["text-generation", "pytorch", "llama"],
            "params": "7B",
            "description": "Meta's Llama 2 7B base model.",
        },
        {
            "id": "mistralai/Mistral-7B-v0.1",
            "downloads": 3_200_000,
            "likes": 2800,
            "tags": ["text-generation", "pytorch", "mistral"],
            "params": "7.24B",
            "description": "Mistral 7B base model.",
        },
    ],
    "text-classification": [
        {
            "id": "distilbert-base-uncased-finetuned-sst-2-english",
            "downloads": 12_000_000,
            "likes": 850,
            "tags": ["text-classification", "pytorch", "distilbert"],
            "params": "66M",
            "description": "DistilBERT fine-tuned on SST-2 sentiment.",
        },
        {
            "id": "cardiffnlp/twitter-roberta-base-sentiment-latest",
            "downloads": 1_500_000,
            "likes": 320,
            "tags": ["text-classification", "pytorch", "roberta"],
            "params": "125M",
            "description": "RoBERTa fine-tuned on Twitter sentiment.",
        },
    ],
    "translation": [
        {
            "id": "Helsinki-NLP/opus-mt-en-de",
            "downloads": 2_000_000,
            "likes": 145,
            "tags": ["translation", "pytorch", "marian"],
            "params": "77M",
            "description": "English-to-German translation.",
        },
        {
            "id": "Helsinki-NLP/opus-mt-en-fr",
            "downloads": 1_800_000,
            "likes": 132,
            "tags": ["translation", "pytorch", "marian"],
            "params": "77M",
            "description": "English-to-French translation.",
        },
    ],
    "summarization": [
        {
            "id": "facebook/bart-large-cnn",
            "downloads": 4_500_000,
            "likes": 280,
            "tags": ["summarization", "pytorch", "bart"],
            "params": "406M",
            "description": "BART fine-tuned on CNN/DailyMail summarization.",
        },
        {
            "id": "philschmid/bart-large-cnn-samsum",
            "downloads": 350_000,
            "likes": 95,
            "tags": ["summarization", "pytorch", "bart"],
            "params": "406M",
            "description": "BART fine-tuned on SAMSum dialog summarization.",
        },
    ],
    "image-classification": [
        {
            "id": "google/vit-base-patch16-224",
            "downloads": 3_800_000,
            "likes": 540,
            "tags": ["image-classification", "pytorch", "vit"],
            "params": "86M",
            "description": "Vision Transformer base 224.",
        },
    ],
}


def search_models(
    task: str,
    *,
    min_downloads: int = 0,
    framework: str | None = None,
    sort_by: str = "downloads",
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Search the (mock) HuggingFace model catalog for the given task.

    Args:
        task: HF task name (e.g. "text-generation", "translation").
        min_downloads: Filter out models below this download count.
        framework: Filter by framework (e.g. "pytorch", "gguf").
        sort_by: One of "downloads", "likes", "trending".
        top_k: Maximum number of results to return.

    Returns:
        List of model dicts, sorted by the chosen criterion.
    """
    catalog = HF_MODEL_CATALOG.get(task, [])

    # Filter
    results = []
    for m in catalog:
        if m["downloads"] < min_downloads:
            continue
        if framework and framework not in m.get("tags", []):
            continue
        results.append(m)

    # Sort
    if sort_by in ("downloads", "likes"):
        results.sort(key=lambda m: m.get(sort_by, 0), reverse=True)
    elif sort_by == "trending":
        # In real life this would use a recency-weighted score
        results.sort(
            key=lambda m: m.get("likes", 0) / max(1, m.get("downloads", 1)),
            reverse=True,
        )

    return results[:top_k]


def list_tasks() -> list[str]:
    """Return all available task types in the catalog."""
    return list(HF_MODEL_CATALOG.keys())


def get_model_info(model_id: str) -> dict[str, Any] | None:
    """Look up a single model by id. Returns None if not found."""
    for models in HF_MODEL_CATALOG.values():
        for m in models:
            if m["id"] == model_id:
                return m
    return None
