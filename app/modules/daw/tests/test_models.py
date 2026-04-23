# DAW Model Tests
import pytest
from uuid import uuid4
from datetime import datetime

from common_lib.modules.daw.models import (
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


class TestStepsConversion:
    """Test step array conversion functions"""

    def test_steps_to_string_standard(self):
        """Test standard steps"""
        steps = [1, 0, 0, 0, 1, 0, 0, 0]
        result = steps_to_string(steps)
        assert result == "[1, 0, 0, 0, 1, 0, 0, 0]"

    def test_steps_to_string_kick_pattern(self):
        """Test kick pattern"""
        steps = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
        result = steps_to_string(steps)
        assert result == "[1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]"

    def test_steps_from_string(self):
        """Test parsing steps from string"""
        steps_str = "[1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0]"
        result = steps_from_string(steps_str)
        assert result == [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]

    def test_steps_roundtrip_full(self):
        """Test roundtrip conversion"""
        original = [1, 1, 0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 0]
        json_str = steps_to_string(original)
        restored = steps_from_string(json_str)
        assert restored == original

    def test_empty_steps(self):
        """Test empty steps"""
        steps_str = "[]"
        result = steps_from_string(steps_str)
        assert result == []

    def test_single_step(self):
        """Test single step"""
        steps = [1]
        result = steps_to_string(steps)
        restored = steps_from_string(result)
        assert restored == [1]


class TestTimeSignatureConversion:
    """Test time signature conversion"""

    def test_time_signature_to_4_4(self):
        """Test 4/4 time signature"""
        result = time_signature_to_string((4, 4))
        assert result == "[4, 4]"

    def test_time_signature_to_3_4(self):
        """Test 3/4 time signature"""
        result = time_signature_to_string((3, 4))
        assert result == "[3, 4]"

    def test_time_signature_from_4_4(self):
        """Test parsing 4/4"""
        result = time_signature_from_string("[4,4]")
        assert result == (4, 4)

    def test_time_signature_roundtrip(self):
        """Test roundtrip"""
        original = (6, 8)
        json_str = time_signature_to_string(original)
        restored = time_signature_from_string(json_str)
        assert restored == original


class TestEnums:
    """Test enum values"""

    def test_project_status_values(self):
        """Test ProjectStatus enum"""
        assert ProjectStatus.DRAFT.value == "draft"
        assert ProjectStatus.PUBLISHED.value == "published"
        assert ProjectStatus.ARCHIVED.value == "archived"

    def test_channel_type_values(self):
        """Test ChannelType enum"""
        assert ChannelType.DRUM.value == "drum"
        assert ChannelType.SYNTH.value == "synth"
        assert ChannelType.BASS.value == "bass"
        assert ChannelType.PAD.value == "pad"
        assert ChannelType.AUDIO.value == "audio"
        assert ChannelType.MIDI.value == "midi"


class TestModelFields:
    """Test model field constraints"""

    def test_project_required_fields(self):
        """Test Project model required fields"""
        project = Project(
            name="Test",
            user_id=uuid4(),
            bpm=128,
            time_signature="[4,4]",
            master_volume=0.8,
            status=ProjectStatus.DRAFT,
        )
        assert project.name == "Test"
        assert project.bpm == 128
        assert project.status == ProjectStatus.DRAFT

    def test_channel_required_fields(self):
        """Test Channel model required fields"""
        channel = Channel(
            name="Kick",
            type="drum",
            color="#ef4444",
            project_id=uuid4(),
            order_index=0,
            steps="[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]",
        )
        assert channel.name == "Kick"
        assert channel.type == "drum"
        assert channel.order_index == 0

    def test_pattern_required_fields(self):
        """Test Pattern model required fields"""
        pattern = Pattern(name="Pattern 1", length=16, project_id=uuid4())
        assert pattern.name == "Pattern 1"
        assert pattern.length == 16

    def test_note_required_fields(self):
        """Test Note model required fields"""
        note = Note(
            pitch=60,
            start=4,
            duration=2,
            velocity=100,
            pattern_id=uuid4(),
            channel_id=uuid4(),
        )
        assert note.pitch == 60
        assert note.start == 4
        assert note.duration == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
