from PIL import Image
import sys
import os

path = sys.argv[1]
if os.path.exists(path):
    with Image.open(path) as img:
        print(f"Metadata for {os.path.basename(path)}:")
        for key, value in img.info.items():
            print(f"--- {key} ---")
            print(value)
            print("-" * 20)
else:
    print(f"File not found: {path}")
