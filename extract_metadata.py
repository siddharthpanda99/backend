from PIL import Image
import os

img_path = r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Backend\generated_content\2026-03-20\dreamshaper_8_768x1536_upscaledBy1.5_20032026_8dd1b8.png"

if os.path.exists(img_path):
    with Image.open(img_path) as img:
        print(f"Metadata for {os.path.basename(img_path)}:")
        for key, value in img.info.items():
            print(f"--- {key} ---")
            print(value)
            print("-" * 20)
else:
    print(f"File not found: {img_path}")
