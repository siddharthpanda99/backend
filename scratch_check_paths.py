import os
from pathlib import Path

def test_paths():
    print(f"Current Directory: {os.getcwd()}")
    print(f"Abspath 'resources': {os.path.abspath('resources')}")
    
    # Try to find the real resources
    current = Path(os.getcwd())
    for parent in [current] + list(current.parents):
        if (parent / "resources").exists():
            print(f"Found resources at: {parent / 'resources'}")
            break

if __name__ == "__main__":
    test_paths()
