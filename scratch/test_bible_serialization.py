import sys
from pathlib import Path

# Add paths to sys.path to locate common_lib
project_root = Path(__file__).resolve().parents[2]
common_lib_src = project_root / "Backend Monorepo" / "Python Libs" / "common_lib" / "src"
sys.path.insert(0, str(common_lib_src))

from common_lib.modules.external_platform.writing_studio.bible import SceneEntry, StoryBeat
from common_lib.modules.external_platform.writing_studio.service import get_bible_service

def test_serialization():
    project_id = "test_project_serialization"
    svc = get_bible_service()
    
    # 1. Clean up any previous test bible
    svc.delete_bible(project_id)
    
    # 2. Create a SceneEntry with custom fields
    scene = SceneEntry(
        id="test_scene_1",
        title="The Forest Encounter",
        chapter=2,
        scene_number=1,
        location="Whispering Woods",
        time_of_day="Dusk",
        prose="The trees loomed high, their branches reaching out like skeletal fingers.",
        beats=[
            StoryBeat(id="beat_1", beat_number=1, summary="Enter the forest"),
            StoryBeat(id="beat_2", beat_number=2, summary="Hear a strange sound")
        ],
        status="drafted",
        word_count_goal=500,
        notes="A suspenseful opening scene"
    )
    
    # 3. Add to the database
    print("Saving SceneEntry to DB...")
    svc.add_entry(project_id, scene)
    
    # 4. Clear service in-memory cache to force DB load
    svc._bibles.clear()
    
    # 5. Fetch it back
    print("Reading SceneEntry from DB...")
    retrieved = svc.get_entry(project_id, "test_scene_1")
    
    # 6. Verify assertions
    assert retrieved is not None, "Failed to retrieve entry"
    assert isinstance(retrieved, SceneEntry), f"Expected SceneEntry, got {type(retrieved)}"
    assert retrieved.chapter == 2, f"Expected chapter 2, got {retrieved.chapter}"
    assert retrieved.scene_number == 1, f"Expected scene_number 1, got {retrieved.scene_number}"
    assert retrieved.location == "Whispering Woods", f"Expected Whispering Woods, got {retrieved.location}"
    assert retrieved.time_of_day == "Dusk", f"Expected Dusk, got {retrieved.time_of_day}"
    assert retrieved.prose == "The trees loomed high, their branches reaching out like skeletal fingers.", "Prose mismatched"
    assert len(retrieved.beats) == 2, f"Expected 2 beats, got {len(retrieved.beats)}"
    assert retrieved.beats[0].summary == "Enter the forest", f"Expected beat summary, got {retrieved.beats[0].summary}"
    assert retrieved.status == "drafted", f"Expected status drafted, got {retrieved.status}"
    
    print("[SUCCESS] All serialization tests passed successfully!")

if __name__ == "__main__":
    test_serialization()
