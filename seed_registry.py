import sys
import os

# Add common_lib and app to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Python Libs", "common_lib", "src")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from common_lib.modules.ai_models.container import AIModelsContainer

def seed():
    print("Starting registry seed...")
    try:
        container = AIModelsContainer()
        container.seed_defaults()
        print("Successfully seeded registry.")
    except Exception as e:
        print(f"Error seeding registry: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    seed()
