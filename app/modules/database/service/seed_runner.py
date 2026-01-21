from typing import List, Type
from sqlmodel import Session
from app.modules.database.service.connection import get_session
from app.modules.database.service.seeder_base import BaseSeeder

# Registry of seeders
_seeders: dict[str, Type[BaseSeeder]] = {}

def register_seeder(seeder_cls: Type[BaseSeeder]):
    if not seeder_cls.key:
        raise ValueError(f"Seeder {seeder_cls.__name__} must have a 'key' attribute")
    _seeders[seeder_cls.key] = seeder_cls

def _get_execution_order(targets: List[str] = None) -> List[str]:
    """
    Returns a list of seeder keys in topological order (dependencies first).
    If targets is provided, only includes those targets and their dependencies.
    """
    # 1. Determine the subgraph to run
    to_visit = set(targets) if targets else set(_seeders.keys())
    visited = set()
    order = []

    def visit(key):
        if key in visited:
            return
        
        seeder_cls = _seeders.get(key)
        if not seeder_cls:
            if targets and key in targets:
                raise ValueError(f"Unknown seeder module: {key}")
            return # Dependency might not be registered or optional, skip

        # Visit dependencies first
        for dep in seeder_cls.dependencies:
            visit(dep)
        
        visited.add(key)
        order.append(key)

    # If targets are specified, we only visit those specific nodes (and their deps via recursion).
    # If no targets, we visit all registered seeders.
    roots = list(to_visit)
    for key in roots:
        visit(key)
        
    return order

def run_seeds(target_modules: List[str] = None):
    print("Starting database seeding...")
    session_gen = get_session()
    session = next(session_gen)
    
    try:
        execution_order = _get_execution_order(target_modules)
        print(f"Execution Order: {' -> '.join(execution_order)}")
        
        for key in execution_order:
            SeederClass = _seeders[key]
            seeder = SeederClass()
            print(f"[{key}] Running seeder: {SeederClass.__name__}")
            seeder.seed(session)
        
        session.commit()
        print("Database seeding completed successfully.")
    except Exception as e:
        session.rollback()
        print(f"Seeding failed: {e}")
        raise
    finally:
        session.close()
