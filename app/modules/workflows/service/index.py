from common_lib.modules.orchestration.workflow.execution.executor import GraphExecutor
from common_lib.modules.orchestration.workflow.execution.core import ExecutionEngine
from common_lib.modules.orchestration.workflow.execution.context import ExecutionContext
from common_lib.modules.orchestration.workflow.execution.primitives import Graph, State, Transition
from common_lib.modules.orchestration.workflow.observability import EventTracer

class WorkflowService:
    def get_all(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        workflows = common_memory.list_workflow_definitions()
        return workflows[skip : skip + limit]

    def get_by_id(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        return common_memory.get_workflow_definition(workflow_id)

    def create(self, workflow_in: WorkflowCreate) -> Dict[str, Any]:
        data = workflow_in.model_dump()
        workflow_id = data.get("id") or data.get("name")
        if not workflow_id:
            raise HTTPException(status_code=400, detail="Workflow ID or Name is required")
            
        common_memory.save_workflow_definition(
            name=workflow_id,
            definition=data.get("definition", {}),
            version=data.get("version", "1.0.0")
        )
        sync_entity_to_fs("workflow", workflow_id)
        return self.get_by_id(workflow_id)

    def update(self, workflow_id: str, workflow_in: WorkflowUpdate) -> Dict[str, Any]:
        existing = self.get_by_id(workflow_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Workflow not found")
            
        update_data = workflow_in.model_dump(exclude_unset=True)
        definition = update_data.get("definition", existing.get("definition", {}))
        version = update_data.get("version", existing.get("version", "1.0.0"))
        
        common_memory.save_workflow_definition(
            name=workflow_id,
            definition=definition,
            version=version
        )
        sync_entity_to_fs("workflow", workflow_id)
        return self.get_by_id(workflow_id)

    def delete(self, workflow_id: str) -> bool:
        if not self.get_by_id(workflow_id):
            raise HTTPException(status_code=404, detail="Workflow not found")
        common_memory.delete_workflow_definition(workflow_id)
        return True

    def run_graph(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], inputs: Dict[str, Any] = {}) -> Dict[str, Any]:
        """
        Converts a UI Node/Edge JSON graph into a backend State Graph and executes it.
        """
        # 1. Build Backend Graph
        graph_id = f"dynamic_{uuid.uuid4().hex[:8]}"
        graph = Graph(id=graph_id, name="UI Transient Workflow", version="1.0.0")
        
        # Mapping from UI Node ID to Backend State ID
        state_map = {}
        
        # Detect start node (usually one with no incoming edges or marked as start)
        incoming_counts = {n['id']: 0 for n in nodes}
        for e in edges:
            incoming_counts[e['to']] = incoming_counts.get(e['to'], 0) + 1
        
        start_node_id = next((nid for nid, count in incoming_counts.items() if count == 0), nodes[0]['id'] if nodes else None)
        graph.start_state_id = start_node_id
        
        for n in nodes:
            # Create a State for each node
            state = State(
                id=n['id'],
                tool_id=n.get('toolId') or n.get('type'),
                static_inputs=n.get('properties', {}),
                description=n.get('title', n['id'])
            )
            graph.add_state(state)
            state_map[n['id']] = state

        # Create transitions for each edge
        for e in edges:
            parent_state = state_map.get(e['from'])
            if parent_state:
                transition = Transition(
                    to_state_id=e['to'],
                    description=f"Link from {e['from']} to {e['to']}"
                )
                parent_state.transitions.append(transition)

        # 2. Execute
        engine = ExecutionEngine()
        tracer = EventTracer()
        executor = GraphExecutor(engine, tracer)
        context = ExecutionContext(agent_id="vision_demo_user", role="tester")
        
        results = executor.execute(graph, inputs, context)
        
        # 3. Collect Trace
        return {
            "status": "success",
            "results": results,
            "trace": tracer.get_events()
        }

workflow_service = WorkflowService()
