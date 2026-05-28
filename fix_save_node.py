"""Fix save_node_definition to return dict instead of bool."""

content = open(
    r"C:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Python Libs\common_lib\src\common_lib\modules\orchestration\context\memory\services.py",
    "r",
).read()

old = """    def save_node_definition(
        self, entity_id: str = None, definition: Dict = None, **kwargs
    ) -> bool:
        try:
            with self._db_session() as session:
                from common_lib.modules.core_infrastructure.tool.models import (
                    NodeDefinitionRecord,
                )

                entity_id = (
                    entity_id or kwargs.get("node_id") or (definition or {}).get("id")
                )
                record = session.get(
                    NodeDefinitionRecord, entity_id
                ) or NodeDefinitionRecord(id=entity_id)
                record.name = (definition or {}).get("name", entity_id)
                record.definition = definition or {}
                for key, value in kwargs.items():
                    if hasattr(record, key):
                        setattr(record, key, value)
                session.add(record)
                session.commit()
                return True
        except Exception as e:
            logger.error(f"save_node_definition: {e}")
        return False"""

new = """    def save_node_definition(
        self, entity_id: str = None, definition: Dict = None, **kwargs
    ) -> Optional[Dict]:
        try:
            with self._db_session() as session:
                from common_lib.modules.core_infrastructure.tool.models import (
                    NodeDefinitionRecord,
                )

                entity_id = (
                    entity_id or kwargs.get("node_id") or (definition or {}).get("id")
                )
                record = session.get(
                    NodeDefinitionRecord, entity_id
                ) or NodeDefinitionRecord(id=entity_id)
                record.name = (definition or {}).get("name", entity_id)
                record.definition = definition or {}
                for key, value in kwargs.items():
                    if hasattr(record, key):
                        setattr(record, key, value)
                session.add(record)
                session.commit()
                session.refresh(record)
                return record.model_dump()
        except Exception as e:
            logger.error(f"save_node_definition: {e}")
        return None"""

if old in content:
    content = content.replace(old, new)
    open(
        r"C:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Python Libs\common_lib\src\common_lib\modules\orchestration\context\memory\services.py",
        "w",
    ).write(content)
    print("Replacement done successfully")
else:
    print("Old string not found - checking actual content...")
    # Debug: show the actual method
    import re

    m = re.search(r"def save_node_definition.*?(?=def |\Z)", content, re.DOTALL)
    if m:
        print(f"Actual method:\n{m.group()[:600]}")
    else:
        print("save_node_definition not found in file")
