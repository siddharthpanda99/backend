"""Audio runtime package — background-job executors for blocking audio work."""

from app.modules.audio.runtime.job_executors import ensure_audio_executors_registered

__all__ = ["ensure_audio_executors_registered"]
