import sys
sys.path.insert(0, r'c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Python Libs\common_lib\src')
from common_lib.modules.data_storage.database.connection import engine, init_db
init_db()
from common_lib.modules.rbac.service import seed_roles
from sqlmodel import Session
try:
    with Session(engine) as session:
        seed_roles(session)
except Exception as e:
    import traceback
    traceback.print_exc()
