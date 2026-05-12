import sys
import os

# Add common_lib and backend to path
repo_root = r"c:\Users\91797\Documents\Dev\JS\Monorepo"
common_lib_path = os.path.join(repo_root, "Backend Monorepo", "Python Libs", "common_lib", "src")
sys.path.insert(0, common_lib_path)

try:
    from common_lib.modules.image_processing.nodes import NODE_CLASS_MAPPINGS
    print("SUCCESS: common_lib.modules.image_processing.nodes imported successfully")
    print(f"Total nodes: {len(NODE_CLASS_MAPPINGS)}")
    
    # Check for specific nodes
    test_nodes = ["ReActorFaceSwap", "ADetailer", "KSampler"]
    for node in test_nodes:
        if node in NODE_CLASS_MAPPINGS:
            print(f"FOUND: {node}")
        else:
            print(f"MISSING: {node}")
            
except Exception as e:
    print(f"FAILURE: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
