"""Simple Tools Panel.

Reuses the simple_tools plugin's adapter. The panel drives the
plugin's 8 tools (slugify, short_hash, generate_uuid, truncate,
word_count, is_valid_email, mask_secret, batch) through a
single form with an "operation" picker.

Same pattern as the HF and data-analytics panels: the panel only
knows about ``self.plugin`` and calls its tool methods directly.
"""

from __future__ import annotations

from typing import Any

from common_lib.modules.plugin_sdk.panels import BasePanel


class SimpleToolsPanel(BasePanel):
    """Demo panel for the simple_tools plugin."""

    id = "simple_tools"
    title = "Simple Tools"
    description = (
        "Handy one-off utilities: slugify, short_hash, generate_uuid, "
        "truncate, word_count, is_valid_email, mask_secret, batch."
    )
    version = "1.0.0"
    icon = "FiTool"
    category = "utility"

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "title": "Quick Tools",
            "description": "Pick an operation, fill in the input, get the result.",
            "properties": {
                "operation": {
                    "type": "string",
                    "title": "Operation",
                    "enum": [
                        "slugify",
                        "short_hash",
                        "generate_uuid",
                        "truncate",
                        "word_count",
                        "is_valid_email",
                        "mask_secret",
                        "batch",
                    ],
                    "default": "slugify",
                },
                "text": {
                    "type": "string",
                    "title": "Text input",
                    "description": "Main input (used by slugify/truncate/word_count/etc.)",
                    "default": "Hello World!",
                },
                "extra": {
                    "type": "string",
                    "title": "Extra input",
                    "description": (
                        "Secondary input: for batch this is the batch size; "
                        "for truncate this is max_chars; for short_hash this is "
                        "the length; for is_valid_email this is the email."
                    ),
                    "default": "5",
                },
            },
            "required": ["operation"],
        }

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.plugin is None:
            return {"error": "Plugin not bound", "rows": []}

        op = payload.get("operation", "slugify")
        text = payload.get("text", "")
        extra = payload.get("extra", "")

        if op == "generate_uuid":
            value = self.plugin.generate_uuid()
            return {
                "rows": [{"operation": op, "result": value}],
                "summary": f"Generated UUID: {value}",
            }

        if op == "slugify":
            value = self.plugin.slugify(text)
            return {
                "rows": [{"operation": op, "input": text, "result": value}],
                "summary": f"Slugified: {text!r} -> {value!r}",
            }

        if op == "short_hash":
            length = int(extra) if extra.isdigit() else 8
            value = self.plugin.short_hash(text, length=length)
            return {
                "rows": [
                    {"operation": op, "input": text, "result": value, "length": length}
                ],
                "summary": f"Short hash ({length} chars) of {text!r}: {value}",
            }

        if op == "truncate":
            max_chars = int(extra) if extra.isdigit() else 100
            value = self.plugin.truncate(text, max_chars=max_chars)
            return {
                "rows": [
                    {
                        "operation": op,
                        "input_len": len(text),
                        "max_chars": max_chars,
                        "result": value,
                    }
                ],
                "summary": f"Truncated {len(text)} chars to {max_chars}: got {len(value)}",
            }

        if op == "word_count":
            value = self.plugin.word_count(text)
            return {
                "rows": [{"operation": op, "input": text, "word_count": value}],
                "summary": f"{value} words in {text!r}",
            }

        if op == "is_valid_email":
            email = extra if "@" in extra else text
            valid = self.plugin.is_valid_email(email)
            return {
                "rows": [{"operation": op, "email": email, "is_valid": valid}],
                "summary": f"Email {email!r} is {'valid' if valid else 'invalid'}",
            }

        if op == "mask_secret":
            visible = int(extra) if extra.isdigit() else 4
            value = self.plugin.mask_secret(text, visible=visible)
            return {
                "rows": [
                    {
                        "operation": op,
                        "input_len": len(text),
                        "visible": visible,
                        "result": value,
                    }
                ],
                "summary": f"Masked secret (visible={visible}): {value}",
            }

        if op == "batch":
            size = int(extra) if extra.isdigit() else 3
            items = [x.strip() for x in text.split(",") if x.strip()]
            batches = self.plugin.batch(items, size=size)
            rows = [
                {"batch": i, "items": b, "count": len(b)} for i, b in enumerate(batches)
            ]
            return {
                "rows": rows,
                "summary": f"Batched {len(items)} items into {len(batches)} batches of size {size}",
            }

        return {"error": f"Unknown operation: {op!r}", "rows": []}


PANEL_CLASS = SimpleToolsPanel
