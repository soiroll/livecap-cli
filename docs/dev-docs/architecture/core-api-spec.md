# LiveCap Core API Specification (Draft)

> **Status:** Phase 1 Draft  
> **Related Issues:** #91 (Phase 0 archive), #105 (Phase 1 kickoff), #115 (Phase 1 tracking)

## 1. Package Overview

```
livecap_core/
├── __init__.py                # Canonical public re-exports
├── cli.py                     # Entry points and diagnostics
├── config/                    # Configuration defaults & validation
├── resources/                 # Model/FFmpeg/resource management
├── transcription/             # File transcription pipeline
├── transcription_types.py     # Event dictionary helpers
├── i18n.py                    # Translation shim (optional extra: translation)
└── languages.py               # Language asset definitions (public)
```

Phase 1 では上記モジュールの公開可否と責務を明確にし、Phase 2 でのリポジトリ分離に備えた API 契約を確立する。

## 2. Module Inventory & Exposure

2025-10-29 時点で `rg "__all__"` / `rg "from livecap_core"` によって棚卸しした公開面と、GUI 側での利用状況を下表に整理する。

| Package surface | Current exports (per `__all__` 等) | Primary consumers | Phase 1 stance | Notes |
| --- | --- | --- | --- | --- |
| `livecap_core.__init__` | `Languages`<br>`FileTranscriptionPipeline`, `FileTranscriptionProgress`, `FileProcessingResult`, `FileSubtitleSegment`, `FileTranscriptionCancelled`<br>`create_transcription_event`, `create_status_event`, `create_error_event`, `create_translation_request_event`, `create_translation_result_event`, `create_subtitle_event`<br>`validate_event_dict`, `get_event_type_name`, `normalize_to_event_dict`, `format_event_summary`, `ValidationError` | GUI (`src/audio/transcription/multi_source_transcriber.py`, `src/engines/shared_engine_manager.py`)<br>音声・字幕マネージャ | **Public** | Phase 1 で translation イベント系と `ValidationError` をトップレベル再エクスポートし、SDK / GUI 双方が単一インポートで利用できるよう整備済み。 |
| `livecap_core.transcription` | 上記 `File*` クラス群 + `ProgressCallback`, `StatusCallback`, `FileResultCallback`, `ErrorCallback`, `SegmentTranscriber`, `Segmenter` | CLI ユーティリティ (`src/file_transcriber.py`)、テスト支援 | **Public** | コールバック型は GUI で直接利用していないが、SDK 利用を想定しドキュメント補強が必要。Phase 2 で使用例を追加。 |
| `livecap_core.transcription_types` | TypedDict 群 (`TranscriptionEventDict`, `StatusEventDict`, `ErrorEventDict`, `TranslationRequestEventDict`, `TranslationResultEventDict`, `SubtitleEventDict`)<br>イベント作成ヘルパー (`create_transcription_event`, `create_status_event`, `create_error_event`, `create_translation_request_event`, `create_translation_result_event`, `create_subtitle_event`)<br>`validate_event_dict`, `validate_translation_event`, `validate_subtitle_event`, `normalize_to_event_dict`, `get_event_type_name`, `format_event_summary` | GUI (`src/gui/widgets/transcriber/*`, `src/gui/core/managers/*`)、翻訳/字幕バックエンド | **Public** | Phase 1 の互換ポリシー: 既存フィールドは維持し、追加は optional に限定。トップレベル再エクスポートは Phase 2 で調整。 |
| `livecap_core.config` | `DEFAULT_CONFIG`, `get_default_config`, `merge_config`, `ConfigValidator`, `ValidationError` | GUI 設定ローダー (`src/config/config_loader.py`)、エンジン初期化 | **Public** | TypedDict ベースのスキーマ導入と `ValidationError` の型整備を Phase 1 で実施。 |
| `livecap_core.resources` | `ModelManager`, `FFmpegManager`, `FFmpegNotFoundError`, `ResourceLocator`<br>`get_model_manager`, `get_ffmpeg_manager`, `get_resource_locator`, `reset_resource_managers` | GUI エンジン群、CLI (`python -m livecap_core`) | **Public** | Phase 2 で `ModelManager.download_file_async` / `FFmpegManager.ensure_executable_async` 等の非同期 API を追加。既存の `models_root` / `cache_root` / `get_models_dir` / `get_temp_dir` / `temporary_directory` / `download_file` / `huggingface_cache` も後方互換として維持。 |
| `livecap_core.cli` | `main` / CLI entrypoint (`python -m livecap_core`)、`DiagnosticReport` dataclass | CLI ツール、インストール診断 | **Public (CLI)** | Phase 1 は `main` と `DiagnosticReport` のみ公式 API。補助関数の公開は Phase 2 で検討。 |
| `livecap_core.i18n` | `translate`, `register_translator`, `register_fallbacks`, `diagnose`, `I18nManager`, `I18nDiagnostics`, `TranslatorDetails` | GUI / エンジン層 (`src/engines/base_engine.py`, `src/file_transcriber.py`) | **Optional** | translation extra（`pip install livecap-core[translation]`）を導入した環境のみサポート。フォールバック登録と診断 API を Phase 2 で整備。 |
| `livecap_core.languages` | `Languages`, `LanguageInfo` | GUI 設定画面、翻訳バックエンド、エンジンメタデータ | **Public** | 後方互換ポリシー: 既存フィールド名称は保持し、追加は非破壊で行う。破壊的変更は Major リリースのみ。 |

### 2.1 Scan observations

- GUI 側では `create_translation_request_event` / `create_translation_result_event` / `create_subtitle_event` を直接 import しているため、Phase 1 で正式サポート API として位置付ける必要がある（例: `src/gui/widgets/transcriber/core_managers.py`）。  
- `ProgressCallback` などのコールバック型は現状直接利用されていないが、Pipeline 拡張時のガイドラインとして公開面の説明を追加する。  
- `register_translator` / `register_fallbacks` はエンジン初期化や翻訳バックエンドから利用されており、Phase 2 で `diagnose()` を追加して登録状態を可視化した。  
- `ModelManager` のメソッド群（`download_file`, `get_models_dir`, `temporary_directory` 等）は GUI/CLI 双方が使用。Phase 1 でサポート対象と非推奨候補を整理し、ドキュメントへ反映する。

## 3. Phase 1 Decisions & Follow-ups

| Topic | Phase 1 Decision | Follow-up / Phase 2 TODO |
| --- | --- | --- |
| CLI API (`livecap_core.cli`) | 公開 API は `main()`, `DiagnosticReport`, `diagnose()`。CLI 経由で設定・FFmpeg を確認する最小ユースケースをサポート。 | GUI からの診断呼び出しを想定した `diagnose()` を Phase 2 で追加済み。 |
| ModelManager surface | `models_root` / `cache_root` / `get_models_dir` / `get_temp_dir` / `temporary_directory` / `download_file` / `download_file_async` / `huggingface_cache` をサポート対象としてドキュメント化。名称変更は行わず、非公開メソッドは内部専用とする。 | 非同期 API は `asyncio` を前提にし、GUI からの呼び出しでも UI ブロッキングを避けられるようにした。 |
| 翻訳イベント・i18n | translation イベントヘルパーは `transcription_types` から提供し、トップレベル再エクスポートは保留。`translate` / `register_translator` / `register_fallbacks` は暫定的に維持する。 | translation extra 導入済み。Phase 2 では API 分離とトップレベル再エクスポートの範囲を再検討する。 |
| Event TypedDict ポリシー | 現行フィールドは互換維持、追加は optional で行う。破壊的変更はメジャー更新時のみ。 | 互換ポリシーを `core-api-spec.md` に追記済み。Phase 2 でサンプル／Migration ガイドを整備。 |

## 4. Reference Usage (Draft)

### 4.1 File transcription (current API surface)

```python
from pathlib import Path
from livecap_core import (
    FileTranscriptionPipeline,
    FileTranscriptionProgress,
    FileProcessingResult,
    FileSubtitleSegment,
)
from livecap_core.config import get_default_config, merge_config

base_config = get_default_config()
custom_config = merge_config(
    base_config,
    {
        "transcription": {
            "engine": "reazonspeech",
            "input_language": "ja",
        }
    },
)

def transcribe_segment(audio_chunk, sample_rate):
    # Place holder implementation; inject engine inference here.
    return f"{len(audio_chunk)} samples @ {sample_rate}Hz"

def on_progress(progress: FileTranscriptionProgress) -> None:
    status = progress.status or "processing"
    print(f"[{progress.current}/{progress.total}] {status}")

pipeline = FileTranscriptionPipeline(config=custom_config)
result: FileProcessingResult = pipeline.process_file(
    file_path=Path("sample.wav"),
    segment_transcriber=transcribe_segment,
    progress_callback=on_progress,
)

for segment in result.subtitles:
    print(f"{segment.start:0.2f}-{segment.end:0.2f}: {segment.text}")
```

### 4.2 Resource bootstrap helpers

```python
from livecap_core.resources import get_model_manager, get_ffmpeg_manager

model_manager = get_model_manager()
weights_dir = model_manager.get_models_dir("reazonspeech")
# Placeholder URL for illustration only; supply a real artifact in practice.
downloaded = model_manager.download_file(
    "https://example.invalid/demo.onnx",
    filename="demo.onnx",
)

ffmpeg_manager = get_ffmpeg_manager()
ffmpeg_path = ffmpeg_manager.ensure_executable()
ffprobe_path = ffmpeg_manager.resolve_probe()

print(f"Model root: {weights_dir}")
print(f"Cached artifact: {downloaded}")
print(f"FFmpeg path: {ffmpeg_path}")
print(f"FFprobe path: {ffprobe_path}")
```

### 4.3 Asynchronous resource helpers (Phase 2)

```python
import asyncio

from livecap_core.resources import get_ffmpeg_manager, get_model_manager


async def prepare_resources() -> None:
    manager = get_model_manager()
    artifact = await manager.download_file_async(
        "https://example.invalid/demo-large.onnx",
        filename="demo-large.onnx",
    )
    print(f"Downloaded artifact to {artifact}")

    ffmpeg_path = await get_ffmpeg_manager().ensure_executable_async()
    print(f"FFmpeg ready at {ffmpeg_path}")


asyncio.run(prepare_resources())
```

### 4.4 Event dictionary helpers

```python
from livecap_core import create_transcription_event, create_status_event

segment_event = create_transcription_event(
    text="こんにちは",
    source_id="mic-1",
    language="ja",
    display_text="こんにちは",
)

status_event = create_status_event(
    status_code="pipeline.starting",
    message="Starting diarisation stage",
    source_id="pipeline",
    metadata={"stage": "diarisation"},
)
```

各コード片は API の呼び出しシグネチャを固定する目的のドラフトであり、Phase 1 のレビューで最終化する。

## 5. Next Steps

- Phase 2 backlog へ本章のフォローアップ（CLI 追加ユースケース、ModelManager async 対応、translation extra 公開 API の整備、Nemo GPU smoke テスト）を登録する。  
- 上記リファレンスコードが実際の API で成立するか継続検証し、必要に応じて docstring・型定義を補強する。  
- Phase 1 全体レビュー後、本ドキュメントを v1.0 として確定し、Phase 2 実装の入力に用いる。
