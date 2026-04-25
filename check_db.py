from common_lib.modules.data_storage.database.connection import engine
from sqlmodel import Session, select
from common_lib.modules.workflows.standard.models.observability import WorkflowExecution

try:
    session = Session(engine)
    result = session.exec(select(WorkflowExecution)).all()
    print(f"COUNT:{len(result)}")
    for r in result:
        print(f"TRACE:{r.trace_id} STATUS:{r.status}")
except Exception as e:
    print(f"ERROR:{e}")
