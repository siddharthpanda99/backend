import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

# Mocking the environment
class VisionGalleryItem(BaseModel):
    filename: str
    url: str
    metadata: Optional[Dict[str, Any]] = None
    folder: Optional[str] = None

class VisionGalleryFolder(BaseModel):
    name: str
    images: list[VisionGalleryItem]

class VisionGalleryResponse(BaseModel):
    folders: list[VisionGalleryFolder]

GENERATED_CONTENT = Path(r"C:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Backend\generated_content")

def test_list_gallery():
    if not GENERATED_CONTENT.exists():
        print("GENERATED_CONTENT does not exist")
        return

    folders_dict: Dict[str, List[VisionGalleryItem]] = {}

    def process_dir(directory: Path, folder_name: str):
        if folder_name not in folders_dict:
            folders_dict[folder_name] = []
        
        for f in directory.iterdir():
            if f.is_file() and f.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
                metadata = {}
                stats = f.stat()
                metadata["timestamp"] = stats.st_mtime
                metadata["size"] = stats.st_size

                folders_dict[folder_name].append(
                    VisionGalleryItem(
                        filename=f.name,
                        url=f"/generated/{folder_name}/{f.name}" if folder_name != "root" else f"/generated/{f.name}",
                        metadata=metadata,
                        folder=folder_name
                    )
                )

    # Process root directory
    process_dir(GENERATED_CONTENT, "root")

    # Process subdirectories
    for d in GENERATED_CONTENT.iterdir():
        if d.is_dir():
            process_dir(d, d.name)

    # Convert to Response schema
    gallery_folders = []
    for name, images in folders_dict.items():
        images.sort(key=lambda x: (x.metadata or {}).get("timestamp", 0), reverse=True)
        if images: 
            gallery_folders.append(VisionGalleryFolder(name=name, images=images))

    gallery_folders.sort(key=lambda x: (0 if x.name == "root" else 1, x.name))
    
    response = VisionGalleryResponse(folders=gallery_folders)
    print(response.model_dump_json(indent=2))

if __name__ == "__main__":
    test_list_gallery()
