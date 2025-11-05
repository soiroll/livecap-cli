"""Default configuration values for the LiveCap core layer."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

# NOTE:
# These defaults intentionally mirror the structure expected by the core
# transcription/audio subsystems so that the core package can operate without
# relying on GUI-side YAML loaders. The values are conservative and can be
# overridden by callers as needed.

DEFAULT_CONFIG: Dict[str, Any] = {
    "audio": {
        "sample_rate": 16000,
        "chunk_duration": 0.25,
        "input_device": None,
        "filter_duplicate_devices": True,
        "processing": {
            "max_audio_value": 10.0,
            "rms_epsilon": 1.0e-10,
            "normalization_headroom": 1.1,
            "default_queue_size": 10,
            "max_queue_size": 100,
            "queue_warning_threshold": 10,
            "max_error_count": 10,
            "no_data_timeout": 5.0,
            "default_read_timeout": 0.1,
            "optimal_blocksize_min": 256,
            "optimal_blocksize_max": 8192,
        },
    },
    "multi_source": {
        "max_sources": 3,
        "defaults": {
            "pywac_capture_chunk_ms": 10,
            "noise_gate": {
                "enabled": True,
                "threshold_db": -55,
                "attack_ms": 0.5,
                "release_ms": 30,
            },
        },
        "sources": {},
    },
    "silence_detection": {
        "vad_threshold": 0.5,
        "vad_min_speech_duration_ms": 250,
        "vad_max_speech_duration_s": 0,
        "vad_speech_pad_ms": 400,
        "vad_min_silence_duration_ms": 100,
        "vad_state_machine": {
            "potential_speech_timeout_frames": 10,
            "speech_end_threshold_frames": 12,
            "post_speech_padding_frames": 18,
            "potential_speech_max_duration_ms": 1000,
            "buffer_duration_s": 30,
            "pre_buffer_max_frames": 50,
            "log_state_transitions": False,
            "save_state_history": False,
            "intermediate_result_min_duration_s": 2.0,
            "intermediate_result_interval_s": 1.0,
            "speculative_execution": {
                "enabled": True,
                "confidence_threshold": 0.6,
                "max_workers": 2,
                "timeout_ms": 100,
            },
        },
    },
    "transcription": {
        "device": None,
        "engine": "auto",
        "input_language": "ja",
        "language_engines": {
            "ja": "reazonspeech",
            "en": "parakeet",
            "zh": "whispers2t_base",
            "ko": "whispers2t_base",
            "de": "voxtral",
            "fr": "voxtral",
            "es": "voxtral",
            "ru": "whispers2t_base",
            "ar": "whispers2t_base",
            "pt": "voxtral",
            "it": "voxtral",
            "hi": "voxtral",
            "default": "whispers2t_base",
        },
        "reazonspeech_config": {
            "use_int8": False,
            "num_threads": 4,
            "decoding_method": "greedy_search",
        },
    },
    "translation": {
        "enabled": False,
        "service": "google",
        "target_language": "en",
        "performance": {
            "cache_size": 3000,
            "batch_size": 5,
            "worker_count": 2,
        },
        "riva_settings": {
            "reserve_memory_gb": 2.0,
        },
    },
    "engines": {
        "reazonspeech": {},
        "parakeet": {
            "model_name": "nvidia/parakeet-tdt-0.6b-v3",
        },
        "parakeet_ja": {
            "model_name": "nvidia/parakeet-tdt_ctc-0.6b-ja",
        },
        "whispers2t_base": {
            "model_size": "base",
        },
        "whispers2t_small": {
            "model_size": "small",
        },
        "whispers2t_medium": {
            "model_size": "medium",
        },
        "whispers2t_large": {
            "model_size": "large",
        },
        "voxtral": {
            "model_name": "mistralai/Voxtral-Mini-3B-2507",
        },
    },
    "logging": {
        "log_dir": "logs",
        "file_log_level": "INFO",
        "console_log_level": "INFO",
    },
    "queue": {
        "max_queue_size": 100,
        "timeout": 0.1,
    },
    "debug": {
        "show_queue_status": False,
        "verbose": False,
    },
    "file_mode": {
        "use_vad": True,
        "min_speech_duration_ms": 200,
        "max_silence_duration_ms": 300,
    },
}


def get_default_config() -> Dict[str, Any]:
    """Return a deep copy of the default configuration."""
    return deepcopy(DEFAULT_CONFIG)


def merge_config(base: Dict[str, Any], override: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    Recursively merge two configuration dictionaries.

    Args:
        base: The base configuration that provides default values.
        override: Overrides coming from callers (can be None).

    Returns:
        A new dictionary containing the merged configuration.
    """
    if override is None:
        return deepcopy(base)

    merged = deepcopy(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = merge_config(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged
