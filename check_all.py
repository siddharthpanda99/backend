import sys
import os
import common_lib
import common_lib.modules.image_processing.core.legacy as legacy
import common_lib.modules.image_processing.nodes.image.face_swapper as face_swapper

print(f"PYTHONPATH: {sys.path}")
print(f"common_lib: {common_lib.__file__}")
print(f"legacy: {legacy.__file__}")
print(f"face_swapper: {face_swapper.__file__}")

with open(legacy.__file__, 'r') as f:
    content = f.read()
    print(f"Legacy file contains '!!! [FACE ANALYSIS DEBUG]': {'!!! [FACE ANALYSIS DEBUG]' in content}")

with open(face_swapper.__file__, 'r') as f:
    content = f.read()
    print(f"Face swapper file contains '!!! [CNET EXTRACTOR DEBUG]': {'!!! [CNET EXTRACTOR DEBUG]' in content}")
