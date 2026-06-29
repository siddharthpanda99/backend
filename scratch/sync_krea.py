import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Python Libs", "common_lib", "src")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common_lib.modules.ai_models.container import AIModelsContainer

container = AIModelsContainer()
container.seed_defaults()
print("Done seeding defaults from YAML")
