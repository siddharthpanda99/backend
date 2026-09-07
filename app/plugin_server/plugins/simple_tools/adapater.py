"""Adapter for simple_tools — wraps a 3rd-party single-file utility
into BaseToolPlugin.
"""

from __future__ import annotations

import logging
from typing import Any

from common_lib.modules.plugin_sdk.runtime.adapter_base import BaseAdapter
from common_lib.modules.plugins.base import BaseToolPlugin
from common_lib.modules.plugins.schemas import PluginMetadata

logger = logging.getLogger(__name__)


class SimpleToolsAdapter(BaseAdapter):
    """Adapter for the 3rd-party single-file utility."""

    def discover(self) -> list[BaseToolPlugin]:

     # Universal deepseek-style lifecycle applied to this plugin
        # Universal deepseek-style lifecycle
        from app.plugin_server.panels import PluginLifecycle, PluginPhase, PluginCapability
        self.lifecycle = PluginLifecycle(
            plugin_id="simple_tools",
            phases=[
                PluginPhase("init", "Initialize utilities"),
                PluginPhase("ready", "Ready to use"),
            ],
            capabilities=[
                PluginCapability("transform", "slugify, truncate, etc", requires_auth=False),
                PluginCapability("hash", "short_hash, generate_uuid", requires_auth=False),
                PluginCapability("validate", "is_valid_email, word_count", requires_auth=False),
            ],
            model_invocable=True,
            user_invocable=True,
            health_check_interval_sec=60.0,
        )

        self.add_cloned_to_sys_path()
        self.add_cloned_to_sys_path()
        try:
            import utils as u  # 3rd-party
        except ImportError as e:
            raise ImportError(
                f"simple_tools: failed to import 3rd-party module: {e}"
            ) from e

        metadata = PluginMetadata(
            id="simple_tools",
            name="Simple Tools",
            version="1.0.0",
            description=(
                "Single-file utility functions: slugify, hash, UUID, "
                "truncate, word count, email validation, batch, etc."
            ),
            category="utility",
            author="3rd-party (utils.py from a small project)",
            tags=["utility", "text", "string", "third-party"],
            dependencies=[],
            required_keys=[],
        )

        from common_lib.modules import plugin_sdk as sdk

        class SimpleToolsPlugin(BaseToolPlugin):
            def __init__(self):
                self.metadata = metadata
                self._u = u

            def check_health(self):
                from common_lib.modules.plugins.schemas import (
                    HealthStatus,
                    PluginHealth,
                )

                return PluginHealth(
                    status=HealthStatus.HEALTHY,
                    message="OK (single-file pure-stdlib)",
                )

            def get_nodes(self):
                return [
                    {
                        "name": "simple_tools.slugify",
                        "entity_type": "tool",
                        "description": "Convert text to URL slug.",
                    },
                    {
                        "name": "simple_tools.short_hash",
                        "entity_type": "tool",
                        "description": "Stable short hash of a string.",
                    },
                    {
                        "name": "simple_tools.generate_uuid",
                        "entity_type": "tool",
                        "description": "Generate a UUID4.",
                    },
                    {
                        "name": "simple_tools.truncate",
                        "entity_type": "tool",
                        "description": "Truncate text to N chars.",
                    },
                    {
                        "name": "simple_tools.word_count",
                        "entity_type": "tool",
                        "description": "Count words in a string.",
                    },
                    {
                        "name": "simple_tools.is_valid_email",
                        "entity_type": "tool",
                        "description": "Cheap email validation.",
                    },
                    {
                        "name": "simple_tools.mask_secret",
                        "entity_type": "tool",
                        "description": "Mask a secret leaving last N chars.",
                    },
                    {
                        "name": "simple_tools.batch",
                        "entity_type": "tool",
                        "description": "Split list into batches.",
                    },
                ]

            @sdk.tool(name="slugify", description="Convert text to URL slug.")
            @sdk.node(
                name="simple_tools.slugify",
                description="Convert text to URL slug.",
                category="simple_tools",
                audience=["planner", "executor"],
                input_schema=sdk.input_object(
                    properties={
                        "text": sdk.string_field("Input text."),
                        "max_length": sdk.number_field("Max length.", default=60),
                    },
                ),
                output_schema=sdk.output_object(
                    properties={
                        "slug": sdk.string_field("URL-safe slug."),
                    },
                ),
            )
            def slugify(self, text: str, max_length: int = 60) -> str:
                return self._u.slugify(text, max_length=max_length)

            @sdk.tool(name="short_hash", description="Stable short hash.")
            @sdk.node(
                name="simple_tools.short_hash",
                description="Stable short hash of a string.",
                category="simple_tools",
                audience=["planner", "executor"],
                input_schema=sdk.input_object(
                    properties={
                        "data": sdk.string_field("Input string."),
                        "length": sdk.number_field("Hash length.", default=8),
                    },
                ),
                output_schema=sdk.output_object(
                    properties={
                        "hash": sdk.string_field("Short hash."),
                    },
                ),
            )
            def short_hash(self, data: str, length: int = 8) -> str:
                return self._u.short_hash(data, length=length)

            @sdk.tool(name="generate_uuid", description="Generate UUID4.")
            @sdk.node(
                name="simple_tools.generate_uuid",
                description="Generate a UUID4.",
                category="simple_tools",
                audience=["planner", "executor"],
                input_schema=sdk.input_object(properties={}),
                output_schema=sdk.output_object(
                    properties={
                        "uuid": sdk.string_field("UUID4 string."),
                    },
                ),
            )
            def generate_uuid(self) -> str:
                return self._u.generate_uuid_v4()

            @sdk.tool(name="truncate", description="Truncate text.")
            @sdk.node(
                name="simple_tools.truncate",
                description="Truncate text to N chars.",
                category="simple_tools",
                audience=["planner", "executor"],
                input_schema=sdk.input_object(
                    properties={
                        "text": sdk.string_field("Input text."),
                        "max_chars": sdk.number_field("Max chars.", default=100),
                    },
                ),
                output_schema=sdk.output_object(
                    properties={
                        "truncated": sdk.string_field("Truncated text."),
                    },
                ),
            )
            def truncate(self, text: str, max_chars: int = 100) -> str:
                return self._u.truncate(text, max_chars=max_chars)

            @sdk.tool(name="word_count", description="Count words.")
            @sdk.node(
                name="simple_tools.word_count",
                description="Count words.",
                category="simple_tools",
                audience=["planner", "executor"],
                input_schema=sdk.input_object(
                    properties={
                        "text": sdk.string_field("Input text."),
                    },
                ),
                output_schema=sdk.output_object(
                    properties={
                        "count": sdk.number_field("Word count."),
                    },
                ),
            )
            def word_count(self, text: str) -> int:
                return self._u.word_count(text)

            @sdk.tool(name="is_valid_email", description="Cheap email check.")
            @sdk.node(
                name="simple_tools.is_valid_email",
                description="Cheap email check.",
                category="simple_tools",
                audience=["planner", "executor"],
                input_schema=sdk.input_object(
                    properties={
                        "email": sdk.string_field("Email to validate."),
                    },
                ),
                output_schema=sdk.output_object(
                    properties={
                        "valid": sdk.boolean_field("True if looks valid."),
                    },
                ),
            )
            def is_valid_email(self, email: str) -> bool:
                return self._u.is_valid_email(email)

            @sdk.tool(name="mask_secret", description="Mask a secret.")
            @sdk.node(
                name="simple_tools.mask_secret",
                description="Mask all but last N chars of a secret.",
                category="simple_tools",
                audience=["planner", "executor"],
                input_schema=sdk.input_object(
                    properties={
                        "secret": sdk.string_field("Secret to mask."),
                        "visible": sdk.number_field("Visible chars at end.", default=4),
                    },
                ),
                output_schema=sdk.output_object(
                    properties={
                        "masked": sdk.string_field("Masked secret."),
                    },
                ),
            )
            def mask_secret(self, secret: str, visible: int = 4) -> str:
                return self._u.mask_secret(secret, visible=visible)

            @sdk.tool(name="batch", description="Split list into batches.")
            @sdk.node(
                name="simple_tools.batch",
                description="Split list into batches.",
                category="simple_tools",
                audience=["planner", "executor"],
                input_schema=sdk.input_object(
                    properties={
                        "items": sdk.array_field("List to batch.", items=sdk.string_field("Item.")),
                        "size": sdk.number_field("Batch size.", default=10),
                    },
                ),
                output_schema=sdk.output_object(
                    properties={
                        "batches": sdk.array_field("List of batches.", items=sdk.string_field("Item.")),
                    },
                ),
            )
            def batch(self, items: list, size: int = 10) -> list[list]:
                return self._u.batch(items, size)

        return [SimpleToolsPlugin()]

    def warm_up(self) -> None:
        self.add_cloned_to_sys_path()
        import utils as u

        # Smoke test
        if u.slugify("Hello World!") != "hello-world":
            raise RuntimeError("slugify smoke test failed")
        self.log("warm_up: OK (slugify smoke test passed)")

    def dispose(self) -> None:
        self.log("dispose: no-op")
