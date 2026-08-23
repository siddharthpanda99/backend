"""
MCP Tools — Memory Feature Flag Management (3-Level Hierarchy).

Hierarchy: Module → Feature Set → Feature
Tools let external agents control which memory features/modules are enabled.
"""

import logging
from typing import Dict, List, Any, Optional
from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger("mcp.tools.memory_features")


def register_memory_feature_tools(mcp: FastMCP):
    """Register tools for memory feature flag management."""

    @mcp.tool()
    async def list_memory_features(category: Optional[str] = None) -> Dict[str, Any]:
        """List all memory feature flags organized by hierarchy level.
        
        Args:
            category: Optional filter — 'module', 'featureset', 'feature', 
                     'search', 'context', etc. or None for all.
        
        Returns:
            Features grouped by level with enabled state and descriptions.
        """
        from common_lib.modules.memory.claude_mem_features.feature_flags import FeatureFlags
        
        all_flags = FeatureFlags.get_all()
        result = {"modules": {}, "featuresets": {}, "features": {}, "claude_mem": {}}
        
        for key, enabled in all_flags.items():
            flag = FeatureFlags.FEATURES.get(key)
            if not flag:
                continue
            entry = {
                "enabled": enabled,
                "description": flag.description,
                "parent": flag.parent,
            }
            if flag.category == "module":
                result["modules"][key] = entry
            elif flag.category == "featureset":
                result["featuresets"][key] = entry
            elif flag.category == "feature":
                result["features"][key] = entry
            else:
                result["claude_mem"][key] = entry
        
        if category:
            if category in result:
                return {"level": category, "items": result[category], "count": len(result[category])}
            # Filter by category tag
            filtered = {}
            for level, items in result.items():
                for k, v in items.items():
                    flag = FeatureFlags.FEATURES.get(k)
                    if flag and flag.category == category:
                        filtered[k] = v
            return {"level": category, "items": filtered, "count": len(filtered)}
        
        return {
            "summary": {
                "modules": len(result["modules"]),
                "featuresets": len(result["featuresets"]),
                "features": len(result["features"]),
                "claude_mem": len(result["claude_mem"]),
                "total": len(all_flags),
            },
            **result,
        }

    @mcp.tool()
    async def get_memory_feature_status() -> Dict[str, Any]:
        """Get summary of all memory features — 14 claude-mem + 24 modules + sub-features.
        
        Returns:
            Summary with counts per level and category.
        """
        from common_lib.modules.memory.claude_mem_features.feature_flags import FeatureFlags
        
        modules = FeatureFlags.get_modules()
        featuresets = FeatureFlags.get_featuresets()
        features = FeatureFlags.get_features()
        claude_mem = FeatureFlags.get_claude_mem_features()
        
        return {
            "total_features": len(FeatureFlags.FEATURES),
            "levels": {
                "module": {"count": len(modules), "enabled": sum(1 for v in modules.values() if v)},
                "featureset": {"count": len(featuresets), "enabled": sum(1 for v in featuresets.values() if v)},
                "feature": {"count": len(features), "enabled": sum(1 for v in features.values() if v)},
                "claude_mem": {"count": len(claude_mem), "enabled": sum(1 for v in claude_mem.values() if v)},
            },
        }

    @mcp.tool()
    async def toggle_memory_feature(feature_key: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable a memory feature at any level (module, featureset, or feature).
        
        Hierarchy rules:
        - Disabling a module disables ALL its featuresets and features
        - Disabling a featureset disables ALL its features
        - Enabling a feature requires its parent to be enabled
        
        Args:
            feature_key: The key (e.g., 'memory_retrieval', 'memory_retrieval.vector_search', 
                        'memory_retrieval.vector_search.minilm')
            enabled: True to enable, False to disable
        
        Returns:
            Status with cascading effects.
        """
        from common_lib.modules.memory.claude_mem_features.feature_flags import FeatureFlags
        
        try:
            if enabled:
                FeatureFlags.enable(feature_key)
            else:
                FeatureFlags.disable(feature_key)
            
            # Check what was affected
            flag = FeatureFlags.FEATURES.get(feature_key)
            affected = []
            if flag and flag.children:
                for child in flag.children:
                    if not FeatureFlags.is_enabled(child):
                        affected.append(child)
            
            return {
                "success": True,
                "feature": feature_key,
                "enabled": FeatureFlags.is_enabled(feature_key),
                "level": flag.category if flag else "unknown",
                "affected_children": affected,
                "description": FeatureFlags.get_description(feature_key),
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def toggle_memory_module(module_key: str, enabled: bool) -> Dict[str, Any]:
        """Toggle an entire memory module (all featuresets and features).
        
        Args:
            module_key: Module key (e.g., 'memory_retrieval', 'memory_security')
            enabled: True to enable, False to disable
        
        Returns:
            Status with all affected items.
        """
        from common_lib.modules.memory.claude_mem_features.feature_flags import FeatureFlags
        
        try:
            if enabled:
                FeatureFlags.enable(module_key)
            else:
                FeatureFlags.disable(module_key)
            
            flag = FeatureFlags.FEATURES.get(module_key)
            children = FeatureFlags.get_children(module_key) if flag else {}
            
            return {
                "success": True,
                "module": module_key,
                "enabled": FeatureFlags.is_enabled(module_key),
                "children_count": len(children),
                "children": children,
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def get_memory_feature_hierarchy() -> Dict[str, Any]:
        """Get the complete 3-level hierarchy tree.
        
        Returns:
            Full tree: Module → Feature Set → Feature with enabled states.
        """
        from common_lib.modules.memory.claude_mem_features.feature_flags import FeatureFlags
        return FeatureFlags.get_hierarchy()

    @mcp.tool()
    async def bulk_toggle_memory_features(features: Dict[str, bool]) -> Dict[str, Any]:
        """Enable or disable multiple memory features at once.
        
        Args:
            features: Mapping of feature keys to enabled states.
                     Example: {"memory_retrieval": true, "memory_security.encryption": false}
        
        Returns:
            Results for each toggle with cascade effects.
        """
        from common_lib.modules.memory.claude_mem_features.feature_flags import FeatureFlags
        
        results = {}
        for key, enabled in features.items():
            try:
                if enabled:
                    FeatureFlags.enable(key)
                else:
                    FeatureFlags.disable(key)
                results[key] = {"success": True, "enabled": FeatureFlags.is_enabled(key)}
            except ValueError as e:
                results[key] = {"success": False, "error": str(e)}
        
        return {"results": results, "total": len(features)}

    @mcp.tool()
    async def save_memory_feature_state() -> Dict[str, Any]:
        """Save current feature states to config.ini [Memory] section.
        
        Returns:
            Status of the save operation.
        """
        from common_lib.modules.memory.claude_mem_features.feature_flags import FeatureFlags
        
        try:
            FeatureFlags.save_to_settings()
            return {"success": True, "total_features": len(FeatureFlags.get_all())}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def reset_memory_features() -> Dict[str, Any]:
        """Reset all feature flags to defaults.
        
        WARNING: This resets everything to default state.
        
        Returns:
            Status with default state.
        """
        from common_lib.modules.memory.claude_mem_features.feature_flags import FeatureFlags
        
        FeatureFlags.reset()
        return {
            "success": True,
            "total_features": len(FeatureFlags.get_all()),
            "enabled_count": sum(1 for v in FeatureFlags.get_all().values() if v),
        }

    @mcp.tool()
    async def get_feature_dependencies(feature_key: str) -> Dict[str, Any]:
        """Check dependencies and parent chain for a feature.
        
        Args:
            feature_key: The feature key to check.
        
        Returns:
            Full dependency tree with states.
        """
        from common_lib.modules.memory.claude_mem_features.feature_flags import FeatureFlags
        
        FeatureFlags._ensure_initialized()
        
        if feature_key not in FeatureFlags._flags:
            return {"error": f"Unknown feature: {feature_key}"}
        
        flag = FeatureFlags._flags[feature_key]
        
        # Walk parent chain
        parent_chain = []
        current = flag.parent
        while current:
            parent_flag = FeatureFlags._flags.get(current)
            if parent_flag:
                parent_chain.append({
                    "key": current,
                    "enabled": FeatureFlags.is_enabled(current),
                    "description": parent_flag.description,
                })
                current = parent_flag.parent
            else:
                break
        
        return {
            "feature": feature_key,
            "enabled": FeatureFlags.is_enabled(feature_key),
            "level": flag.category,
            "parent_chain": parent_chain,
            "direct_dependencies": [
                {"key": dep, "enabled": FeatureFlags.is_enabled(dep)}
                for dep in flag.dependencies
            ],
            "children": FeatureFlags.get_children(feature_key),
            "description": flag.description,
        }

    logger.info("Memory feature management MCP tools registered (9 tools)")
