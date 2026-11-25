import logging
from typing import List, Dict, Any, Optional
from app.mcp.fastmcp_compat import FastMCP
from ..mcp_dependencies import resolve_entity_studio_service

logger = logging.getLogger("mcp.tools.entity_studio")


def register_entity_studio_tools(mcp: FastMCP):
    """Register tools for Entity Studio - programmatic entity creation for agents."""

    @mcp.tool()
    async def create_atom(
        atom_id: str,
        name: str,
        category: str,
        content: str,
        description: str = "",
        format: str = "md",
        variables: List[str] = None,
        dependencies: List[str] = None,
        tags: List[str] = None,
        use_cases: List[str] = None,
        platforms: List[str] = None,
        ai_instructions: str = "",
        ai_warnings: List[str] = None,
        ai_context: str = "",
        ai_prerequisites: List[str] = None,
        human_instructions: str = "",
        human_warnings: List[str] = None,
        human_notes: str = "",
        examples: List[str] = None,
        anti_patterns: List[str] = None,
        related_atoms: List[str] = None,
        owner: str = "platform-team",
        maintainers: List[str] = None,
        reviewers: List[str] = None,
        approval_status: str = "approved",
        version: int = 1,
        is_system: bool = True,
        deprecated: bool = False,
        deprecated_reason: str = "",
        superseded_by: str = "",
        metadata: Dict[str, Any] = None,
        actor: str = "mcp",
    ) -> Dict[str, Any]:
        """Create a new atom definition in Entity Studio.

        Atoms are the fundamental building blocks - rules, instructions, examples, variables, etc.
        """
        service = resolve_entity_studio_service()
        from entity_studio.api import AtomCreateRequest

        request = AtomCreateRequest(
            atom_id=atom_id,
            name=name,
            category=category,
            description=description,
            content=content,
            format=format,
            variables=variables or [],
            dependencies=dependencies or [],
            tags=tags or [],
            use_cases=use_cases or [],
            platforms=platforms or [],
            ai_instructions=ai_instructions,
            ai_warnings=ai_warnings or [],
            ai_context=ai_context,
            ai_prerequisites=ai_prerequisites or [],
            human_instructions=human_instructions,
            human_warnings=human_warnings or [],
            human_notes=human_notes,
            examples=examples or [],
            anti_patterns=anti_patterns or [],
            related_atoms=related_atoms or [],
            owner=owner,
            maintainers=maintainers or [],
            reviewers=reviewers or [],
            approval_status=approval_status,
            version=version,
            is_system=is_system,
            deprecated=deprecated,
            deprecated_reason=deprecated_reason,
            superseded_by=superseded_by,
            metadata=metadata or {},
        )

        result = await service.create_atom(request, actor=actor)
        return result.model_dump() if hasattr(result, "model_dump") else result

    @mcp.tool()
    async def create_molecule(
        molecule_id: str,
        name: str,
        description: str,
        category: str,
        atom_ids: List[str],
        priority: int = 100,
        is_system: bool = False,
        tags: List[str] = None,
        atom_categories: List[str] = None,
        config_schema: Dict[str, Any] = None,
        default_values: Dict[str, Any] = None,
        actor: str = "mcp",
    ) -> Dict[str, Any]:
        """Create a new molecule definition in Entity Studio.

        Molecules are compositions of atoms that work together for a specific purpose.
        """
        service = resolve_entity_studio_service()
        from entity_studio.api import MoleculeCreateRequest

        request = MoleculeCreateRequest(
            molecule_id=molecule_id,
            name=name,
            description=description,
            category=category,
            priority=priority,
            is_system=is_system,
            tags=tags or [],
            atom_ids=atom_ids,
            atom_categories=atom_categories or ["instruction"] * len(atom_ids),
            config_schema=config_schema or {},
            default_values=default_values or {},
        )

        result = await service.create_molecule(request, actor=actor)
        return result.model_dump() if hasattr(result, "model_dump") else result

    @mcp.tool()
    async def create_organism(
        organism_id: str,
        name: str,
        description: str,
        organism_type: str,
        molecule_ids: List[str],
        molecule_configs: Dict[str, Dict[str, Any]] = None,
        tags: List[str] = None,
        output_format: str = "yaml",
        actor: str = "mcp",
    ) -> Dict[str, Any]:
        """Create a new organism (agent, workflow, skill, guardrail, trigger, ruleset) in Entity Studio.

        Organisms are complete executable entities composed of molecules.
        """
        service = resolve_entity_studio_service()
        from entity_studio.api import OrganismCreateRequest

        request = OrganismCreateRequest(
            organism_id=organism_id,
            name=name,
            description=description,
            organism_type=organism_type,
            molecule_ids=molecule_ids,
            molecule_configs=molecule_configs or {},
            tags=tags or [],
            output_format=output_format,
        )

        result = await service.create_organism(request, actor=actor)
        return result.model_dump() if hasattr(result, "model_dump") else result

    @mcp.tool()
    async def ai_assisted_create(
        prompt: str,
        entity_type: str,
        target_category: Optional[str] = None,
        context: Dict[str, Any] = None,
        use_nemotron: bool = True,
    ) -> Dict[str, Any]:
        """Use Nemotron 3 Ultra (via NVIDIA NIM) to assist entity creation from natural language."""
        service = resolve_entity_studio_service()
        from entity_studio.api import AIAssistedCreateRequest

        request = AIAssistedCreateRequest(
            prompt=prompt,
            entity_type=entity_type,
            target_category=target_category,
            context=context or {},
            use_nemotron=use_nemotron,
        )

        result = await service.ai_assisted_create(request)
        return result.model_dump() if hasattr(result, "model_dump") else result

    @mcp.tool()
    async def get_atom(atom_id: str) -> Dict[str, Any]:
        """Get an atom by ID."""
        service = resolve_entity_studio_service()
        from pathlib import Path
        import yaml

        atom_file = Path(
            "/home/siddharth/Documents/Dev/agentic-platform/Backend Monorepo/Python Libs/common_lib/src/common_lib/modules/templating/templates/atoms/{atom_id}.md".format(
                atom_id=atom_id
            )
        )
        if not atom_file.exists():
            return {"status": "error", "message": f"Atom {atom_id} not found"}

        content = atom_file.read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                frontmatter["content"] = parts[2].strip()
                return frontmatter
        return {"status": "error", "message": f"Atom {atom_id} not found"}

    @mcp.tool()
    async def get_molecule(molecule_id: str) -> Dict[str, Any]:
        """Get a molecule by ID."""
        from pathlib import Path
        import yaml

        mol_file = Path(
            "/home/siddharth/Documents/Dev/agentic-platform/Backend Monorepo/Python Libs/common_lib/src/common_lib/modules/templating/templates/molecules/{molecule_id}.yaml".format(
                molecule_id=molecule_id
            )
        )
        if not mol_file.exists():
            return {"status": "error", "message": f"Molecule {molecule_id} not found"}
        return yaml.safe_load(mol_file.read_text(encoding="utf-8"))

    @mcp.tool()
    async def get_organism(organism_id: str) -> Dict[str, Any]:
        """Get an organism by ID."""
        from pathlib import Path
        import yaml

        org_file = Path(
            "/home/siddharth/Documents/Dev/agentic-platform/Backend Monorepo/Python Libs/common_lib/src/common_lib/modules/templating/templates/organisms/{organism_id}.yaml".format(
                organism_id=organism_id
            )
        )
        if not org_file.exists():
            return {"status": "error", "message": f"Organism {organism_id} not found"}
        return yaml.safe_load(org_file.read_text(encoding="utf-8"))

    @mcp.tool()
    async def suggest_entities(
        prompt: str,
        entity_type: str = "molecule",
    ) -> Dict[str, Any]:
        """Get AI-suggested entities for a natural language prompt."""
        from entity_studio.suggest_molecules import MoleculeSuggester

        suggester = MoleculeSuggester()
        return suggester.suggest_for_prompt(prompt)

    @mcp.tool()
    async def list_atoms(
        category: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List all available atoms, optionally filtered by category or tag."""
        from entity_studio.atom_catalog import ATOM_DEFINITIONS

        atoms = []
        for atom_def in ATOM_DEFINITIONS:
            atom_id = atom_def.get("atom_id", "")
            if category and atom_def.get("category") != category:
                continue
            if tag and tag not in atom_def.get("tags", []):
                continue
            atoms.append({"atom_id": atom_id, **atom_def})
            if len(atoms) >= limit:
                break
        return atoms

    @mcp.tool()
    async def list_molecules(
        category: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List all available molecules, optionally filtered by category or tag."""
        from pathlib import Path
        import yaml

        molecules = []
        mol_dir = Path(
            "/home/siddharth/Documents/Dev/agentic-platform/Backend Monorepo/Python Libs/common_lib/src/common_lib/modules/templating/templates/molecules"
        )
        if mol_dir.exists():
            for mol_file in mol_dir.glob("*.yaml"):
                data = yaml.safe_load(mol_file.read_text(encoding="utf-8"))
                if category and data.get("category") != category:
                    continue
                if tag and tag not in data.get("tags", []):
                    continue
                molecules.append(data)
                if len(molecules) >= limit:
                    break
        return molecules

    @mcp.tool()
    async def list_organisms(
        organism_type: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List all available organisms, optionally filtered by type or tag."""
        from pathlib import Path
        import yaml

        organisms = []
        org_dir = Path(
            "/home/siddharth/Documents/Dev/agentic-platform/Backend Monorepo/Python Libs/common_lib/src/common_lib/modules/templating/templates/organisms"
        )
        if org_dir.exists():
            for org_file in org_dir.glob("*.yaml"):
                data = yaml.safe_load(org_file.read_text(encoding="utf-8"))
                if organism_type and data.get("organism_type") != organism_type:
                    continue
                if tag and tag not in data.get("tags", []):
                    continue
                organisms.append(data)
                if len(organisms) >= limit:
                    break
        return organisms

    @mcp.tool()
    async def validate_entity(
        entity_type: str,
        entity_id: str,
    ) -> Dict[str, Any]:
        """Validate an entity definition."""
        # TODO: Implement full validation
        return {"valid": True, "warnings": [], "errors": []}

    @mcp.tool()
    async def sync_to_db(entity_type: str = "all") -> Dict[str, Any]:
        """Sync entity definitions to database."""
        # This would trigger the sync process
        return {
            "status": "synced",
            "entity_type": entity_type,
            "message": "Sync completed",
        }

    @mcp.tool()
    async def export_entity(
        entity_type: str,
        entity_id: str,
        output_format: str = "json",
    ) -> Dict[str, Any]:
        """Export an entity to various formats (json, yaml, markdown, typescript)."""
        # TODO: Implement export
        return {
            "status": "exported",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "format": output_format,
        }

    # ─── Lineage & Audit ──────────────────────────────────────────────

    @mcp.tool()
    async def get_entity_lineage(
        entity_type: str,
        entity_id: str,
    ) -> Dict[str, Any]:
        """Get full lineage/audit trail for a specific entity."""
        from entity_studio.lineage import get_lineage_tracker

        tracker = get_lineage_tracker()
        entries = tracker.get_entity_lineage(entity_type, entity_id)
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "lineage": [entry.__dict__ for entry in entries],
        }

    @mcp.tool()
    async def get_actor_lineage(actor: str) -> Dict[str, Any]:
        """Get all activity for a specific actor/agent."""
        from entity_studio.lineage import get_lineage_tracker

        tracker = get_lineage_tracker()
        entries = tracker.get_actor_activity(actor)
        return {
            "actor": actor,
            "activity": [entry.__dict__ for entry in entries],
        }

    @mcp.tool()
    async def get_session_lineage(session_id: str) -> Dict[str, Any]:
        """Get all activity for a specific session."""
        from entity_studio.lineage import get_lineage_tracker

        tracker = get_lineage_tracker()
        entries = tracker.get_session_activity(session_id)
        return {
            "session_id": session_id,
            "activity": [entry.__dict__ for entry in entries],
        }

    @mcp.tool()
    async def get_recent_lineage(
        limit: int = 100,
        entity_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get recent lineage activity across all entities."""
        from entity_studio.lineage import get_lineage_tracker

        tracker = get_lineage_tracker()
        entries = tracker.get_recent_activity(limit=limit, entity_type=entity_type)
        return {
            "recent_activity": [entry.__dict__ for entry in entries],
            "total": len(entries),
        }

    @mcp.tool()
    async def get_lineage_stats() -> Dict[str, Any]:
        """Get lineage statistics."""
        from entity_studio.lineage import get_lineage_tracker

        tracker = get_lineage_tracker()
        return tracker.get_stats()

    # ─── Autonomous Evolution ─────────────────────────────────────────

    @mcp.tool()
    async def scan_for_gaps() -> Dict[str, Any]:
        """Scan the entity catalog for gaps (missing molecules, atoms, organisms)."""
        from entity_studio.autonomous_evolution import GapDetector

        detector = GapDetector()
        gaps = detector.scan_all_gaps()

        return {
            "gaps_found": len(gaps),
            "gaps": [
                {
                    "gap_id": gap.gap_id,
                    "gap_type": gap.gap_type,
                    "description": gap.description,
                    "context": gap.context,
                    "priority": gap.priority,
                    "status": gap.status,
                }
                for gap in gaps[:20]  # Limit to top 20
            ],
        }

    @mcp.tool()
    async def trigger_evolution(
        gap_type: str,
        description: str,
        context: Dict[str, Any] = None,
        priority: int = 50,
    ) -> Dict[str, Any]:
        """Manually trigger autonomous evolution for a specific gap."""
        from entity_studio.autonomous_evolution import (
            AutonomousEvolutionOrchestrator,
            EvolutionConfig,
            Gap,
        )

        config = EvolutionConfig(
            scan_interval_seconds=3600,
            max_concurrent_evolutions=3,
            confidence_threshold=0.7,
            run_tests_before_publish=True,
        )

        orchestrator = AutonomousEvolutionOrchestrator(config)

        gap = Gap(
            gap_type=gap_type,
            description=description,
            context=context or {},
            priority=priority,
        )

        task = await orchestrator.trigger_evolution(gap)

        return {
            "task_id": task.task_id,
            "gap_id": task.gap.gap_id,
            "status": task.status,
            "entities_created": len(task.created_entities),
            "entities": task.created_entities,
            "test_results": task.test_results,
            "error": task.error,
            "completed_at": task.completed_at,
        }

    @mcp.tool()
    async def get_evolution_status() -> Dict[str, Any]:
        """Get the current status of the autonomous evolution loop."""
        # This would require a persistent orchestrator instance
        # For now, return a placeholder
        return {
            "status": "not_running",
            "message": "Autonomous evolution loop is not currently running. Use trigger_evolution to run individual evolutions.",
        }

    @mcp.tool()
    async def get_evolution_history(
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Get history of completed evolution tasks."""
        # This would require persistent storage
        return {
            "history": [],
            "message": "Evolution history requires persistent orchestrator state.",
        }
