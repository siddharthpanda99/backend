# DAW Tests - Comprehensive test suite for DAW module
import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime
from typing import Generator

# Test imports
from app.modules.daw.models import (
    Project,
    Channel,
    Pattern,
    Note,
    Clip,
    ProjectStatus,
    ChannelType,
    steps_from_string,
    steps_to_string,
    time_signature_from_string,
    time_signature_to_string,
)
from app.modules.daw.schemas import (
    DAWProjectCreate,
    DAWProjectUpdate,
    ChannelCreate,
    ChannelUpdate,
    PatternCreate,
    PatternUpdate,
    NoteCreate,
    NoteUpdate,
    ClipCreate,
    ClipUpdate,
    ProjectStatus as SchemaProjectStatus,
    ChannelType as SchemaChannelType,
)


# =============================================================================
# Model Tests
# =============================================================================


class TestDAWModels:
    """Tests for DAW data models"""

    def test_steps_to_string(self):
        """Test converting steps list to JSON string"""
        steps = [1, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
        result = steps_to_string(steps)
        assert result == "[1,0,1,0,1,0,0,0,1,0,0,0,1,0,0,0]"

    def test_steps_from_string(self):
        """Test converting JSON string to steps list"""
        steps_str = "[1,0,1,0,1,0,0,0,1,0,0,0,1,0,0,0]"
        result = steps_from_string(steps_str)
        assert result == [1, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]

    def test_steps_from_string_empty(self):
        """Test empty steps string"""
        steps_str = "[]"
        result = steps_from_string(steps_str)
        assert result == []

    def test_steps_roundtrip(self):
        """Test steps conversion roundtrip"""
        original = [1, 0, 1, 1, 0, 0, 1, 1]
        converted = steps_to_string(original)
        restored = steps_from_string(converted)
        assert restored == original

    def test_time_signature_to_string(self):
        """Test time signature to string"""
        ts = (4, 4)
        result = time_signature_to_string(ts)
        assert result == "[4,4]"

    def test_time_signature_from_string(self):
        """Test time signature from string"""
        ts_str = "[4,4]"
        result = time_signature_from_string(ts_str)
        assert result == (4, 4)

    def test_project_status_values(self):
        """Test ProjectStatus enum values"""
        assert ProjectStatus.DRAFT.value == "draft"
        assert ProjectStatus.PUBLISHED.value == "published"
        assert ProjectStatus.ARCHIVED.value == "archived"

    def test_channel_type_values(self):
        """Test ChannelType enum values"""
        assert ChannelType.DRUM.value == "drum"
        assert ChannelType.SYNTH.value == "synth"
        assert ChannelType.BASS.value == "bass"
        assert ChannelType.PAD.value == "pad"
        assert ChannelType.AUDIO.value == "audio"
        assert ChannelType.MIDI.value == "midi"


# =============================================================================
# Schema Tests
# =============================================================================


class TestDAWSchemas:
    """Tests for Pydantic schemas"""

    def test_create_project_schema(self):
        """Test DAWProjectCreate schema"""
        project = DAWProjectCreate(name="Test Project", bpm=120)
        assert project.name == "Test Project"
        assert project.bpm == 120
        assert project.master_volume == 0.8

    def test_create_project_bpm_bounds(self):
        """Test BPM boundary values"""
        # Valid BPM
        project = DAWProjectCreate(name="Test", bpm=128)
        assert project.bpm == 128

        # Test with custom values
        project = DAWProjectCreate(name="Test", bpm=200)
        assert project.bpm == 200

    def test_update_project_schema(self):
        """Test DAWProjectUpdate schema"""
        update = DAWProjectUpdate(name="New Name", bpm=140)
        assert update.name == "New Name"
        assert update.bpm == 140

    def test_update_project_optional_fields(self):
        """Test optional fields"""
        update = DAWProjectUpdate()
        assert update.name is None
        assert update.bpm is None

    def test_create_channel_schema(self):
        """Test ChannelCreate schema"""
        channel = ChannelCreate(
            name="Kick", type=SchemaChannelType.DRUM, color="#ef4444", volume=0.8
        )
        assert channel.name == "Kick"
        assert channel.type == SchemaChannelType.DRUM
        assert channel.color == "#ef4444"
        assert channel.volume == 0.8

    def test_channel_update_schema(self):
        """Test ChannelUpdate schema"""
        update = ChannelUpdate(name="New Name", mute=True)
        assert update.name == "New Name"
        assert update.mute is True
        assert update.solo is None

    def test_pattern_create_schema(self):
        """Test PatternCreate schema"""
        pattern = PatternCreate(name="Pattern 1", length=16)
        assert pattern.name == "Pattern 1"
        assert pattern.length == 16

    def test_note_create_schema(self):
        """Test NoteCreate schema"""
        note = NoteCreate(
            pitch=60, start=4, duration=2, velocity=100, channel_id=uuid4()
        )
        assert note.pitch == 60
        assert note.start == 4
        assert note.duration == 2
        assert note.velocity == 100

    def test_note_update_schema(self):
        """Test NoteUpdate schema"""
        update = NoteUpdate(pitch=72, velocity=120)
        assert update.pitch == 72
        assert update.velocity == 120

    def test_clip_create_schema(self):
        """Test ClipCreate schema"""
        clip = ClipCreate(pattern_id=uuid4(), channel_id=uuid4(), start=0, length=16)
        assert clip.start == 0
        assert clip.length == 16


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.asyncio
class TestDAWService:
    """Integration tests for DAWService"""

    @pytest_asyncio.fixture
    async def service(self):
        """Fixture to get DAW service instance"""
        from app.modules.daw.service import daw_service

        return daw_service

    @pytest_asyncio.fixture
    async def test_user_id(self):
        """Fixture for test user ID"""
        return uuid4()

    async def test_create_project(self, service, test_user_id):
        """Test project creation"""
        data = DAWProjectCreate(name="Test Project")
        project = await service.create_project(test_user_id, data)

        assert project is not None
        assert project.name == "Test Project"
        assert project.user_id == test_user_id
        assert project.bpm == 128
        assert project.status == ProjectStatus.DRAFT

    async def test_get_project(self, service, test_user_id):
        """Test getting a project"""
        # Create first
        data = DAWProjectCreate(name="Get Test")
        created = await service.create_project(test_user_id, data)

        # Get it back
        retrieved = await service.get(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Get Test"

    async def test_get_user_projects(self, service, test_user_id):
        """Test listing user projects"""
        # Create multiple projects
        await service.create_project(test_user_id, DAWProjectCreate(name="Project 1"))
        await service.create_project(test_user_id, DAWProjectCreate(name="Project 2"))

        projects = await service.get_user_projects(test_user_id)
        assert len(projects) >= 2

    async def test_update_project(self, service, test_user_id):
        """Test project update"""
        created = await service.create_project(
            test_user_id, DAWProjectCreate(name="Original")
        )

        update = DAWProjectUpdate(name="Updated", bpm=140)
        updated = await service.update_project(created.id, update)

        assert updated.name == "Updated"
        assert updated.bpm == 140

    async def test_update_nonexistent_project(self, service):
        """Test updating nonexistent project raises error"""
        from app.modules.common.exceptions import NotFoundError

        update = DAWProjectUpdate(name="Test")
        with pytest.raises(NotFoundError):
            await service.update_project(uuid4(), update)

    async def test_create_channel(self, service, test_user_id):
        """Test channel creation"""
        project = await service.create_project(
            test_user_id, DAWProjectCreate(name="Channel Test")
        )

        channel_data = ChannelCreate(
            name="Test Channel",
            type=SchemaChannelType.SYNTH,
            color="#ff0000",
            steps=[1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
        )
        channel = await service.create_channel(project.id, channel_data)

        assert channel is not None
        assert channel.name == "Test Channel"
        assert channel.type == "synth"

        # Verify steps stored correctly
        stored_steps = steps_from_string(channel.steps)
        assert stored_steps == [1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0]

    async def test_update_channel(self, service, test_user_id):
        """Test channel update"""
        project = await service.create_project(
            test_user_id, DAWProjectCreate(name="Update Channel Test")
        )

        # Create channel
        channel = await service.create_channel(
            project.id, ChannelCreate(name="Original", type=SchemaChannelType.DRUM)
        )

        # Update
        update = ChannelUpdate(name="Updated", mute=True, volume=0.5)
        updated = await service.update_channel(channel.id, update)

        assert updated.name == "Updated"
        assert updated.mute is True
        assert updated.volume == 0.5

    async def test_toggle_channel_mute(self, service, test_user_id):
        """Test toggling channel mute"""
        project = await service.create_project(
            test_user_id, DAWProjectCreate(name="Mute Test")
        )
        channel = await service.create_channel(
            project.id, ChannelCreate(name="To Mute", type=SchemaChannelType.DRUM)
        )

        # Toggle mute
        update = ChannelUpdate(mute=True)
        updated = await service.update_channel(channel.id, update)
        assert updated.mute is True

        # Toggle off
        update_off = ChannelUpdate(mute=False)
        updated_off = await service.update_channel(channel.id, update_off)
        assert updated_off.mute is False

    async def test_delete_channel(self, service, test_user_id):
        """Test deleting a channel"""
        project = await service.create_project(
            test_user_id, DAWProjectCreate(name="Delete Test")
        )
        channel = await service.create_channel(
            project.id, ChannelCreate(name="To Delete", type=SchemaChannelType.DRUM)
        )

        await service.delete_channel(channel.id)

        # Verify deleted - get should return None
        # (We can't directly test this without get_channel method)

    async def test_create_pattern(self, service, test_user_id):
        """Test pattern creation"""
        project = await service.create_project(
            test_user_id, DAWProjectCreate(name="Pattern Test")
        )

        pattern = await service.create_pattern(
            project.id, PatternCreate(name="New Pattern", length=32)
        )

        assert pattern is not None
        assert pattern.name == "New Pattern"
        assert pattern.length == 32


# =============================================================================
# Fixtures for testing
# =============================================================================


@pytest.fixture
def sample_channel_steps() -> list[int]:
    """Sample 16-step pattern"""
    return [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


@pytest.fixture
def sample_daw_project_data() -> DAWProjectCreate:
    """Sample project creation data"""
    return DAWProjectCreate(
        name="Test Project",
        description="Test description",
        bpm=128,
        time_signature=(4, 4),
        master_volume=0.8,
    )


@pytest.fixture
def sample_channel_data() -> ChannelCreate:
    """Sample channel creation data"""
    return ChannelCreate(
        name="Kick",
        type=SchemaChannelType.DRUM,
        color="#ef4444",
        volume=0.8,
        pan=0,
        mute=False,
        solo=False,
        steps=[1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
    )


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
