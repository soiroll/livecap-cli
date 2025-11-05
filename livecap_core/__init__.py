"""Canonical re-exports for the LiveCap Core public API surface.

Phase 1 で合意した API 一覧（docs/dev-docs/architecture/core-api-spec.md）と
揃え、GUI や外部ツールが `livecap_core` 直下から主要シンボルを取得できるようにする。
"""

from .languages import Languages
from .transcription_types import (
    create_transcription_event,
    create_status_event,
    create_error_event,
    create_translation_request_event,
    create_translation_result_event,
    create_subtitle_event,
    validate_event_dict,
    get_event_type_name,
    normalize_to_event_dict,
    format_event_summary,
)
from .transcription.file_pipeline import (
    FileTranscriptionPipeline,
    FileTranscriptionProgress,
    FileProcessingResult,
    FileSubtitleSegment,
    FileTranscriptionCancelled,
)
from .config import ValidationError

__all__ = [
    'Languages',
    # 後方互換性のため既存のエクスポートを維持
    'create_transcription_event',
    'create_status_event',
    'create_error_event',
    'create_translation_request_event',
    'create_translation_result_event',
    'create_subtitle_event',
    'validate_event_dict',
    'get_event_type_name',
    'normalize_to_event_dict',
    'format_event_summary',
    'FileTranscriptionPipeline',
    'FileTranscriptionProgress',
    'FileProcessingResult',
    'FileSubtitleSegment',
    'FileTranscriptionCancelled',
    'ValidationError',
]
