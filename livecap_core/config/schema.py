"""TypedDict definitions for Phase 1 core configuration planning.

These types mirror the structure documented in
`docs/dev-docs/architecture/core-config-boundaries.md` and will back the
ConfigValidator improvements planned during Phase 1.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, MutableMapping, Sequence, TypedDict

__all__ = [
    "AudioConfig",
    "AudioProcessingConfig",
    "SilenceDetectionConfig",
    "TranscriptionEngineConfig",
    "TranscriptionConfig",
    "MultiSourceInputConfig",
    "MultiSourceConfig",
    "TranslationConfig",
    "EnginesConfig",
    "QueueConfig",
    "FileModeConfig",
    "LoggingConfig",
    "DebugConfig",
    "CoreConfig",
]


class AudioProcessingConfig(TypedDict, total=False):
    max_audio_value: float
    rms_epsilon: float
    normalization_headroom: float
    default_queue_size: int
    max_queue_size: int
    queue_warning_threshold: int
    max_error_count: int
    no_data_timeout: float
    default_read_timeout: float
    optimal_blocksize_min: int
    optimal_blocksize_max: int


class AudioConfig(TypedDict, total=False):
    sample_rate: int
    chunk_duration: float
    input_device: str | None
    filter_duplicate_devices: bool
    processing: AudioProcessingConfig


class SilenceDetectionConfig(TypedDict, total=False):
    vad_threshold: float
    vad_min_speech_duration_ms: int
    vad_max_speech_duration_s: float
    vad_speech_pad_ms: int
    vad_min_silence_duration_ms: int
    vad_state_machine: MutableMapping[str, Any]


class TranscriptionEngineConfig(TypedDict, total=False):
    beam_size: int
    language: str | None
    diarisation_enabled: bool


class TranscriptionConfig(TypedDict, total=False):
    device: str | None
    engine: Literal["auto", "reazonspeech", "whisper", "canary", "voxtral", "parakeet"] | str
    input_language: str
    language_engines: Mapping[str, str]
    reazonspeech_config: MutableMapping[str, Any]


class MultiSourceInputConfig(TypedDict, total=False):
    id: str
    input_device: str | None
    gain: float | None
    enabled: bool


class MultiSourceConfig(TypedDict, total=False):
    enabled: bool
    prefer_primary: bool
    max_sources: int
    defaults: MutableMapping[str, Any]
    sources: Sequence[MultiSourceInputConfig] | MutableMapping[str, MultiSourceInputConfig]


class TranslationConfig(TypedDict, total=False):
    enabled: bool
    service: Literal["google", "riva"]
    target_language: str
    performance: MutableMapping[str, Any]
    riva_settings: MutableMapping[str, Any]


EnginesConfig = MutableMapping[str, MutableMapping[str, Any]]


class QueueConfig(TypedDict, total=False):
    max_queue_size: int | float
    timeout: float


class FileModeConfig(TypedDict, total=False):
    use_vad: bool
    min_speech_duration_ms: int
    max_silence_duration_ms: int


class LoggingConfig(TypedDict, total=False):
    log_dir: str
    file_log_level: str
    console_log_level: str


class DebugConfig(TypedDict, total=False):
    show_queue_status: bool
    verbose: bool


class _CoreConfigRequired(TypedDict):
    audio: AudioConfig
    silence_detection: SilenceDetectionConfig
    transcription: TranscriptionConfig
    multi_source: MultiSourceConfig
    engines: EnginesConfig
    queue: QueueConfig
    file_mode: FileModeConfig


class CoreConfig(_CoreConfigRequired, total=False):
    translation: TranslationConfig
    logging: LoggingConfig
    debug: DebugConfig
