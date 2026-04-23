# Audio Tests
import pytest
import os


class TestAudioService:
    """Tests for AudioService"""

    def test_service_instance_exists(self):
        from common_lib.modules.audio.service import audio_service

        assert audio_service is not None

    def test_service_has_generate_tts_method(self):
        from common_lib.modules.audio.service import audio_service

        assert hasattr(audio_service, "generate_tts")
        assert callable(audio_service.generate_tts)

    def test_service_has_transcribe_method(self):
        from common_lib.modules.audio.service import audio_service

        assert hasattr(audio_service, "transcribe")
        assert callable(audio_service.transcribe)

    def test_service_has_edit_audio_method(self):
        from common_lib.modules.audio.service import audio_service

        assert hasattr(audio_service, "edit_audio")
        assert callable(audio_service.edit_audio)

    def test_service_has_get_history_method(self):
        from common_lib.modules.audio.service import audio_service

        assert hasattr(audio_service, "get_history")
        assert callable(audio_service.get_history)

    def test_audio_service_is_async(self):
        from common_lib.modules.audio.service import AudioService
        import inspect

        assert inspect.iscoroutinefunction(AudioService.generate_tts)
        assert inspect.iscoroutinefunction(AudioService.transcribe)
        assert inspect.iscoroutinefunction(AudioService.edit_audio)
        assert inspect.iscoroutinefunction(AudioService.get_history)


class TestAudioServiceSchemas:
    """Tests for Audio schemas"""

    def test_tts_request_schema_imports(self):
        from common_lib.modules.audio.schemas import TTSRequest

        assert TTSRequest is not None

    def test_tts_response_schema_imports(self):
        from common_lib.modules.audio.schemas import TTSResponse

        assert TTSResponse is not None

    def test_transcription_request_schema_imports(self):
        from common_lib.modules.audio.schemas import TranscriptionRequest

        assert TranscriptionRequest is not None

    def test_transcription_response_schema_imports(self):
        from common_lib.modules.audio.schemas import TranscriptionResponse

        assert TranscriptionResponse is not None

    def test_audio_edit_request_schema_imports(self):
        from common_lib.modules.audio.schemas import AudioEditRequest

        assert AudioEditRequest is not None

    def test_audio_edit_response_schema_imports(self):
        from common_lib.modules.audio.schemas import AudioEditResponse

        assert AudioEditResponse is not None


class TestAudioSchemasFields:
    """Tests for Audio schema fields"""

    def test_tts_request_has_required_fields(self):
        from common_lib.modules.audio.schemas import TTSRequest

        request = TTSRequest(text="Hello world", model_id="test-model")
        assert request.text == "Hello world"
        assert request.model_id == "test-model"

    def test_transcription_request_has_required_fields(self):
        from common_lib.modules.audio.schemas import TranscriptionRequest

        request = TranscriptionRequest(audio_path="/path/to/audio.wav")
        assert request.audio_path == "/path/to/audio.wav"

    def test_audio_edit_request_has_required_fields(self):
        from common_lib.modules.audio.schemas import AudioEditRequest

        request = AudioEditRequest(input_path="/input.wav", operation="trim")
        assert request.input_path == "/input.wav"
        assert request.operation == "trim"


class TestAudioServiceConfiguration:
    """Tests for Audio service configuration"""

    def test_service_has_generator(self):
        from common_lib.modules.audio.service import AudioService

        service = AudioService()
        assert hasattr(service, "generator")

    def test_service_has_output_dir(self):
        from common_lib.modules.audio.service import AudioService

        service = AudioService()
        assert hasattr(service, "output_dir")
        assert isinstance(service.output_dir, os.PathLike)


class TestAudioServiceBehavior:
    """Tests for Audio service behavior"""

    @pytest.mark.asyncio
    async def test_get_history_returns_list(self):
        from common_lib.modules.audio.service import audio_service

        result = await audio_service.get_history()
        assert isinstance(result, list)

    def test_generator_initialization(self):
        from common_lib.modules.audio.service import AudioService

        service = AudioService()
        assert service.generator is not None
