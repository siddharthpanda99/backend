import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Query
from app.modules.plugins.schemas.plugin_schemas import (
    PluginResponse,
    NodeCandidateSchema,
    OnboardRequest,
    PluginDetailResponse,
    NodeDefinitionSchema,
    HealthStatus,
    PluginType,
    PluginUpdateRequest,
)
from common_lib.modules.plugins.manager import PluginManager
from common_lib.modules.plugins.schemas import ExtractionCandidate

# Path constants for project KB - compute at module load time from this file's location
_DOCS_BASE = (
    Path(__file__).resolve().parent.parent.parent.parent.parent.parent
    / "Python Libs/common_lib/docs"
)
_KB_BASE = (
    Path(__file__).resolve().parent.parent.parent.parent.parent.parent / "Knowledgebase"
)


def _load_kb_graph() -> dict:
    """Load unified project graph from Apache AGE + Knowledgebase filesystem."""
    from app.modules.database.service.connection import engine
    from sqlalchemy import text
    import logging
    import re
    from pathlib import Path

    logger = logging.getLogger(__name__)

    memo_graph = {
        "graph": {
            "id": "unified_super_graph",
            "name": "Unified Super Graph",
            "version": "2.0.0",
        },
        "nodes": [],
        "edges": [],
        "categories": [],
    }

    category_colors = {
        "Core": "#6366f1",
        "Evolution": "#8b5cf6",
        "Features": "#f59e0b",
        "Walkthroughs": "#10b981",
        "Vision": "#f97316",
        "Engine": "#ec4899",
        "Agent": "#a855f7",
        "Workflow": "#22c55e",
        "Procedure": "#3b82f6",
        "Memory": "#06b6d4",
        "Tag": "#94a3b8",
    }

    categories = set()
    node_id_lookup = set()
    all_tags: dict[str, list[str]] = {}

    try:
        with engine.connect() as conn:
            conn.execute(text("LOAD 'age';"))
            conn.execute(text('SET search_path = ag_catalog, "$user", public;'))

            node_query = """
            SELECT * FROM cypher('super_graph', $q$
                MATCH (n) RETURN n
            $q$) as (n agtype);
            """
            query_result = conn.execute(text(node_query))

            for row in query_result:
                node_raw = row[0]
                node_data = {}

                if isinstance(node_raw, str):
                    clean_json = (
                        node_raw.split("::")[0] if "::" in node_raw else node_raw
                    )
                    try:
                        node_data = json.loads(clean_json)
                    except:
                        logger.error(f"Failed to parse AGE node: {node_raw}")
                        continue
                elif isinstance(node_raw, dict):
                    node_data = node_raw
                else:
                    node_data = getattr(node_raw, "__dict__", {})

                props = node_data.get("properties", {})
                node_id = str(props.get("id") or str(node_data.get("id", "")))

                if not node_id or node_id == "None":
                    continue

                cat = str(
                    props.get("category") or props.get("type") or "Knowledge"
                ).capitalize()
                categories.add(cat)
                node_id_lookup.add(node_id)

                node_tags = [str(t) for t in props.get("tags", [])]
                memo_graph["nodes"].append(
                    {
                        "id": node_id,
                        "label": str(
                            props.get("name") or props.get("filename") or node_id
                        ),
                        "category": cat,
                        "description": str(
                            props.get("description") or props.get("filename") or ""
                        ),
                        "doc": str(props.get("filename", ""))
                        if props.get("filename")
                        else None,
                        "tags": node_tags,
                        "entity_type": str(props.get("type", "doc")),
                    }
                )
                if node_tags:
                    all_tags[node_id] = node_tags

            edge_query = """
            SELECT * FROM cypher('super_graph', $q$
                MATCH (a)-[r]->(b) 
                WHERE a.id IS NOT NULL AND b.id IS NOT NULL
                RETURN a.id, b.id, label(r)
            $q$) as (a_id agtype, b_id agtype, rel_label agtype);
            """
            edges_result = conn.execute(text(edge_query))

            for row in edges_result:
                from_id = (
                    str(row[0]).split("::")[0].strip('"')
                    if row[0] is not None
                    else None
                )
                to_id = (
                    str(row[1]).split("::")[0].strip('"')
                    if row[1] is not None
                    else None
                )
                rel = (
                    str(row[2]).split("::")[0].strip('"')
                    if row[2] is not None
                    else "CONNECTED"
                )

                if from_id == "None" or to_id == "None" or not from_id or not to_id:
                    continue

                if from_id not in node_id_lookup or to_id not in node_id_lookup:
                    continue

                memo_graph["edges"].append(
                    {
                        "from": from_id,
                        "to": to_id,
                        "label": rel,
                        "type": "explicit" if rel == "LINKS_TO" else "tag",
                    }
                )

    except Exception as e:
        logger.error(f"Failed to load KB graph from AGE: {e}")

    has_db_nodes = len(memo_graph["nodes"]) > 0

    if not has_db_nodes:
        logger.info("No nodes from AGE, falling back to filesystem KB scan")

        wikilink_pattern = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
        hashtag_pattern = re.compile(r"#([A-Za-z][A-Za-z0-9_]+)")

        def scan_markdown_files(base_path: Path, category: str) -> list[dict]:
            nodes = []
            if not base_path.exists():
                return nodes
            for md_file in base_path.rglob("*.md"):
                if "__pycache__" in str(md_file) or md_file.stat().st_size == 0:
                    continue
                try:
                    content = md_file.read_text(encoding="utf-8", errors="ignore")
                except:
                    continue

                rel_path = str(md_file.relative_to(base_path))
                node_id = rel_path.replace("\\", "/").replace(".md", "")

                title = md_file.stem
                if node_id == "INDEX" or node_id == "README":
                    title = md_file.parent.name or title

                tags = hashtag_pattern.findall(content)
                wikilinks = wikilink_pattern.findall(content)

                description = (
                    content[:200].replace("\n", " ").strip() if content else ""
                )

                nodes.append(
                    {
                        "id": node_id,
                        "label": title,
                        "category": category,
                        "description": description,
                        "doc": rel_path.replace("\\", "/"),
                        "tags": list(set(tags)),
                        "entity_type": "doc",
                        "_wikilinks": wikilinks,
                        "_source_path": str(md_file),
                    }
                )

                if tags:
                    all_tags[node_id] = list(set(tags))
                node_id_lookup.add(node_id)

            return nodes

        docs_base = _DOCS_BASE
        kb_base = _KB_BASE

        for path, cat in [(docs_base, "Engine"), (kb_base, "Knowledge")]:
            file_nodes = scan_markdown_files(path, cat)
            memo_graph["nodes"].extend(file_nodes)
            if file_nodes:
                categories.add(cat)

        explicit_edges = []
        tag_edges = []

        for node in memo_graph["nodes"]:
            wikilinks = node.get("_wikilinks", [])
            for wl in wikilinks:
                target_id = wl.replace("\\", "/").replace(".md", "")
                if target_id in node_id_lookup:
                    explicit_edges.append(
                        {
                            "from": node["id"],
                            "to": target_id,
                            "label": "LINKS_TO",
                            "type": "explicit",
                        }
                    )

        tag_to_nodes: dict[str, list[str]] = {}
        for node_id, tags in all_tags.items():
            for tag in tags:
                if tag not in tag_to_nodes:
                    tag_to_nodes[tag] = []
                tag_to_nodes[tag].append(node_id)

        for tag, node_ids in tag_to_nodes.items():
            if len(node_ids) > 1:
                for i, from_id in enumerate(node_ids):
                    for to_id in node_ids[i + 1 :]:
                        tag_edges.append(
                            {
                                "from": from_id,
                                "to": to_id,
                                "label": f"shares#{tag}",
                                "type": "conceptual",
                                "weight": len(node_ids),
                            }
                        )

        memo_graph["edges"].extend(explicit_edges)
        memo_graph["edges"].extend(tag_edges)

        for wl_node in memo_graph["nodes"]:
            wl_node.pop("_wikilinks", None)
            wl_node.pop("_source_path", None)

    for cat_name in categories:
        memo_graph["categories"].append(
            {
                "id": cat_name,
                "color": category_colors.get(cat_name, "#6366f1"),
                "label": cat_name,
            }
        )

    memo_graph["_analytics"] = _compute_graph_analytics(
        memo_graph["nodes"], memo_graph["edges"]
    )

    logger.info(
        f"Loaded KB graph: {len(memo_graph['nodes'])} nodes, {len(memo_graph['edges'])} edges"
    )
    return memo_graph


def _compute_graph_analytics(nodes: list[dict], edges: list[dict]) -> dict:
    """Compute basic graph analytics: centrality, communities, gaps."""
    from collections import defaultdict
    import math

    if not nodes or not edges:
        return {}

    adj: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        f, t = e.get("from"), e.get("to")
        if f and t:
            adj[f].add(t)
            adj[t].add(f)

    node_ids = {n["id"] for n in nodes}
    centrality: dict[str, float] = {nid: 0.0 for nid in node_ids}

    for source in node_ids:
        if source not in adj:
            continue
        bfs_dist = {source: 0}
        q = [source]
        idx = 0
        while idx < len(q):
            cur = q[idx]
            idx += 1
            for nb in adj.get(cur, []):
                if nb not in bfs_dist:
                    bfs_dist[nb] = bfs_dist[cur] + 1
                    q.append(nb)
            for intermediary in q[:idx]:
                d_inter = bfs_dist[intermediary]
                d_cur = bfs_dist.get(cur, 0)
                if d_inter < d_cur:
                    for nb in adj.get(cur, []):
                        if nb in bfs_dist and bfs_dist[nb] > d_inter:
                            centrality[intermediary] = (
                                centrality.get(intermediary, 0) + 1
                            )

    max_c = max(centrality.values()) if centrality.values() else 1
    for nid in centrality:
        centrality[nid] = round(centrality[nid] / max_c, 3) if max_c > 0 else 0

    tag_freq: dict[str, int] = defaultdict(int)
    for n in nodes:
        for t in n.get("tags", []):
            tag_freq[t] += 1

    common_tags = sorted(tag_freq.items(), key=lambda x: -x[1])[:20]

    community_nodes: dict[str, list[str]] = defaultdict(list)
    for n in nodes:
        cats = n.get("tags", [])
        if cats:
            community_nodes[cats[0]].append(n["id"])
    communities = [
        {"id": t, "label": t, "node_count": len(ns), "nodes": ns[:10]}
        for t, ns in sorted(community_nodes.items(), key=lambda x: -len(x[1]))[:10]
    ]

    all_tags_set = set(tag_freq.keys())
    gaps = []
    connected_tags: set[str] = set()
    for e in edges:
        if e.get("type") == "conceptual":
            lbl = e.get("label", "")
            if lbl.startswith("shares#"):
                connected_tags.add(lbl[7:])
    for tag in all_tags_set - connected_tags:
        if tag_freq[tag] >= 2:
            gaps.append({"tag": tag, "frequency": tag_freq[tag], "type": "unlinked"})

    return {
        "centrality": centrality,
        "top_tags": common_tags,
        "communities": communities,
        "gaps": gaps[:10],
    }


# Cache for KB graph
_KB_GRAPH_CACHE = None

router = APIRouter(tags=["Plugins"])
plugin_manager = PluginManager()
plugin_manager.start()

from app.core.common_lib_integration import common_memory


@router.get("", response_model=List[PluginResponse])
@router.get("/", response_model=List[PluginResponse])
async def list_plugins():
    """
    Returns a list of all installed and discovered plugins with rich metadata from DB.
    """
    # 1. Fetch all plugin definitions from PostgreSQL
    records = common_memory.list_plugin_definitions()

    # 2. Get active engine plugins for status/health checks
    engine_plugins = {p.id: p for p in plugin_manager.engine.list_plugins()}

    results = []
    for p in records:
        # Determine status: HEALTHY if in engine, DISCOVERED otherwise (or based on artifacts)
        status = HealthStatus.HEALTHY
        p_type = PluginType.EXTERNAL

        p_id = p.get("id")
        p_artifacts = p.get("artifacts") or {}

        if p_id in engine_plugins:
            instance = engine_plugins[p_id]
            # Map healthy to ACTIVE for frontend marker consistency
            if instance.check_health().status == HealthStatus.HEALTHY:
                status = HealthStatus.ACTIVE
            else:
                status = instance.check_health().status
            p_type = instance.metadata.plugin_type
        else:
            # Check if it was discovered by RegistryStabilizer
            yaml_path = p_artifacts.get("yaml_path", "")
            if "discovered" in yaml_path:
                status = (
                    HealthStatus.ACTIVE
                )  # Show as installed/active if successfully stabilized
            else:
                status = HealthStatus.INACTIVE

        p_nodes_list = p.get("nodes_list") or []
        node_count = len(p_nodes_list)

        # Format human-readable date
        raw_updated = p.get("updated_at")
        if hasattr(raw_updated, "strftime"):
            updated_str = raw_updated.strftime("%Y-%m-%d")
        elif isinstance(raw_updated, str):
            updated_str = raw_updated[:10]
        else:
            updated_str = "2024-04-16"

        results.append(
            PluginResponse(
                id=p_id,
                name=p.get("name") or p_id,
                description=p.get("description"),
                category=p.get("category") or "general",
                version=p.get("version") or "1.0.0",
                status=status,
                plugin_type=p_type,
                node_count=node_count,
                total_nodes=node_count,
                active_node_count=node_count,
                author_url=p.get("author_url"),
                thumbnail_url=p.get("thumbnail_url"),
                downloads_count=p.get("downloads_count") or 0,
                updated_at=updated_str,
                author=p.get("author") or "Nexus Official",
                tags=p.get("tags") or [],
            )
        )
    return results


@router.get("/{plugin_id}", response_model=PluginDetailResponse)
async def get_plugin_details(plugin_id: str):
    """
    Returns full details for a specific plugin, including its tools from DB.
    """
    p = common_memory.get_plugin_definition(plugin_id)
    if not p:
        raise HTTPException(status_code=404, detail="Plugin not found")

    engine_plugins = {p.id: p for p in plugin_manager.engine.list_plugins()}
    status = HealthStatus.ACTIVE if plugin_id in engine_plugins else HealthStatus.ACTIVE
    p_type = (
        engine_plugins[plugin_id].metadata.plugin_type
        if plugin_id in engine_plugins
        else PluginType.EXTERNAL
    )

    # Fetch tool details for all nodes in the list
    nodes = []
    p_nodes_list = p.get("nodes_list") or []
    # Path: Backend/app/modules/plugins/routes/router.py -> Backend Monorepo/Python Libs/common_lib/src/common_lib/templates/tools/discovered
    templates_root = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "Python Libs"
        / "common_lib"
        / "src"
        / "common_lib"
        / "templates"
        / "tools"
        / "discovered"
    )

    for node_id in p_nodes_list:
        node_record = common_memory.get_tool_definition(node_id)
        defn: Dict[str, Any] = {}
        capability: Dict[str, Any] = {}
        description = ""
        parameters = {}

        # First try DB - data is nested in definition.nodes_list[0].capability
        if node_record:
            defn = node_record.get("definition") or {}
            nodes_list = defn.get("nodes_list", [])
            # Find the tool in nodes_list that matches node_id
            for node_data in nodes_list:
                if isinstance(node_data, dict) and node_data.get("id") == node_id:
                    capability = node_data.get("capability") or node_data or {}
                    defn = node_data
                    break
            # Fallback if no nested match
            if not capability:
                capability = defn.get("capability") or {}

        # If no capability in DB, read directly from YAML file
        if not capability:
            yaml_file = templates_root / f"{node_id}.tool.yaml"
            if yaml_file.exists():
                try:
                    with open(yaml_file) as f:
                        yaml_def = yaml.safe_load(f) or {}
                        capability = yaml_def.get("capability") or yaml_def or {}
                        defn = yaml_def
                except Exception:
                    pass

        if capability:
            description = capability.get("description") or defn.get("description") or ""

            # NEW SCHEMA: input_schema
            if capability.get("input_schema"):
                input_schema_dict = capability.get("input_schema", {})
                if isinstance(input_schema_dict, dict):
                    input_props = input_schema_dict.get("properties", {})
                    input_required = input_schema_dict.get("required", [])
                else:
                    input_props = {}
                    input_required = []
            # OLD SCHEMA: capability.parameters.properties
            elif capability.get("parameters"):
                params = capability.get("parameters", {})
                input_props = params.get("properties", {})
                input_required = params.get("required", list(input_props.keys()))
            else:
                input_props = {}
                input_required = []

            # NEW SCHEMA: output_schema
            output_schema = (
                capability.get("output_schema") or defn.get("output_schema") or {}
            )
            if isinstance(output_schema, dict) and "description" in output_schema:
                output_schema = {
                    "type": "object",
                    "properties": {},
                    "description": output_schema.get("description"),
                }
        else:
            description = ""
            input_props = {}
            input_required = []
            output_schema = {}

        name = defn.get("name") or node_id.split(".")[-1].replace("_", " ").title()

        # Build input_schema as plain dict - NOT via Pydantic model to avoid defaults
        input_schema_obj = None
        if input_props:
            clean_props = {}
            for prop_name, prop_val in input_props.items():
                if isinstance(prop_val, dict):
                    # Only keep non-None values from the source data
                    clean_val = {k: v for k, v in prop_val.items() if v is not None}
                    if clean_val:
                        clean_props[prop_name] = clean_val
            if clean_props:
                input_schema_obj = {
                    "type": "object",
                    "properties": clean_props,
                    "required": input_required,
                }

        # Clean output_schema as plain dict
        clean_output = None
        if output_schema and isinstance(output_schema, dict):
            clean_output = {k: v for k, v in output_schema.items() if v is not None}
            if not clean_output:
                clean_output = None

        nodes.append(
            NodeDefinitionSchema(
                id=node_id,
                name=name,
                description=description,
                category=defn.get("category"),
                version=defn.get("version", "1.0.0"),
                tags=defn.get("tags", []),
                audience=capability.get("audience")
                or defn.get("audience")
                or ["executor"],
                input_schema=input_schema_obj,
                output_schema=clean_output,
                execution_timeout=capability.get("execution_timeout")
                or defn.get("execution_timeout")
                or 60,
                execution_mode=capability.get("execution_mode")
                or defn.get("execution_mode")
                or "sync",
                cacheable=capability.get("cacheable") or defn.get("cacheable") or False,
                idempotent=capability.get("idempotent")
                or defn.get("idempotent")
                or False,
                metadata=defn.get("metadata"),
            )
        )

    node_count = len(p_nodes_list)

    # Format human-readable date
    raw_updated = p.get("updated_at")
    if hasattr(raw_updated, "strftime"):
        updated_one_str = raw_updated.strftime("%Y-%m-%d")
    elif isinstance(raw_updated, str):
        updated_one_str = raw_updated[:10]
    else:
        updated_one_str = "2024-04-16"

    return PluginDetailResponse(
        id=p.get("id"),
        name=p.get("name"),
        description=p.get("description"),
        category=p.get("category") or "general",
        version=p.get("version") or "1.0.0",
        status=status,
        plugin_type=p_type,
        node_count=node_count,
        total_nodes=node_count,
        active_node_count=node_count,
        author=p.get("author") or "Nexus Official",
        author_url=p.get("author_url"),
        thumbnail_url=p.get("thumbnail_url"),
        downloads_count=p.get("downloads_count") or 0,
        updated_at=updated_one_str,
        tags=p.get("tags") or [],
        nodes=nodes,
    )


@router.post("/analyze", response_model=List[NodeCandidateSchema])
async def analyze_plugin(file: UploadFile = File(...)):
    """
    Uploads a python plugin file and returns candidate nodes found via static analysis.
    """
    if not file.filename.endswith(".py"):
        raise HTTPException(
            status_code=400, detail="Only .py files are supported for analysis."
        )

    # Save to a temporary location for analysis
    temp_dir = Path("resources/temp_uploads")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file.filename

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        candidates = plugin_manager.analyze_plugin_file(temp_path)
        return [
            NodeCandidateSchema(
                name=c.name,
                description=c.description,
                parameters=c.parameters,
                module_path=str(temp_path),
            )
            for c in candidates
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/onboard")
async def onboard_plugin_tools(
    plugin_id: str = Form(...),
    name: str = Form(...),
    category: str = Form("general"),
    author: str = Form("System"),
    author_url: Optional[str] = Form(None),
    thumbnail_url: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # Comma separated
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
):
    """
    Comprehensive onboarding endpoint:
    1. Uploads ZIP or .py file.
    2. Extracts and analyzes tools.
    3. Generates enriched Plugin and Tool YAMLs.
    """
    # Create temp directory for upload
    temp_dir = Path("resources/temp_uploads")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file.filename

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Prepare metadata for PluginManager
        metadata = {
            "description": description,
            "author_url": author_url,
            "thumbnail_url": thumbnail_url,
            "tags": [tag.strip() for tag in tags.split(",")] if tags else [],
        }

        # Determine if it's a zip or py
        if file.filename.endswith(".zip"):
            result = plugin_manager.onboard_plugin(
                plugin_id=plugin_id,
                name=name,
                zip_path=temp_path,
                metadata=metadata,
                category=category,
                author=author,
            )
        elif file.filename.endswith(".py"):
            with open(temp_path, "r", encoding="utf-8") as f:
                code = f.read()
            result = plugin_manager.onboard_plugin(
                plugin_id=plugin_id,
                name=name,
                source_code=code,
                metadata=metadata,
                category=category,
                author=author,
            )
        else:
            raise HTTPException(
                status_code=400, detail="Unsupported file type. Use .zip or .py"
            )

        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()

        return result

    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(status_code=500, detail=f"Onboarding failed: {str(e)}")


@router.patch("/{plugin_id}", response_model=PluginResponse)
async def update_plugin(plugin_id: str, request: PluginUpdateRequest):
    """Update plugin metadata."""
    existing = common_memory.get_plugin_definition(plugin_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Merge existing with update request
    update_data = request.dict(exclude_unset=True)

    # name is a required positional arg in save_plugin_definition signature
    name = update_data.pop("name", existing["name"])

    try:
        common_memory.save_plugin_definition(
            plugin_id=plugin_id, name=name, **update_data
        )

        # Return updated state
        p = common_memory.get_plugin_definition(plugin_id)

        # Re-use status determination logic from list_plugins if needed,
        # but for PATCH return, a simple response is usually enough as long as status matches schema.
        # However, PluginResponse requires all fields.

        # Determine status (consistent with list_plugins logic)
        engine_plugins = {
            p_inst.id: p_inst for p_inst in plugin_manager.engine.list_plugins()
        }
        status = (
            HealthStatus.ACTIVE if plugin_id in engine_plugins else HealthStatus.ACTIVE
        )
        tags = p.get("tags") or []

        # Format human-readable date
        raw_updated = p.get("updated_at")
        if hasattr(raw_updated, "strftime"):
            updated_str = raw_updated.strftime("%Y-%m-%d")
        elif isinstance(raw_updated, str):
            updated_str = raw_updated[:10]
        else:
            updated_str = "2024-04-16"

        return PluginResponse(
            id=p.get("id"),
            name=p.get("name"),
            description=p.get("description"),
            category=p.get("category") or "general",
            version=p.get("version") or "1.0.0",
            status=status,
            plugin_type=PluginType.EXTERNAL,  # Fallback for discovered/external
            node_count=len(p.get("nodes_list") or []),
            total_nodes=len(p.get("nodes_list") or []),
            active_node_count=len(p.get("nodes_list") or []),
            author_url=p.get("author_url"),
            thumbnail_url=p.get("thumbnail_url"),
            downloads_count=p.get("downloads_count") or 0,
            updated_at=updated_str,
            author=p.get("author") or "Nexus Official",
            tags=tags,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{plugin_id}")
async def delete_plugin(plugin_id: str):
    """Remove plugin definition from registry."""
    success = common_memory.delete_plugin_definition(plugin_id)
    if not success:
        raise HTTPException(status_code=404, detail="Plugin not found")

    return {"status": "success", "message": f"Plugin {plugin_id} deleted"}


# ==================== Project KB / Documentation ====================


@router.get("/project-kb/graph")
async def get_project_kb_graph(refresh: bool = Query(False)):
    """
    Returns the project knowledge base graph for visualization.
    Syncs all docs/*.md files and returns them as nodes.
    """
    global _KB_GRAPH_CACHE
    if _KB_GRAPH_CACHE is None or refresh:
        _KB_GRAPH_CACHE = _load_kb_graph()
    return _KB_GRAPH_CACHE


@router.get("/project-kb/nodes")
async def get_project_kb_nodes():
    """Returns all wiki nodes for documentation browser."""
    graph = await get_project_kb_graph()
    return {"nodes": graph.get("nodes", []), "categories": graph.get("categories", [])}


@router.get("/project-kb/node/{node_id}")
async def get_project_kb_node(node_id: str):
    """Returns details for a specific wiki node."""
    graph = await get_project_kb_graph()
    for node in graph.get("nodes", []):
        if node.get("id") == node_id:
            return node
    raise HTTPException(status_code=404, detail=f"Node {node_id} not found")


@router.get("/project-kb/search")
async def search_project_kb(q: str = ""):
    """Search wiki nodes by label or description."""
    graph = await get_project_kb_graph()
    query = q.lower()
    results = []
    for node in graph.get("nodes", []):
        if (
            query in node.get("label", "").lower()
            or query in node.get("description", "").lower()
        ):
            results.append(node)
    return {"results": results, "query": q}


@router.get("/docs/{doc_path:path}")
async def get_doc_content(doc_path: str):
    """Returns raw documentation content from markdown files."""
    docs_path = _DOCS_BASE / doc_path
    if not docs_path.exists():
        docs_path = _DOCS_BASE / f"{doc_path}.md"
    if docs_path.exists():
        with open(docs_path, "r", encoding="utf-8") as f:
            content = f.read()
            return {"content": content, "path": doc_path, "format": "markdown"}
    raise HTTPException(status_code=404, detail=f"Documentation {doc_path} not found")
