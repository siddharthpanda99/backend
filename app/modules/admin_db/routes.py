"""
Admin Database API Routes — thin wrapper around common_lib services.

All business logic lives in common_lib.modules.admin_db.service.
These routes only handle HTTP concerns: request parsing, dependency injection, response formatting.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException

from common_lib.modules.admin_db.service import (
    ConnectionService,
    SchemaInspectorService,
    QueryExecutorService,
    DataBrowserService,
    HealthMonitorService,
    SchemaManagerService,
    ExportService,
    AiAssistantService,
    DbtStudioService,
    DbtFreshnessService,
    DbtColumnLineageService,
    DbtDocService,
    PipelineService,
)
from common_lib.modules.admin_db.schemas import (
    ConnectionProfileCreate,
    ConnectionProfileUpdate,
    ConnectionTestRequest,
    QueryExecuteRequest,
    DataBrowserRequest,
    RowInsertRequest,
    RowUpdateRequest,
    RowDeleteRequest,
    CreateTableRequest,
    AlterTableRequest,
    DropTableRequest,
    CreateIndexRequest,
    DropIndexRequest,
    CreateViewRequest,
    DropViewRequest,
    CreateSchemaRequest,
    DropSchemaRequest,
    ExportRequest,
    AiGenerateRequest,
    DbtProjectCreate,
    DbtModelSaveRequest,
    DbtCompileRequest,
    DbtRunRequest,
    DbtTestRequest,
    PipelineCreate,
    PipelineNodeCreate,
    PipelineNodeUpdate,
    PipelineEdgeCreate,
    PipelineRunRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin-db", tags=["Admin Database"])


# =============================================================================
# Connection Profile Endpoints
# =============================================================================


@router.get("/connections")
def list_connections(
    search: Optional[str] = Query(None),
    db_type: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List saved database connection profiles."""
    return ConnectionService.list_profiles(search=search, db_type=db_type, offset=offset, limit=limit)


@router.get("/connections/{profile_id}")
def get_connection(profile_id: str):
    """Get a single connection profile by ID."""
    return ConnectionService.get_profile(profile_id)


@router.post("/connections")
def create_connection(data: ConnectionProfileCreate):
    """Create a new database connection profile."""
    return ConnectionService.create_profile(data)


@router.put("/connections/{profile_id}")
def update_connection(profile_id: str, data: ConnectionProfileUpdate):
    """Update an existing connection profile."""
    return ConnectionService.update_profile(profile_id, data)


@router.delete("/connections/{profile_id}")
def delete_connection(profile_id: str):
    """Delete a connection profile."""
    return ConnectionService.delete_profile(profile_id)


@router.post("/connections/test")
def test_connection(data: ConnectionTestRequest):
    """Test a database connection (from profile or inline details)."""
    return ConnectionService.test_connection(data)


# =============================================================================
# Schema Inspector Endpoints
# =============================================================================


@router.get("/schemas/{profile_id}")
def list_schemas(profile_id: str):
    """List all schemas in a connected database."""
    return SchemaInspectorService.list_schemas(profile_id)


@router.get("/schemas/{profile_id}/tables")
def list_tables(profile_id: str, schema: str = Query("public")):
    """List all tables in a schema."""
    return SchemaInspectorService.list_tables(profile_id, schema)


@router.get("/schemas/{profile_id}/overview")
def get_full_schema(profile_id: str):
    """Get complete schema overview (all schemas, tables)."""
    result = SchemaInspectorService.get_full_schema(profile_id)
    return result.model_dump()


@router.get("/schemas/{profile_id}/tables/{schema}/{table}")
def get_table_info(profile_id: str, schema: str, table: str):
    """Get full table info: columns, constraints, indexes."""
    result = SchemaInspectorService.get_table_info(profile_id, schema, table)
    return result.model_dump()


@router.get("/schemas/{profile_id}/tables/{schema}/{table}/columns")
def get_columns(profile_id: str, schema: str, table: str):
    """Get column details for a table."""
    return SchemaInspectorService.get_columns(profile_id, schema, table)


@router.get("/schemas/{profile_id}/tables/{schema}/{table}/constraints")
def get_constraints(profile_id: str, schema: str, table: str):
    """Get constraints for a table."""
    return SchemaInspectorService.get_constraints(profile_id, schema, table)


@router.get("/schemas/{profile_id}/tables/{schema}/{table}/indexes")
def get_indexes(profile_id: str, schema: str, table: str):
    """Get indexes for a table."""
    return SchemaInspectorService.get_indexes(profile_id, schema, table)


# =============================================================================
# Query Execution Endpoints
# =============================================================================


@router.post("/query")
def execute_query(data: QueryExecuteRequest):
    """Execute a SQL query against a connected database."""
    return QueryExecutorService.execute(data)


# =============================================================================
# EXPLAIN ANALYZE
# =============================================================================


@router.post("/explain")
def explain_query(data: QueryExecuteRequest):
    """Run EXPLAIN ANALYZE on a SQL query."""
    return QueryExecutorService.explain_analyze(data.profile_id, data.sql)


# =============================================================================
# Data Browser Endpoints
# =============================================================================


@router.post("/data")
def fetch_data(data: DataBrowserRequest):
    """Fetch paginated, sortable, filterable data from a table."""
    return DataBrowserService.fetch_data(data)


@router.post("/data/rows")
def insert_row(data: RowInsertRequest):
    """Insert a row into a table."""
    return DataBrowserService.insert_row(data)


@router.put("/data/rows")
def update_row(data: RowUpdateRequest):
    """Update a row by primary key."""
    return DataBrowserService.update_row(data)


@router.delete("/data/rows")
def delete_row(data: RowDeleteRequest):
    """Delete a row by primary key."""
    return DataBrowserService.delete_row(data)


# =============================================================================
# Health Monitor Endpoints
# =============================================================================


@router.get("/health/{profile_id}")
def get_health_stats(profile_id: str):
    """Get comprehensive database health statistics."""
    return HealthMonitorService.get_stats(profile_id)


@router.get("/health/{profile_id}/indexes")
def get_index_usage(profile_id: str):
    """G3: Index usage statistics (scan counts, unused indexes, sizes)."""
    return HealthMonitorService.get_index_usage(profile_id)


@router.get("/health/{profile_id}/connections")
def get_connection_monitor(profile_id: str):
    """G5: Connection monitor (by state, user, app, idle time)."""
    return HealthMonitorService.get_connection_monitor(profile_id)


@router.get("/health/{profile_id}/bloat")
def get_table_bloat(profile_id: str):
    """G7: Table bloat analysis (dead tuples, VACUUM candidates)."""
    return HealthMonitorService.get_table_bloat(profile_id)


# =============================================================================
# Schema Manager (DDL) Endpoints
# =============================================================================


@router.post("/ddl/create-table")
def create_table(data: CreateTableRequest):
    return SchemaManagerService.create_table(data)


@router.post("/ddl/alter-table")
def alter_table(data: AlterTableRequest):
    return SchemaManagerService.alter_table(data)


@router.post("/ddl/drop-table")
def drop_table(data: DropTableRequest):
    return SchemaManagerService.drop_table(data)


@router.post("/ddl/create-index")
def create_index(data: CreateIndexRequest):
    return SchemaManagerService.create_index(data)


@router.post("/ddl/drop-index")
def drop_index(data: DropIndexRequest):
    return SchemaManagerService.drop_index(data)


@router.post("/ddl/create-view")
def create_view(data: CreateViewRequest):
    return SchemaManagerService.create_view(data)


@router.post("/ddl/drop-view")
def drop_view(data: DropViewRequest):
    return SchemaManagerService.drop_view(data)


@router.post("/ddl/create-schema")
def create_schema(data: CreateSchemaRequest):
    return SchemaManagerService.create_schema(data)


@router.post("/ddl/drop-schema")
def drop_schema(data: DropSchemaRequest):
    return SchemaManagerService.drop_schema(data)


# ── Introspection endpoints for sub-tabs ─────────────────────────

@router.get("/schemas/{profile_id}/views")
def list_views(profile_id: str, schema: str = Query("public")):
    return SchemaManagerService.list_views(profile_id, schema)


@router.get("/schemas/{profile_id}/indexes")
def list_all_indexes(profile_id: str, schema: str = Query("public")):
    return SchemaManagerService.list_indexes(profile_id, schema)


@router.get("/schemas/{profile_id}/enums")
def list_enums(profile_id: str, schema: str = Query("public")):
    return SchemaManagerService.list_enums(profile_id, schema)


@router.get("/schemas/{profile_id}/functions")
def list_functions(profile_id: str, schema: str = Query("public")):
    return SchemaManagerService.list_functions(profile_id, schema)


# =============================================================================
# Export Endpoints
# =============================================================================


@router.post("/export")
def export_data(data: ExportRequest):
    return ExportService.export(data)


# =============================================================================
# AI Assistant Endpoints
# =============================================================================


@router.post("/ai/generate")
def ai_generate(data: AiGenerateRequest):
    return AiAssistantService.generate(data)


# =============================================================================
# dbt Studio Endpoints
# =============================================================================


@router.get("/dbt/projects")
def dbt_list_projects():
    """List all dbt projects."""
    return DbtStudioService.list_projects().model_dump()


@router.get("/dbt/projects/{project_id}")
def dbt_get_project(project_id: str):
    """Get a dbt project by ID."""
    return DbtStudioService.get_project(project_id).model_dump()


@router.post("/dbt/projects")
def dbt_create_project(data: DbtProjectCreate):
    """Create a new dbt project."""
    return DbtStudioService.create_project(data).model_dump()


@router.delete("/dbt/projects/{project_id}")
def dbt_delete_project(project_id: str):
    """Delete a dbt project."""
    return DbtStudioService.delete_project(project_id)


@router.get("/dbt/projects/{project_id}/models")
def dbt_list_models(project_id: str, folder: Optional[str] = Query(None), search: Optional[str] = Query(None)):
    """List models in a dbt project, optionally filtered by folder/search."""
    return DbtStudioService.list_models(project_id, folder=folder, search=search).model_dump()


@router.get("/dbt/projects/{project_id}/models/{model_path:path}")
def dbt_get_model(project_id: str, model_path: str):
    """Get a single model by path."""
    return DbtStudioService.get_model(project_id, model_path).model_dump()


@router.post("/dbt/projects/{project_id}/models")
def dbt_create_model(project_id: str, body: dict):
    """Create a new model in a project."""
    model_path = body.get('model_path', '')
    sql = body.get('sql', '')
    description = body.get('description', '')
    return DbtStudioService.create_model(project_id, model_path, sql, description).model_dump()


@router.put("/dbt/projects/{project_id}/models")
def dbt_save_model(project_id: str, data: DbtModelSaveRequest):
    """Save/update a model's SQL and metadata."""
    data.project_id = project_id
    return DbtStudioService.save_model(data).model_dump()


@router.delete("/dbt/projects/{project_id}/models/{model_path:path}")
def dbt_delete_model(project_id: str, model_path: str):
    """Delete a model."""
    return DbtStudioService.delete_model(project_id, model_path)


@router.get("/dbt/projects/{project_id}/dag")
def dbt_get_dag(project_id: str):
    """Get the dependency DAG for a project."""
    return DbtStudioService.get_dag(project_id).model_dump()


@router.post("/dbt/compile")
def dbt_compile(data: DbtCompileRequest):
    """Compile a model's Jinja SQL into executable SQL."""
    return DbtStudioService.compile(data).model_dump()


@router.post("/dbt/run")
def dbt_run(data: DbtRunRequest):
    """Run dbt models (compile + execute)."""
    return DbtStudioService.run(data).model_dump()


@router.post("/dbt/test")
def dbt_test(data: DbtTestRequest):
    """Run dbt data tests."""
    return DbtStudioService.run_tests(data).model_dump()


@router.get("/dbt/projects/{project_id}/history")
def dbt_run_history(project_id: str, limit: int = Query(20, ge=1, le=100)):
    """Get run history for a project."""
    return [h.model_dump() for h in DbtStudioService.get_run_history(project_id, limit)]


@router.get("/dbt/projects/{project_id}/stats")
def dbt_project_stats(project_id: str):
    """Get project statistics (model counts, folder breakdown)."""
    return DbtStudioService.get_stats(project_id).model_dump()


# --- dbt Source Freshness ---

@router.post("/dbt/freshness")
def dbt_check_freshness(project_id: str = Query(...), source_name: Optional[str] = Query(None)):
    """Check freshness of dbt source tables."""
    return DbtFreshnessService.check_freshness(project_id, source_name=source_name)


# --- dbt Column Lineage ---

@router.get("/dbt/projects/{project_id}/lineage/{model_path:path}")
def dbt_column_lineage(project_id: str, model_path: str):
    """Get column-level lineage for a dbt model."""
    return DbtColumnLineageService.get_lineage(project_id, model_path)


# --- dbt Documentation ---

@router.get("/dbt/projects/{project_id}/docs")
def dbt_generate_docs(
    project_id: str,
    output_format: str = Query('markdown'),
    include_tests: bool = Query(True),
    include_lineage: bool = Query(True),
):
    """Generate documentation for a dbt project."""
    return DbtDocService.generate(
        project_id, output_format=output_format,
        include_tests=include_tests, include_lineage=include_lineage,
    )


# =============================================================================
# ETL Pipeline Endpoints
# =============================================================================


@router.get("/pipelines/dbt/projects")
def pipeline_dbt_projects():
    """List dbt projects available for pipeline node configuration."""
    return DbtStudioService.list_projects().model_dump()


@router.get("/pipelines/dbt/projects/{project_id}/models")
def pipeline_dbt_models(project_id: str, folder: Optional[str] = Query(None)):
    """List dbt models in a project for pipeline node configuration."""
    return DbtStudioService.list_models(project_id, folder=folder).model_dump()


@router.get("/pipelines/connectors")
def pipeline_list_connectors():
    """List available connectors (database, file, API, cloud, dbt)."""
    return PipelineService.list_connectors().model_dump()


@router.get("/pipelines")
def pipeline_list():
    """List all ETL pipelines."""
    return PipelineService.list_pipelines().model_dump()


@router.get("/pipelines/stats")
def pipeline_stats():
    """Get pipeline statistics (total, success rate, rows processed)."""
    return PipelineService.get_stats().model_dump()


@router.get("/pipelines/{pipeline_id}")
def pipeline_get(pipeline_id: str):
    """Get a pipeline by ID."""
    return PipelineService.get_pipeline(pipeline_id).model_dump()


@router.post("/pipelines")
def pipeline_create(data: PipelineCreate):
    """Create a new ETL pipeline."""
    return PipelineService.create_pipeline(data).model_dump()


@router.delete("/pipelines/{pipeline_id}")
def pipeline_delete(pipeline_id: str):
    """Delete a pipeline."""
    return PipelineService.delete_pipeline(pipeline_id)


@router.get("/pipelines/{pipeline_id}/graph")
def pipeline_graph(pipeline_id: str):
    """Get the full pipeline graph (nodes + edges)."""
    return PipelineService.get_graph(pipeline_id).model_dump()


@router.get("/pipelines/{pipeline_id}/nodes")
def pipeline_list_nodes(pipeline_id: str):
    """List nodes in a pipeline."""
    return [n.model_dump() for n in PipelineService.list_nodes(pipeline_id)]


@router.post("/pipelines/{pipeline_id}/nodes")
def pipeline_add_node(pipeline_id: str, data: PipelineNodeCreate):
    """Add a node to a pipeline."""
    return PipelineService.add_node(pipeline_id, data).model_dump()


@router.put("/pipelines/{pipeline_id}/nodes/{node_id}")
def pipeline_update_node(pipeline_id: str, node_id: str, data: PipelineNodeUpdate):
    """Update a pipeline node."""
    return PipelineService.update_node(pipeline_id, node_id, data).model_dump()


@router.delete("/pipelines/{pipeline_id}/nodes/{node_id}")
def pipeline_delete_node(pipeline_id: str, node_id: str):
    """Delete a pipeline node."""
    return PipelineService.delete_node(pipeline_id, node_id)


@router.get("/pipelines/{pipeline_id}/edges")
def pipeline_list_edges(pipeline_id: str):
    """List edges in a pipeline."""
    return [e.model_dump() for e in PipelineService.list_edges(pipeline_id)]


@router.post("/pipelines/{pipeline_id}/edges")
def pipeline_add_edge(pipeline_id: str, data: PipelineEdgeCreate):
    """Add an edge (connection) between two nodes."""
    return PipelineService.add_edge(pipeline_id, data).model_dump()


@router.delete("/pipelines/{pipeline_id}/edges/{edge_id}")
def pipeline_delete_edge(pipeline_id: str, edge_id: str):
    """Delete a pipeline edge."""
    return PipelineService.delete_edge(pipeline_id, edge_id)


@router.post("/pipelines/run")
def pipeline_run(data: PipelineRunRequest):
    """Execute a pipeline."""
    return PipelineService.run_pipeline(data).model_dump()


@router.get("/pipelines/{pipeline_id}/history")
def pipeline_run_history(pipeline_id: str, limit: int = Query(20, ge=1, le=100)):
    """Get run history for a pipeline."""
    return [h.model_dump() for h in PipelineService.get_run_history(pipeline_id, limit)]
