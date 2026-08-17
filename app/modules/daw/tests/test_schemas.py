# DAW Schema Tests
import pytest
from uuid import uuid4

from common_lib.modules.audio_processing.daw.schemas import (
    DAWProjectCreate,
    DAWProjectUpdate,
    DAWProjectResponse,
    ChannelCreate,
    ChannelUpdate,
    ChannelResponse,
    PatternCreate,
    PatternUpdate,
    PatternResponse,
    NoteCreate,
    NoteUpdate,
    NoteResponse,
    ClipCreate,
    ClipUpdate,
    ClipResponse,
    DAWExport,
    ProjectStatus,
    ChannelType,
)


class TestProjectSchemas:
    """Test project schemas"""

    def test_daw_project_create_defaults(self):
        """Test default values"""
        project = DAWProjectCreate(name="Test")
        assert project.name == "Test"
        assert project.bpm == 128
        assert project.master_volume == 0.8
        assert project.time_signature == (4, 4)

    def test_daw_project_create_custom(self):
        """Test custom values"""
        project = DAWProjectCreate(
            name="Custom", bpm=140, master_volume=0.9, time_signature=(3, 4)
        )
        assert project.name == "Custom"
        assert project.bpm == 140
        assert project.master_volume == 0.9
        assert project.time_signature == (3, 4)

    def test_daw_project_update(self):
        """Test update schema"""
        update = DAWProjectUpdate(name="New Name", bpm=120)
        assert update.name == "New Name"
        assert update.bpm == 120

    def test_daw_project_update_all_optional(self):
        """Test all fields optional"""
        update = DAWProjectUpdate()
        assert update.name is None
        assert update.bpm is None


class TestChannelSchemas:
    """Test channel schemas"""

    def test_channel_create_defaults(self):
        """Test default values"""
        channel = ChannelCreate(name="Kick", type=ChannelType.DRUM)
        assert channel.name == "Kick"
        assert channel.type == ChannelType.DRUM
        assert channel.color == "#3b82f6"
        assert channel.volume == 0.8
        assert channel.pan == 0
        assert channel.mute is False
        assert channel.solo is False

    def test_channel_create_steps(self):
        """Test steps initialization"""
        channel = ChannelCreate(name="Kick", type=ChannelType.DRUM)
        assert len(channel.steps) == 16
        assert channel.steps == [0] * 16

    def test_channel_update(self):
        """Test channel update"""
        update = ChannelUpdate(name="New Name", mute=True, volume=0.5)
        assert update.name == "New Name"
        assert update.mute is True
        assert update.volume == 0.5


class TestPatternSchemas:
    """Test pattern schemas"""

    def test_pattern_create_defaults(self):
        """Test default values"""
        pattern = PatternCreate(name="Pattern 1")
        assert pattern.name == "Pattern 1"
        assert pattern.length == 16
        assert pattern.notes == []

    def test_pattern_create_custom(self):
        """Test custom length"""
        pattern = PatternCreate(name="Long Pattern", length=32)
        assert pattern.length == 32

    def test_pattern_update(self):
        """Test pattern update"""
        update = PatternUpdate(name="New Name", length=8)
        assert update.name == "New Name"
        assert update.length == 8


class TestNoteSchemas:
    """Test note schemas"""

    def test_note_create_required(self):
        """Test required fields"""
        note = NoteCreate(pitch=60, start=4, duration=2, channel_id=uuid4())
        assert note.pitch == 60
        assert note.start == 4
        assert note.duration == 2
        assert note.velocity == 100

    def test_note_create_bounds(self):
        """Test note value bounds"""
        # Valid values
        note = NoteCreate(pitch=0, start=0, duration=1, channel_id=uuid4())
        assert note.pitch == 0

        note = NoteCreate(pitch=127, start=0, duration=1, channel_id=uuid4())
        assert note.pitch == 127

    def test_note_update(self):
        """Test note update"""
        update = NoteUpdate(pitch=72, velocity=120)
        assert update.pitch == 72
        assert update.velocity == 120


class TestClipSchemas:
    """Test clip schemas"""

    def test_clip_create_required(self):
        """Test required fields"""
        clip = ClipCreate(pattern_id=uuid4(), channel_id=uuid4(), start=0, length=16)
        assert clip.start == 0
        assert clip.length == 16

    def test_clip_update(self):
        """Test clip update"""
        update = ClipUpdate(start=8, length=8)
        assert update.start == 8
        assert update.length == 8


class TestDAWExport:
    """Test export schema"""

    def test_export_schema(self):
        """Test export format"""
        export = DAWExport(project={"name": "Test"}, channels=[], patterns=[], clips=[])
        assert export.version == "1.0.0"
        assert export.project == {"name": "Test"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
