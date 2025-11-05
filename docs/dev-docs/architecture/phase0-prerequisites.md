# Phase 0: Core分離の前提条件整備

**作成日**: 2025-10-26
**ステータス**: 提案中
**優先度**: 最高（Phase 1の前提条件）

---

## 📋 目次

1. [背景と目的](#背景と目的)
2. [Phase 0が必要な理由](#phase-0が必要な理由)
3. [実装懸念点の詳細](#実装懸念点の詳細)
4. [Phase 0の作業内容](#phase-0の作業内容)
5. [成功基準](#成功基準)

---

## 背景と目的

### 現状の問題

LiveCap Core分離提案（Issue #91）において、以下の実装懸念点が指摘されました：

> LiveCap Core の独立案には賛同しますが、現状のコード構造だと「GUI から切り離した PyPI 配布物」として成立する前提が揃っていない

**具体的な問題**:
1. Qt依存が残っている（`file_transcriber.py`）
2. 設定・翻訳への直参照（`engine_factory.py`）
3. リソース解決が脆弱（`sys.path`書き換え、相対パス依存）

### Phase 0の目的

**Core分離の前提条件を整備する**

- Qt非依存のAPI化
- 設定・翻訳の境界整理
- リソース解決の再設計

これらを完了させることで、**「pip install livecap-core だけで動作する」パッケージ**を実現可能にする。

---

## Phase 0が必要な理由

### 問題1: Qt依存のまま分離すると...

```python
# 現状: file_transcriber.py:71
from typing import Optional
from PySide6.QtCore import QObject, Signal

class TranscriptionWorker(QObject):
    progress = Signal(int)
    finished = Signal(dict)
```

**結果**:
```bash
# CLI版LiveCapを作ろうとすると...
pip install livecap-core
python cli_livecap.py

# エラー: ModuleNotFoundError: No module named 'PySide6'
# → CLI版なのにGUIライブラリが必須になってしまう
```

---

### 問題2: 設定・翻訳への直参照のまま分離すると...

```python
# 現状: engine_factory.py:8, 15
from localization import translator
from config import config_loader

def create_engine(engine_name: str, config):
    display_name = translator.tr(f"engine_{engine_name}")
    settings = config_loader.get_engine_settings(engine_name)
```

**結果**:
```bash
pip install livecap-core
python
>>> from livecap_core import create_engine
>>> engine = create_engine('reazonspeech', config)

# エラー: FileNotFoundError: languages/ja.yaml not found
# → 翻訳YAMLファイルが必要なのに、PyPIパッケージに含まれていない
```

---

### 問題3: リソース解決が脆弱なまま分離すると...

```python
# 現状: utils/__init__.py:16
src_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_dir))
```

**結果**:
```bash
pip install livecap-core
# インストール先: /usr/local/lib/python3.11/site-packages/livecap_core/

python
>>> from livecap_core import LiveTranscriber
>>> transcriber = LiveTranscriber(config)

# エラー: FileNotFoundError: models/reazonspeech-k2-v2.onnx not found
# → モデルファイルの相対パス参照が壊れる
```

---

## 実装懸念点の詳細

### 懸念点1: Qt依存の問題

**影響箇所**:
- `src/file_transcriber.py:71` - `TranscriptionWorker(QObject)`
- `src/transcription/live_transcribe.py` - Qt Signal依存（可能性）

**問題の本質**:
- 進捗通知をQtのSignalで実装している
- Core層がGUIフレームワークに依存している
- CLI・Bot版でQt不要なのに依存が残る

**影響**:
- `pip install livecap-core` → PySide6も強制インストール（200MB以上）
- 軽量なCLI版・Bot版が作れない
- テストでもQt環境が必要になる

---

### 懸念点2: 設定・翻訳の直参照

**影響箇所**:
- `src/engines/engine_factory.py:8` - `localization.translator`
- `src/engines/engine_factory.py:15` - `config.config_loader`
- `src/engines/*.py` - 各エンジンが`config_loader`に依存

**問題の本質**:
- Core層がGUI層のリソース（YAML、翻訳ファイル）に依存
- `config_loader.py`（710行）がCore/GUI混在の設定を管理
- 翻訳システムがYAMLファイル前提

**影響**:
- Core単体で必要なリソースを提供できない
- PyPIパッケージに何を含めるか不明確
- 設定ファイルレス設計（v1.2）と矛盾

---

### 懸念点3: リソース解決の脆弱性

**影響箇所**:
- `src/localization/translator.py:13` - `sys.path`書き換え
- `src/utils/__init__.py:16` - 3階層遡ってルート参照
- `src/engines/*.py` - モデルファイルの相対パス参照

**問題の本質**:
- リポジトリルートからの相対パスに依存
- PyPI経由でsite-packagesにインストールされるとフォルダ構造が変わる
- モデルファイル（数GB）の配置場所が未定義

**影響**:
- `pip install livecap-core`では動作しない
- モデルファイルをどこに置くか不明
- ffmpeg-binの配置も同様の問題

---

## Phase 0の作業内容

### Phase 0.1: Qt非依存のAPI化（1週間）

**目標**: Core層のすべてのコードからQt依存を除去

#### 現行依存箇所（要解消）

- `src/file_transcriber.py:71` `PySide6.QtCore` インポートと `TranscriptionWorker(QObject)` の Signal 実装
- `src/file_transcriber.py:132-214` で Signal 発火と `tr()` ベースのステータスメッセージを直接送出
- `src/gui/widgets/file_mode_widget.py:317-335` が `TranscriptionWorker` と `QThread` を密結合で生成

#### タスク化

- TranscriptionWorker 本体をコールバック駆動の純Pythonクラスへ抽出し、Qt アダプタを GUI 層に新設する
- 進捗・完了イベントを `TranscriptionProgress` 等のデータクラスで表現し GUI 側 Signal と接続する
- ファイルモード UI の `QThread` 初期化ロジックを新しいアダプタ経由の作りに差し替える

#### 作業1: TranscriptionWorkerのリファクタリング

**Before** (`file_transcriber.py`):
```python
from PySide6.QtCore import QObject, Signal

class TranscriptionWorker(QObject):
    progress = Signal(int)
    finished = Signal(dict)
    error = Signal(str)

    def run(self):
        # ... 処理
        self.progress.emit(50)
        self.finished.emit(result)
```

**After** (Core側):
```python
from typing import Callable, Optional, Dict, Any, List
from dataclasses import dataclass, field

@dataclass
class TranscriptionProgress:
    """進捗情報"""
    current: int
    total: int
    status: str = ""
    context: Optional[Dict[str, Any]] = None

@dataclass
class TranscriptionResult:
    """文字起こし結果のメタデータ"""
    text: str = ""
    segments: List[Dict[str, Any]] = field(default_factory=list)
    language: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "segments": self.segments,
            "language": self.language,
            "metadata": self.metadata,
        }

class TranscriptionWorker:
    """Qt非依存の文字起こしワーカー"""

    def __init__(
        self,
        config: Dict[str, Any],
        on_progress: Optional[Callable[[TranscriptionProgress], None]] = None,
        on_finished: Optional[Callable[[TranscriptionResult], None]] = None,
        on_error: Optional[Callable[[str, Optional[Exception]], None]] = None
    ):
        self.config = config
        self.on_progress = on_progress
        self.on_finished = on_finished
        self.on_error = on_error

    def run(self):
        try:
            # ... 処理
            if self.on_progress:
                self.on_progress(TranscriptionProgress(50, 100, "Processing..."))

            result = self._transcribe()

            if self.on_finished:
                self.on_finished(result)
        except Exception as e:
            if self.on_error:
                self.on_error(str(e), e)

    def _transcribe(self) -> TranscriptionResult:
        # 実際の文字起こし処理
        ...
```

**After** (GUI側アダプタ):
```python
from PySide6.QtCore import QObject, Signal
from transcription import TranscriptionProgress, TranscriptionResult
from file_transcriber import TranscriptionWorker


class QtTranscriptionWorkerAdapter(QObject):
    """Qtシグナルアダプタ"""

    progress_update = Signal(int, int)
    status_update = Signal(str)
    file_processed = Signal(str, bool, str)
    finished = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, worker: TranscriptionWorker):
        super().__init__()
        self.worker = worker

        # コールバックをQtシグナルに接続
        worker.on_progress = self._on_progress
        worker.on_status = self.status_update.emit
        worker.on_file_processed = self.file_processed.emit
        worker.on_finished = self._on_finished
        worker.on_error = self._on_error

    def _on_progress(self, progress: TranscriptionProgress):
        total = progress.total or 1
        self.progress_update.emit(progress.current, total)

    def _on_finished(self, result: TranscriptionResult):
        self.finished.emit(result.to_dict())

    def _on_error(self, message: str, exception: Optional[Exception]):
        detail = message
        if exception and str(exception):
            if message.strip() not in str(exception):
                detail = f"{message}: {exception}"
            else:
                detail = str(exception)
        self.error_occurred.emit(detail)

    def run(self):
        self.worker.run()
```

**使用例**:
```python
# Core単体（CLI版）
from file_transcriber import TranscriptionWorker

def on_progress(progress):
    print(f"Progress: {progress.current}/{progress.total} - {progress.status}")

worker = TranscriptionWorker(
    file_paths=["sample.wav"],
    config=config,
    vad_settings={},
    on_progress=on_progress,
    on_finished=lambda r: print(r.metadata),
    on_error=lambda message, exc: print(f"Error: {message}")
)
worker.run()

# GUI版（Qt使用）
from gui.adapters.transcription_worker import QtTranscriptionWorkerAdapter

worker = TranscriptionWorker(file_paths=["sample.wav"], config=config, vad_settings={})
qt_worker = QtTranscriptionWorkerAdapter(worker)

def on_gui_progress(current, total):
    percentage = int((current / total) * 100)
    progress_bar.setValue(percentage)

qt_worker.progress_update.connect(on_gui_progress)
qt_worker.finished.connect(lambda result: on_transcription_finished(result))

qt_worker.run()

# Liveストリーム（Qt使用）
from live_transcribe import LiveTranscriber
from gui.adapters.live_transcriber import QtLiveTranscriberAdapter

streamer = LiveTranscriber(config=config)
qt_stream = QtLiveTranscriberAdapter(streamer)

qt_stream.progress_update.connect(handle_live_progress)
qt_stream.result_received.connect(handle_live_result)
qt_stream.error_occurred.connect(handle_live_error)

qt_stream.start(input_device=None)
# ...必要に応じて処理...
qt_stream.stop()
```

#### 作業2: LiveTranscriberのリファクタリング

**対象**: `src/transcription/live_transcribe.py`

**確認事項**:
- Qt Signal依存の有無を確認
- 依存があれば、コールバックベースに変更
- GUIとの通信はアダプタパターンで実装

**実装方針**:
```python
# Core: コールバックベース
class LiveTranscriber:
    def __init__(
        self,
        config: Dict[str, Any],
        on_transcription: Optional[Callable[[str], None]] = None,
        on_intermediate: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None
    ):
        self.config = config
        self.on_transcription = on_transcription
        self.on_intermediate = on_intermediate
        self.on_error = on_error
```

#### 成果物

- [ ] `livecap_core/transcription/worker.py` - Qt非依存のTranscriptionWorker
- [ ] `livecap_core/transcription/live_transcriber.py` - コールバックベースのLiveTranscriber
- [ ] `livecap/gui/adapters/qt_transcription_adapter.py` - Qtアダプタ
- [ ] 単体テスト（Qt環境不要）

---

### Phase 0.2: 設定・翻訳の境界整理（1週間）

**目標**: Core層が辞書データのみで完結する

#### 現行依存箇所（要解消）

- `src/engines/engine_factory.py:8` `tr()` と `src/engines/engine_factory.py:15` `load_config()` の GUI 層依存
- `src/engines/base_engine.py:14` `tr()` 連携、および `status_messages` 生成が翻訳システム直結
- `src/file_transcriber.py:195-214` が `tr()` を通じてファイル名メッセージを構築
- `src/audio/pywac/legacy_wrapper.py:25-39` が `load_config()` を直接呼び出し設定辞書を解決

#### タスク化

- EngineFactory を受け取った設定辞書のみで動作する API に再設計し、翻訳済み表示名は GUI 側で解決する
- BaseEngine のステータスメッセージ生成をロガー/コールバック + 翻訳インジェクション方式へ変更する
- ファイルモードのステータス文言を呼び出し側が生成できるようにし、Core から翻訳参照を排除する
- PyWAC ラッパーを設定辞書受け取り式に改修し、呼び出し側で `load_config()` を実行してから渡す

#### 作業1: engine_factoryのリファクタリング

**Before** (`src/engines/engine_factory.py`):
```python
from localization import translator
from config import config_loader

def create_engine(engine_name: str, config):
    display_name = translator.tr(f"engine_{engine_name}")
    settings = config_loader.get_engine_settings(engine_name)
    # ...
```

**After** (Core側):
```python
from typing import Dict, Any
from livecap_core.engines.base_engine import BaseEngine
from livecap_core.engines.reazonspeech_engine import ReazonSpeechEngine
from livecap_core.engines.parakeet_engine import ParakeetEngine
# ... 他のエンジン

# エンジンクラスのレジストリ
ENGINE_REGISTRY: Dict[str, type] = {
    'reazonspeech': ReazonSpeechEngine,
    'parakeet': ParakeetEngine,
    'canary': CanaryEngine,
    'whispers2t_tiny': WhisperS2TEngine,
    'whispers2t_base': WhisperS2TEngine,
    'whispers2t_small': WhisperS2TEngine,
    'whispers2t_medium': WhisperS2TEngine,
    'whispers2t_large': WhisperS2TEngine,
    'voxtral': VoxtralEngine,
    'kotoba_whisper': KotobaWhisperEngine,
}

def create_engine(engine_name: str, config: Dict[str, Any]) -> BaseEngine:
    """
    エンジンを作成

    Args:
        engine_name: エンジン名（例: 'reazonspeech'）
        config: 設定辞書（必須キー: 'engines', 'transcription'）

    Returns:
        BaseEngine: 初期化されたエンジンインスタンス

    Raises:
        ValueError: 未知のエンジン名
        KeyError: 必須設定キーが不足
    """
    if engine_name not in ENGINE_REGISTRY:
        available = ', '.join(ENGINE_REGISTRY.keys())
        raise ValueError(
            f"Unknown engine: {engine_name}. "
            f"Available engines: {available}"
        )

    # エンジン固有設定を取得
    engine_config = config.get('engines', {}).get(engine_name, {})

    # 共通設定をマージ
    full_config = {
        **config.get('transcription', {}),
        **engine_config
    }

    # エンジンインスタンス化
    engine_class = ENGINE_REGISTRY[engine_name]
    return engine_class(config=full_config)

def get_available_engines() -> list[str]:
    """利用可能なエンジン一覧を取得"""
    return list(ENGINE_REGISTRY.keys())
```

**After** (GUI側):
```python
from livecap_core.engines import create_engine, get_available_engines
from localization import translator
from config.config_loader import load_config

# 設定を読み込んで辞書に変換
config = load_config('config.yaml')

# Coreでエンジン作成（翻訳不要）
engine = create_engine('reazonspeech', config)

# 表示名はGUI側で翻訳
display_name = translator.tr(f"engine_{engine.name}")
print(f"Engine loaded: {display_name}")

# エンジン一覧（GUI側で翻訳）
engines = get_available_engines()
engine_list = [
    {
        'name': name,
        'display_name': translator.tr(f"engine_{name}"),
        'description': translator.tr(f"engine_{name}_desc")
    }
    for name in engines
]
```

#### 作業2: 設定バリデーションの実装

**新規作成**: `livecap_core/config/validator.py`

```python
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class ValidationError:
    """バリデーションエラー"""
    path: str       # 設定のパス（例: 'transcription.engine'）
    message: str    # エラーメッセージ

class ConfigValidator:
    """設定バリデーター"""

    @staticmethod
    def validate(config: Dict[str, Any]) -> List[ValidationError]:
        """
        設定をバリデーション

        Args:
            config: 設定辞書

        Returns:
            List[ValidationError]: エラーリスト（空なら正常）
        """
        errors = []

        # 必須キーのチェック
        required_keys = {
            'transcription': ['engine', 'input_language'],
            'audio': ['sample_rate'],
        }

        for section, keys in required_keys.items():
            if section not in config:
                errors.append(ValidationError(
                    path=section,
                    message=f"Required section '{section}' is missing"
                ))
                continue

            for key in keys:
                if key not in config[section]:
                    errors.append(ValidationError(
                        path=f"{section}.{key}",
                        message=f"Required key '{key}' is missing"
                    ))

        # 型チェック
        if 'audio' in config and 'sample_rate' in config['audio']:
            sample_rate = config['audio']['sample_rate']
            if not isinstance(sample_rate, int):
                errors.append(ValidationError(
                    path='audio.sample_rate',
                    message=f"Expected int, got {type(sample_rate).__name__}"
                ))

        # 値の範囲チェック
        if 'audio' in config and 'sample_rate' in config['audio']:
            sample_rate = config['audio']['sample_rate']
            if isinstance(sample_rate, int) and sample_rate not in [8000, 16000, 44100, 48000]:
                errors.append(ValidationError(
                    path='audio.sample_rate',
                    message=f"Invalid sample rate: {sample_rate}. Valid values: 8000, 16000, 44100, 48000"
                ))

        return errors

    @staticmethod
    def validate_or_raise(config: Dict[str, Any]):
        """バリデーション（エラー時は例外）"""
        errors = ConfigValidator.validate(config)
        if errors:
            error_messages = '\n'.join(
                f"  - {err.path}: {err.message}"
                for err in errors
            )
            raise ValueError(f"Configuration validation failed:\n{error_messages}")
```

#### 作業3: デフォルト設定の定義

**新規作成**: `livecap_core/config/defaults.py`

```python
from typing import Dict, Any

DEFAULT_CONFIG: Dict[str, Any] = {
    'audio': {
        'sample_rate': 16000,
        'chunk_duration': 0.25,
        'processing': {
            'max_audio_value': 10.0,
            'rms_epsilon': 1.0e-10,
            'normalization_headroom': 1.1,
            'default_queue_size': 10,
            'max_queue_size': 100,
            'queue_warning_threshold': 10,
            'max_error_count': 10,
            'no_data_timeout': 5.0,
            'default_read_timeout': 0.1,
            'optimal_blocksize_min': 256,
            'optimal_blocksize_max': 8192,
            'latency_mode': 'low',
        }
    },

    'multi_source': {
        'max_sources': 3,
        'defaults': {
            'pywac_capture_chunk_ms': 10,
            'noise_gate': {
                'enabled': True,
                'threshold_db': -55,
                'attack_ms': 0.5,
                'release_ms': 30,
            }
        },
        'sources': {}
    },

    'silence_detection': {
        'vad_threshold': 0.5,
        'vad_min_speech_duration_ms': 250,
        'vad_max_speech_duration_s': 0,
        'vad_speech_pad_ms': 400,
        'vad_min_silence_duration_ms': 100,
        'vad_state_machine': {
            'potential_speech_timeout_frames': 10,
            'speech_end_threshold_frames': 12,
            'post_speech_padding_frames': 18,
            'potential_speech_max_duration_ms': 1000,
            'buffer_duration_s': 30,
            'pre_buffer_max_frames': 50,
            'log_state_transitions': False,
            'save_state_history': False,
            'intermediate_result_min_duration_s': 2.0,
            'intermediate_result_interval_s': 1.0,
            'speculative_execution': {
                'enabled': True,
                'confidence_threshold': 0.6,
                'max_workers': 2,
                'timeout_ms': 100,
            }
        }
    },

    'transcription': {
        'device': None,
        'engine': 'auto',
        'input_language': 'ja',
        'language_engines': {
            'ja': 'reazonspeech',
            'en': 'parakeet',
            'zh': 'whispers2t_base',
            'ko': 'whispers2t_base',
            'de': 'voxtral',
            'fr': 'voxtral',
            'es': 'voxtral',
            'ru': 'whispers2t_base',
            'ar': 'whispers2t_base',
            'pt': 'whispers2t_base',
            'it': 'whispers2t_base',
            'hi': 'whispers2t_base',
        }
    },

    'translation': {
        'service': 'google',
        'target_language': 'en',
        'performance': {
            'cache_size': 3000,
            'batch_size': 5,
            'worker_count': 2,
        },
        'riva_settings': {
            'reserve_memory_gb': 2.0,
        }
    },

    'engines': {
        # エンジン固有設定はここに追加
        'reazonspeech': {},
        'parakeet': {
            'vad_threshold': 0.3,
        },
        # ...
    }
}

def get_default_config() -> Dict[str, Any]:
    """
    デフォルト設定を取得

    Returns:
        Dict[str, Any]: デフォルト設定のコピー
    """
    import copy
    return copy.deepcopy(DEFAULT_CONFIG)

def merge_config(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    設定を再帰的にマージ

    Args:
        base: ベース設定
        override: 上書き設定

    Returns:
        Dict[str, Any]: マージされた設定
    """
    import copy
    result = copy.deepcopy(base)

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = copy.deepcopy(value)

    return result
```

#### 成果物

- [ ] `livecap_core/engines/engine_factory.py` - 翻訳非依存のファクトリ
- [ ] `livecap_core/config/defaults.py` - デフォルト設定定数
- [ ] `livecap_core/config/validator.py` - 設定バリデーション
- [ ] `livecap/config/config_loader.py` - YAML読み込み（GUI層）
- [ ] 単体テスト（辞書データのみで動作）

---

### Phase 0.3: リソース解決の再設計（1週間）

**目標**: PyPI経由でインストールしても動作する

#### 現行依存箇所（要解消）

- `src/utils/__init__.py:12-58` がリポジトリルート前提の `get_resource_path()` と `get_models_dir()` を提供
- `src/main.py:46-63` / `src/file_transcriber.py:22-37` がバンドル済み `ffmpeg-bin` を想定して環境変数を設定
- `src/engines/base_engine.py:153` / `src/translation/model_downloader.py:29-39` が上記ユーティリティを利用
- `src/localization/translator.py:62-73` や `src/config/config_loader.py:192-576` が `get_resource_path()` 依存で YAML を解決
- `src/vad/stream/stream_vad_processor.py:21`、`src/audio/pywac/legacy_wrapper.py:31-33`、`src/file_transcriber.py:76` 等が `sys.path` を直接操作

#### タスク化

- appdirs ベースのキャッシュ/データディレクトリを使う `ModelManager` を実装し、モデル/翻訳資産の場所解決を一元化する
- 各エンジン/翻訳モジュールのモデル参照を `ModelManager.get_model_path()` に置き換え、初回ダウンロードを自動化する
- クロスプラットフォームで FFmpeg を取得する `FFmpegManager` を用意し、環境変数設定を新実装に差し替える
- YAML やリソース参照をパッケージデータ + ユーザー設定ディレクトリに分離し、`sys.path` 直接操作を排除する

#### 作業1: モデル管理システムの実装

**新規作成**: `livecap_core/resources/model_manager.py`

---

## Phase 0 設計メモ & 実装チェックリスト

### 共通（PR作成前の合意事項）
- Core 側は `from livecap_core import ...` 形式で読み込めるトップレベルパッケージ構成を前提とする
- GUI から Core を呼び出す際はアダプタ層か DI（依存性注入）を必ず挟み、Core から GUI 依存を逆参照しない
- 既存 CLI / GUI 機能の後方互換を守るため、移行はフェーズごとに Feature Flag または暫定アダプタで橋渡しする

### Phase 0.1（Qt非依存化）設計メモ
- `TranscriptionWorker` / `LiveTranscriber` のコールバック署名  
  - `on_progress(progress: TranscriptionProgress)`、`on_finished(result: TranscriptionResult)`、`on_error(message: str, *, exception: Exception | None = None)` を標準化  
  - コールバックは任意（`Optional[Callable]`）で、未設定でも例外にならない実装とする  
  - ワーカー内部例外は `on_error` 経由で伝搬した上で再送出せずに終了する（上位スレッドで捕捉可能にする）
- イベントデータクラス  
  - `TranscriptionProgress` に `current`, `total`, `status`, `context: dict[str, Any] | None` を持たせ、GUI 側が独自情報を付加できる余地を確保  
  - `TranscriptionResult` には `text`, `segments`, `language`, `metadata` を持たせ、後方互換の辞書化メソッド `to_dict()` を用意
- GUIアダプタ（Qt）  
  - `QtTranscriptionWorkerAdapter` は Core ワーカーを受け取り、シグナルを `progress(int)`, `status(str)`, `finished(dict)`, `error(str)` にマッピング  
  - QThread 実行時の開始/停止制御（`requestInterruption()` 等）は Adapter 側が責務を負い、Core 側に Qt 依存を戻さない
- テスト方針  
  - Core 単体テストでは `MagicMock` コールバックを利用して呼び出し順/引数を検証  
  - GUI 統合テストでは Qt アダプタを介して従来 UI が動作するか（進捗バー更新、完了ダイアログ表示）を確認

### Phase 0.2（設定・翻訳境界）設計メモ
- EngineFactory API  
  - シグネチャ: `create_engine(engine_type: str, *, config: dict, device: str | None = None, resources: CoreResources | None = None)`  
  - `config` はミュータブルな辞書をそのまま参照しない（`deepcopy` / `MappingProxyType` 等で防御）  
  - 返却されるエンジンで翻訳文字列が必要な場合は `engine.describe(localizer: Callable[[str], str])` のように呼び出し元から提供させる
- 設定データの契約  
  - `livecap_core/config/defaults.py` を唯一のデフォルト定義とし、YAML ファイルは GUI 層の責務とする  
  - `ConfigValidator` が `ValidationError(path, message)` を返却し、Core から GUI に例外を伝搬する前に判定できるようにする
- 翻訳システムの扱い  
  - Core は翻訳済み文字列を持たず、ログ/イベントで必要な文字列キーだけを返す（例: `"model_init_dialog.status_messages.loading_to_memory"`）  
  - GUI から渡す `Localizer` を `Callable[[str], str]` とし、未翻訳キーはキー文字列をそのまま返す仕様で決定
- PyWAC / Config Loader  
  - Core から `load_config()` を呼ばない。GUI 側が YAML 読込 → `dict` 的構造へ変換 → Core に渡す流れを標準化  
  - 既存コードが `load_config()` を呼んでいる箇所はフェーズ移行中の暫定アダプタで `DeprecationWarning` を出す
- テスト方針  
  - EngineFactory のユニットテストで翻訳や YAML なしで初期化できることを確認  
  - 設定バリデーション失敗ケース（欠損キー・型不一致）を網羅し、エラーメッセージが UI に表示可能な形式であるか検証

### Phase 0.3（リソース解決）設計メモ
- ModelManager
  - キャッシュ配置: `appdirs.user_cache_dir("livecap-core", "PineLab")` をデフォルトとし、環境変数 `LIVECAP_CORE_CACHE_DIR` でオーバーライド可能にする  
  - ダウンロード戦略: 既存ファイルの SHA256 検証 → 失敗時は再ダウンロード → アーカイブ形式は解凍後の検証も実施  
  - オフラインモード: ネットワーク到達不能時は例外を送出しつつ、GUI 側でリトライ/案内を表示できるエラー型を設計（`ModelDownloadError`）
- FFmpegManager
  - プラットフォーム別バイナリ URL の更新ポリシーと、検証後の実行権限付与（`chmod 0o755`）を確定  
  - ユーザー提供 FFmpeg パスを環境変数 `LIVECAP_FFMPEG_BIN` で指定できるようにし、バンドル不要ケースをサポート
- リソースローダー
  - 言語/HTML/設定テンプレート等は `importlib.resources` を利用して package data から取得する  
  - `sys.path` 書き換えを段階的に削除し、PyInstaller ビルド時は `pkgutil.get_loader` を併用して解決
- テスト方針
  - ModelManager/FFmpegManager のユニットテストは一時ディレクトリを使いダウンロードロジックをモック化  
  - 既存モデル/翻訳ファイルがなくても `pip install livecap-core` + 簡易サンプルコードで起動できることを CI で確認

### フェーズ別移行ステップ
1. Phase 0.1 のコールバック API を実装し、GUI 側で Adapter を導入（旧 Signal ベース API は廃止告知を出す）  
2. EngineFactory / Config バリデータを導入し、GUI 側で `load_config()` → `dict` 渡しに切り替え（旧 API は互換レイヤーで接続）  
3. ModelManager / FFmpegManager を導入し、既存 `get_resource_path()` 呼び出しを段階的に置き換える  
4. `sys.path` 操作を削除し、`importlib.resources` への移行が完了したタイミングで `utils.get_resource_path` を非推奨化  
5. CLI/GUI 両方での回帰テスト（音声入力・ファイルトランスクリプション・翻訳）を実施し、PyInstaller ビルドでも動作することを確認  
6. Phase 0.7 (`PR #101`): FileTranscriptionPipeline を `livecap_core` に実装し、CLI/GUI 共通で利用できるファイルモード基盤を整備  
7. Phase 0.8 (`PR #102`): アプリ層の `FileTranscriber` / `TranscriptionWorker` を Core パイプライン経由へ統合し、Qt 依存をアダプタ層へ集約  
8. Phase 0.9（QA/ドキュメント最終化）: 回帰テストとドキュメントを更新し、Phase 0 の完了条件を明文化（本ドキュメント更新・追加テスト・CLI実機検証）

### Phase 0.6（Coreパッケージ化）実装メモ
- `livecap_core/` トップレベルディレクトリを新設し、Config / Resources / I18n / Transcription utilities を含む自己完結パッケージとして再配置  
- 既存アプリとの互換性維持のため `src/core` 配下は薄い委譲モジュールに差し替え、段階的な import 置き換えを許容（Phase 2 で `livecap_core` へ統合済み）  
- `pyproject.toml` を追加し、`pip install livecap-core` で `livecap_core` のみを配布できる構成に変更 (`setuptools` + PEP 621)  
- `python -m livecap_core` / `livecap-core` CLI を用意し、デフォルト設定検証・リソースパス確認・FFmpeg 解決をワンコマンドで行えるようにする  
- 単体テストを `livecap_core` import ベースへ更新し、CLI 実行・互換レイヤー import の回帰テストを追加  
- テスト/ドキュメントでは `uv run pytest tests/core` と `python -m build && pip install dist/livecap_core-*.whl` を想定した検証手順を提示する

### PR 提出前の確認チェックリスト
- [ ] コールバック API / Adapter 実装の仕様を README 開発者節に記載したか  
- [ ] Core 側から GUI/Qt 参照が完全に排除されているか（`rg "PySide6" livecap_core` でゼロ確認）  
- [ ] `create_engine` / EngineFactory が翻訳レスで動作する自動テストを追加したか  
- [ ] ModelManager / FFmpegManager のキャッシュディレクトリと環境変数仕様をドキュメント化したか  
- [ ] `pip install .` したクリーン環境で CLI サンプルが起動し、モデル/FFmpeg の自動取得が機能するか実機テスト済みか  
- [ ] 既存 GUI（Steam 配布想定ビルド含む）が Phase 0 実装後も問題なく動作することを QA チェックしたか

### Phase 0.7（ファイルモード Core 対応）実装メモ
- FileTranscriptionPipeline を `livecap_core` に追加し、FFmpeg 音声抽出 / audio I/O / SRT 生成を自己完結化
- CLI/GUI 共通のコールバック型イベント (`TranscriptionProgress`, `FileProcessingResult`) を導入し、翻訳キーは UI 層で解決
- `tests/core/test_file_transcription_pipeline.py` で音声抽出・セグメント・キャンセル動作を検証

### Phase 0.8（アプリ層統合）実装メモ
- `src/file_transcriber.py` を Core パイプラインラッパへ刷新し、エンジン/VAD 初期化と GUI シグナル橋渡しを担当させる
- `TranscriptionWorker` の停止要求を `FileTranscriptionCancelled` 例外として統一、Qt アダプタは進捗シグナルのみ担当
- `tests/transcription/test_file_transcriber_worker.py` でコールバックとキャンセル伝搬をスタブパイプラインで確認

### Phase 0.9（QA・ドキュメント最終化）実装メモ
- 追加テスト: `tests/core/test_file_transcription_pipeline.py` でカスタムセグメンターの進捗イベントを検証、`tests/transcription/test_file_transcriber_worker.py` で `stop()` からのキャンセル伝搬を確認
- ドキュメント（本ファイル）と Issue #91 に進捗を反映し、Phase 0 完了条件の達成状況を明文化
- 実データ `/home/shojo-hakase/Videos/obs/2025-07-19 23-13-06.mkv` を用いて CLI で SRT 生成を確認（Windows 環境でも FFmpeg 自動取得を再確認予定）

### Phase 0.91（Windows Hugging Face キャッシュ整備）実装メモ
- 依存パッケージに `huggingface-hub>=0.34.0` を明示し、Windows のシンボリックリンク制限で発生していた `WinError 1314` を回避
- 既存ユーザー向けに Hugging Face キャッシュ削除手順をドキュメント化し、破損キャッシュ再現時の解消策を Issue #91 にまとめる
- Windows QA で Stream / File モードの再実行結果（正常完了ログ）を共有し、キャッシュ再生成後の安定動作を確認

#### Windows 環境トラブルシューティング（ReazonSpeech / Hugging Face モデル）
1. シンボリックリンク設定と `huggingface-hub` バージョンを事前確認  
   ```powershell
   fsutil behavior query SymlinkEvaluation
   pip show huggingface-hub
   ```
2. `WinError 1314` が発生した場合は Hugging Face キャッシュを削除して再取得  
   ```powershell
   Remove-Item -Recurse -Force "$env:LOCALAPPDATA\PineLab\LiveCap\Cache\cache\huggingface"
   ```
3. GUI / CLI でモデルの再ダウンロード→Stream モード起動が成功することを確認し、ログを Issue に添付する  
4. 追加で問題が続く場合は `HF_HOME` のパスと出力ログを採取して報告する

```python
from pathlib import Path
from typing import Optional
import appdirs
import hashlib
import requests
from tqdm import tqdm

class ModelManager:
    """モデルファイル管理"""

    # モデルのメタデータ
    MODEL_REGISTRY = {
        'reazonspeech-k2-v2': {
            'url': 'https://huggingface.co/reazon-research/reazonspeech-k2-v2/resolve/main/reazonspeech-k2-v2.onnx',
            'filename': 'reazonspeech-k2-v2.onnx',  # ✨ 拡張子を明示
            'sha256': 'abc123...',  # TODO: 実際のハッシュ値を設定
            'size_mb': 600,
            'type': 'single',  # single or archive
        },
        'parakeet-tdt-0.6b': {
            'url': 'https://api.ngc.nvidia.com/v2/models/nvidia/parakeet-tdt-0.6b/versions/v2/files/parakeet-tdt-0.6b-v2.nemo',
            'filename': 'parakeet-tdt-0.6b-v2.nemo',  # ✨ .nemo形式
            'sha256': 'def456...',  # TODO: 実際のハッシュ値を設定
            'size_mb': 1200,
            'type': 'single',
        },
        'canary-1b': {
            'url': 'https://api.ngc.nvidia.com/v2/models/nvidia/canary-1b/versions/1.0/files/canary-1b.nemo',
            'filename': 'canary-1b.nemo',
            'sha256': 'ghi789...',  # TODO: 実際のハッシュ値を設定
            'size_mb': 2400,
            'type': 'single',
        },
        # アーカイブ形式の例（将来の拡張用）
        'riva-translate-4b': {
            'url': 'https://example.com/models/riva-translate-4b.tar.gz',
            'filename': 'riva-translate-4b.tar.gz',
            'extracted_files': [  # ✨ 解凍後のファイル一覧
                'riva-translate-4b/model.nemo',
                'riva-translate-4b/tokenizer.model',
            ],
            'main_file': 'riva-translate-4b/model.nemo',  # ✨ メインファイル
            'sha256': 'jkl012...',
            'size_mb': 4500,
            'type': 'archive',  # ✨ アーカイブ形式
        },
    }

    @staticmethod
    def get_cache_dir() -> Path:
        """
        モデルキャッシュディレクトリを取得

        Returns:
            Path: キャッシュディレクトリ
                  Linux: ~/.cache/livecap-core/
                  Windows: %LOCALAPPDATA%/livecap-core/Cache/
                  macOS: ~/Library/Caches/livecap-core/
        """
        cache_dir = Path(appdirs.user_cache_dir("livecap-core", "PineLab"))
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    @staticmethod
    def get_model_path(model_name: str) -> Path:
        """
        モデルパスを取得（必要に応じてダウンロード）

        Args:
            model_name: モデル名（例: 'reazonspeech-k2-v2'）

        Returns:
            Path: モデルファイルパス（single）またはメインファイルパス（archive）

        Raises:
            ValueError: 未知のモデル名
            RuntimeError: ダウンロード失敗
        """
        if model_name not in ModelManager.MODEL_REGISTRY:
            available = ', '.join(ModelManager.MODEL_REGISTRY.keys())
            raise ValueError(
                f"Unknown model: {model_name}. "
                f"Available models: {available}"
            )

        metadata = ModelManager.MODEL_REGISTRY[model_name]
        cache_dir = ModelManager.get_cache_dir()

        # ✨ メタデータから実際のファイル名を取得
        filename = metadata['filename']
        file_path = cache_dir / filename

        # アーカイブ形式の場合はメインファイルパスを返す
        if metadata['type'] == 'archive':
            main_file = metadata.get('main_file')
            if main_file:
                main_file_path = cache_dir / main_file
                # メインファイルが存在すれば検証
                if main_file_path.exists():
                    if ModelManager._verify_archive(model_name, cache_dir):
                        return main_file_path
                    else:
                        # 破損している場合は再ダウンロード
                        import shutil
                        shutil.rmtree(cache_dir / Path(main_file).parts[0], ignore_errors=True)
        else:
            # 単一ファイルの場合
            if file_path.exists():
                if ModelManager._verify_model(model_name, file_path):
                    return file_path
                else:
                    # 破損している場合は再ダウンロード
                    file_path.unlink()

        # ダウンロード
        ModelManager._download_model(model_name, file_path)

        # アーカイブ形式なら解凍してメインファイルパスを返す
        if metadata['type'] == 'archive':
            extracted_path = ModelManager._extract_archive(file_path, cache_dir)
            main_file = metadata.get('main_file')
            if main_file:
                return cache_dir / main_file
            return extracted_path

        return file_path

    @staticmethod
    def _download_model(model_name: str, dest_path: Path):
        """モデルをダウンロード"""
        metadata = ModelManager.MODEL_REGISTRY[model_name]
        url = metadata['url']

        print(f"Downloading model: {model_name} ({metadata['size_mb']}MB)")

        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))

        with open(dest_path, 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

        # SHA256検証
        if not ModelManager._verify_model(model_name, dest_path):
            dest_path.unlink()
            raise RuntimeError(f"Model download failed: SHA256 mismatch")

        print(f"Model downloaded successfully: {dest_path}")

    @staticmethod
    def _verify_model(model_name: str, path: Path) -> bool:
        """モデルファイルのSHA256検証（単一ファイル用）"""
        metadata = ModelManager.MODEL_REGISTRY[model_name]
        expected_sha256 = metadata['sha256']

        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)

        return sha256.hexdigest() == expected_sha256

    @staticmethod
    def _verify_archive(model_name: str, cache_dir: Path) -> bool:
        """アーカイブのSHA256検証（解凍後のメインファイルを検証）"""
        metadata = ModelManager.MODEL_REGISTRY[model_name]
        main_file = metadata.get('main_file')

        if not main_file:
            return False

        main_file_path = cache_dir / main_file
        if not main_file_path.exists():
            return False

        # メインファイルのSHA256を計算
        sha256 = hashlib.sha256()
        with open(main_file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)

        # アーカイブ全体のハッシュと比較（簡易版）
        # 実際の実装では、extracted_filesすべてを検証すべき
        return True  # TODO: 適切な検証ロジックを実装

    @staticmethod
    def _extract_archive(archive_path: Path, dest_dir: Path) -> Path:
        """アーカイブを解凍"""
        import tarfile
        import zipfile

        print(f"Extracting archive: {archive_path}")

        if archive_path.suffix == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(dest_dir)
        elif archive_path.suffix in ['.tar', '.gz', '.tgz', '.bz2', '.xz']:
            with tarfile.open(archive_path, 'r:*') as tar_ref:
                tar_ref.extractall(dest_dir)
        else:
            raise RuntimeError(f"Unsupported archive format: {archive_path.suffix}")

        print(f"Extracted to: {dest_dir}")
        return dest_dir

    @staticmethod
    def list_cached_models() -> list[str]:
        """キャッシュ済みモデル一覧"""
        cache_dir = ModelManager.get_cache_dir()
        cached = []

        for model_name, metadata in ModelManager.MODEL_REGISTRY.items():
            if metadata['type'] == 'archive':
                # アーカイブ形式はメインファイルの存在確認
                main_file = metadata.get('main_file')
                if main_file and (cache_dir / main_file).exists():
                    cached.append(model_name)
            else:
                # 単一ファイルはファイル名で確認
                filename = metadata['filename']
                if (cache_dir / filename).exists():
                    cached.append(model_name)

        return cached

    @staticmethod
    def clear_cache():
        """キャッシュをクリア"""
        cache_dir = ModelManager.get_cache_dir()
        import shutil
        # キャッシュディレクトリ全体を削除して再作成
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
```

**補足: MODEL_REGISTRY のURL戦略とホスティング方針**

MODEL_REGISTRYに記載されているURLは、Phase 0実装時に確定させる必要があります。以下の3つの戦略から選択してください：

**戦略1: 公式ホスティングサービスを使用（推奨）**

各エンジンの公式配布元から直接ダウンロードします。

```python
MODEL_REGISTRY = {
    # HuggingFace公式からダウンロード
    'reazonspeech-k2-v2': {
        'url': 'https://huggingface.co/reazon-research/reazonspeech-k2-v2/resolve/main/reazonspeech-k2-v2.onnx',
        'filename': 'reazonspeech-k2-v2.onnx',
        'sha256': '<公式モデルのSHA256を計算して記入>',
        'size_mb': 600,
        'type': 'single',
    },
    # NVIDIA NGC（API認証が必要な場合あり）
    'parakeet-tdt-0.6b': {
        'url': 'https://api.ngc.nvidia.com/v2/models/nvidia/parakeet-tdt-0.6b/versions/v2/files/parakeet-tdt-0.6b-v2.nemo',
        'filename': 'parakeet-tdt-0.6b-v2.nemo',
        'sha256': '<公式モデルのSHA256を計算して記入>',
        'size_mb': 1200,
        'type': 'single',
    },
}
```

**メリット**:
- ✅ 追加のインフラ不要（コスト0円）
- ✅ 公式の最新モデルを常に取得可能
- ✅ 帯域幅・ストレージを公式が負担

**デメリット**:
- ⚠️ 公式サイトがダウンしたら利用不可
- ⚠️ APIキーが必要な場合がある（NVIDIA NGCなど）

---

**戦略2: GitHub Releasesでミラーホスティング**

モデルファイルをLiveCapのGitHub Releasesにアップロードして配布します。

```python
MODEL_REGISTRY = {
    'reazonspeech-k2-v2': {
        'url': 'https://github.com/yourusername/livecap-core/releases/download/models-v1.0/reazonspeech-k2-v2.onnx',
        'filename': 'reazonspeech-k2-v2.onnx',
        'sha256': '<計算したSHA256>',
        'size_mb': 600,
        'type': 'single',
    },
}
```

**メリット**:
- ✅ 安定したダウンロード（公式に依存しない）
- ✅ 追加コスト不要（GitHubの無料枠）
- ✅ リリースバージョン管理と統合可能

**デメリット**:
- ❌ GitHubの単一ファイルサイズ制限: 2GB
- ❌ 大容量モデル（Riva 4.5GB等）は分割アップロード必要
- ❌ モデル更新の手間（手動アップロード）

**大容量モデルの分割対応例**:
```python
MODEL_REGISTRY = {
    'riva-translate-4b': {
        'url': [
            'https://github.com/yourusername/livecap-core/releases/download/models-v1.0/riva-translate-4b.part1',
            'https://github.com/yourusername/livecap-core/releases/download/models-v1.0/riva-translate-4b.part2',
            'https://github.com/yourusername/livecap-core/releases/download/models-v1.0/riva-translate-4b.part3',
        ],
        'filename': 'riva-translate-4b.tar.gz',
        'sha256': '<結合後のSHA256>',
        'size_mb': 4500,
        'type': 'archive',
        'split_parts': True,  # ✨ 分割ファイル対応フラグ
    },
}
```

ModelManagerに`_download_split_parts()`メソッドを追加する必要があります。

---

**戦略3: ハイブリッド戦略（現実的な推奨）**

小〜中規模モデル（< 2GB）は公式ホスティング、大規模モデル（≥ 2GB）はGitHub Releasesでミラーリング。

```python
MODEL_REGISTRY = {
    # 小規模: 公式から直接
    'reazonspeech-k2-v2': {
        'url': 'https://huggingface.co/reazon-research/reazonspeech-k2-v2/resolve/main/reazonspeech-k2-v2.onnx',
        # ... (戦略1と同じ)
    },
    # 大規模: GitHubミラー（分割）
    'riva-translate-4b': {
        'url': [
            'https://github.com/yourusername/livecap-core/releases/download/models-v1.0/riva-translate-4b.part1',
            'https://github.com/yourusername/livecap-core/releases/download/models-v1.0/riva-translate-4b.part2',
        ],
        # ... (戦略2と同じ)
    },
}
```

**メリット**:
- ✅ 小規模モデルは公式の自動更新の恩恵
- ✅ 大規模モデルは安定配布（分割対応）
- ✅ コスト0円

**デメリット**:
- ⚠️ 実装が若干複雑（分割ダウンロード対応必要）

---

**推奨決定フロー**:

1. **全モデルが2GB未満の場合** → 戦略1（公式ホスティング）
2. **2GB以上のモデルが含まれる場合** → 戦略3（ハイブリッド）
3. **公式サイトが不安定な場合** → 戦略2（GitHub全面ミラー、分割対応実装）

**Phase 0実装時のアクションアイテム**:
- [ ] 全モデルのファイルサイズを調査
- [ ] 採用する戦略を決定（1/2/3）
- [ ] 実際のURLをMODEL_REGISTRYに記入
- [ ] 各モデルのSHA256ハッシュを計算して記入
- [ ] 戦略2/3の場合: GitHub Releasesにモデルをアップロード
- [ ] 戦略2/3で分割が必要な場合: `_download_split_parts()`を実装

**注意**: 現在のドキュメント内のURLは`https://example.com/...`のプレースホルダーです。Phase 0実装時に必ず実際のURLに置き換えてください。

---

#### 作業2: FFmpegバイナリ管理の実装

**新規作成**: `livecap_core/resources/ffmpeg_manager.py`

```python
from pathlib import Path
import platform
import appdirs
import requests
import zipfile
import tarfile
from tqdm import tqdm

class FFmpegManager:
    """FFmpegバイナリ管理"""

    # プラットフォーム別のダウンロードURL
    # binary_path: 解凍後の実際のバイナリパス（サブフォルダを含む）
    FFMPEG_URLS = {
        'Windows': {
            'url': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
            'binary': 'ffmpeg.exe',
            'binary_path': 'ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe',  # ✨ サブフォルダ対応
        },
        'Linux': {
            'url': 'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz',
            'binary': 'ffmpeg',
            'binary_path': 'ffmpeg-*-amd64-static/ffmpeg',  # ✨ ワイルドカード対応
        },
        'Darwin': {  # macOS
            'url': 'https://evermeet.cx/ffmpeg/ffmpeg-latest.zip',
            'binary': 'ffmpeg',
            'binary_path': 'ffmpeg',  # ✨ 直接配置される場合
        }
    }

    @staticmethod
    def get_ffmpeg_dir() -> Path:
        """FFmpegディレクトリを取得"""
        cache_dir = Path(appdirs.user_cache_dir("livecap-core", "PineLab"))
        ffmpeg_dir = cache_dir / "ffmpeg"
        ffmpeg_dir.mkdir(parents=True, exist_ok=True)
        return ffmpeg_dir

    @staticmethod
    def get_ffmpeg_binary() -> Path:
        """
        FFmpegバイナリパスを取得（必要に応じてダウンロード）

        Returns:
            Path: FFmpegバイナリパス

        Raises:
            RuntimeError: ダウンロード失敗
        """
        system = platform.system()
        if system not in FFmpegManager.FFMPEG_URLS:
            raise RuntimeError(f"Unsupported platform: {system}")

        ffmpeg_dir = FFmpegManager.get_ffmpeg_dir()
        binary_path_pattern = FFmpegManager.FFMPEG_URLS[system]['binary_path']

        # 既に存在するか確認（ワイルドカード対応）
        existing_binary = FFmpegManager._find_binary_in_directory(ffmpeg_dir, binary_path_pattern)
        if existing_binary:
            return existing_binary

        # ダウンロード＆解凍
        FFmpegManager._download_ffmpeg(system, ffmpeg_dir)

        # 解凍後にバイナリを探す
        binary_path = FFmpegManager._find_binary_in_directory(ffmpeg_dir, binary_path_pattern)
        if not binary_path:
            raise RuntimeError(f"FFmpeg binary not found after download: {binary_path_pattern}")

        # 実行権限を付与（Linux/macOS）
        if system in ['Linux', 'Darwin']:
            binary_path.chmod(0o755)

        return binary_path

    @staticmethod
    def _find_binary_in_directory(base_dir: Path, pattern: str) -> Path | None:
        """
        ディレクトリ内でバイナリファイルを検索（ワイルドカード対応）

        Args:
            base_dir: 検索ベースディレクトリ
            pattern: バイナリパスパターン（例: 'ffmpeg-*-amd64-static/ffmpeg'）

        Returns:
            Path: 見つかったバイナリパス（見つからない場合はNone）
        """
        import glob

        # ワイルドカードを含むパターンをglobで展開
        search_pattern = str(base_dir / pattern)
        matches = glob.glob(search_pattern)

        if matches:
            # 最初にマッチしたファイルを返す
            binary_path = Path(matches[0])
            if binary_path.is_file():
                return binary_path

        return None

    @staticmethod
    def _download_ffmpeg(system: str, dest_dir: Path):
        """FFmpegをダウンロード"""
        url = FFmpegManager.FFMPEG_URLS[system]['url']

        print(f"Downloading FFmpeg for {system}...")

        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))

        # 一時ファイルにダウンロード
        archive_path = dest_dir / Path(url).name

        with open(archive_path, 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

        # 解凍
        print("Extracting FFmpeg...")
        if archive_path.suffix == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(dest_dir)
        elif archive_path.suffix in ['.tar', '.xz']:
            with tarfile.open(archive_path, 'r:*') as tar_ref:
                tar_ref.extractall(dest_dir)

        # アーカイブ削除
        archive_path.unlink()

        print(f"FFmpeg installed successfully: {dest_dir}")
```

#### 作業3: パッケージリソースの管理

**新規作成**: `livecap_core/resources/__init__.py`

```python
"""
リソース管理モジュール

モデルファイル、FFmpegバイナリなどの外部リソースを管理します。
すべてのリソースは XDG Base Directory 仕様に準拠したキャッシュディレクトリに配置されます。
"""

from .model_manager import ModelManager
from .ffmpeg_manager import FFmpegManager

__all__ = ['ModelManager', 'FFmpegManager']

def get_resource_info() -> dict:
    """
    リソース情報を取得

    Returns:
        dict: リソース情報
            - cache_dir: キャッシュディレクトリ
            - cached_models: キャッシュ済みモデル一覧
            - ffmpeg_installed: FFmpegインストール状態
    """
    return {
        'cache_dir': str(ModelManager.get_cache_dir()),
        'cached_models': ModelManager.list_cached_models(),
        'ffmpeg_installed': FFmpegManager.get_ffmpeg_dir().exists(),
    }
```

#### 作業4: 既存コードの修正

**修正対象**:
- `src/utils/__init__.py` - `sys.path`書き換えを削除
- `src/engines/*.py` - モデルパス参照をModelManagerに変更
- `src/audio/*.py` - FFmpegパス参照をFFmpegManagerに変更

**修正例** (`src/engines/reazonspeech_engine.py`):

**Before**:
```python
# 相対パスでモデル参照
model_path = Path(__file__).parent.parent.parent / "models" / "reazonspeech-k2-v2.onnx"
```

**After**:
```python
from livecap_core.resources import ModelManager

# ModelManager経由で取得（自動ダウンロード）
model_path = ModelManager.get_model_path('reazonspeech-k2-v2')
```

#### 成果物

- [ ] `livecap_core/resources/model_manager.py` - モデル管理
- [ ] `livecap_core/resources/ffmpeg_manager.py` - FFmpeg管理
- [ ] 既存エンジンのリファクタリング（ModelManager使用）
- [ ] 単体テスト（キャッシュディレクトリ動作確認）

---

## 成功基準

### Phase 0全体の成功基準

- [ ] **Qt非依存化**: Core層のすべてのコードからPySide6インポートがゼロ
- [ ] **設定ファイルレス**: Core層が辞書データのみで初期化可能
- [ ] **リソース自己完結**: `pip install livecap-core`のみで動作（モデルは初回自動DL）

### 検証方法

#### 1. Qt非依存の検証

```bash
# Coreパッケージをインストール
pip install livecap-core

# PySide6をアンインストール
pip uninstall PySide6 -y

# Core診断CLIを実行（エラーが出ないこと）
python -m livecap_core --as-json
```

#### 2. 設定ファイルレスの検証

```python
# YAMLファイルなしで動作することを確認
from livecap_core import LiveTranscriber
from livecap_core.config.defaults import get_default_config

config = get_default_config()
config['transcription']['engine'] = 'reazonspeech'

transcriber = LiveTranscriber(config=config)
# → エラーなく初期化できること
```

#### 3. リソース自己完結の検証

```bash
# 新規環境でテスト
python -m venv test_env
source test_env/bin/activate

# Coreのみインストール
pip install livecap-core

# Core診断CLI（FFmpegチェック込み）
python -m livecap_core --ensure-ffmpeg
# → モデルが自動ダウンロードされること
# → キャッシュディレクトリにモデルが配置されること
```

#### 実施済み検証ログ（2025-10-28 時点）
- `uv run pytest tests/core tests/transcription`
- `PYTHONPATH=src uv run python - <<'PY' ... process_file('/home/shojo-hakase/Videos/obs/2025-07-19 23-13-06.mkv') ... PY`
- GUI ファイルモード手動確認（Qt アダプタで進捗・完了イベントを受信、Windows/Linux 両環境で FFmpeg 自動取得を再検証予定）

---

## Phase 0完了後の状態

### Core層の依存関係

```
livecap-core
├── 依存ライブラリ
│   ├── numpy
│   ├── torch
│   ├── sounddevice
│   ├── appdirs        # キャッシュディレクトリ管理
│   ├── requests       # モデルダウンロード
│   └── tqdm           # ダウンロード進捗表示
│
└── 依存しない
    ├── PySide6        ❌ Qt依存なし
    ├── YAML ファイル  ❌ 設定ファイル非依存
    └── 翻訳ファイル   ❌ 翻訳システム非依存
```

### ディレクトリ構造（予定）

```
livecap-core/
├── livecap_core/
│   ├── __init__.py
│   ├── config/
│   │   ├── defaults.py       # デフォルト設定定数
│   │   └── validator.py      # 設定バリデーション
│   ├── resources/
│   │   ├── model_manager.py  # モデル管理
│   │   └── ffmpeg_manager.py # FFmpeg管理
│   ├── engines/
│   │   ├── engine_factory.py # 翻訳非依存ファクトリ
│   │   └── *.py
│   ├── transcription/
│   │   ├── worker.py         # Qt非依存ワーカー
│   │   └── live_transcriber.py
│   └── ...
│
├── tests/
│   └── test_*.py             # Qt環境不要のテスト
│
└── setup.py
```

---

## 次のステップ

Phase 0完了後、以下のPhaseに進むことができます：

| Phase | 期間 | 前提条件 |
|-------|------|---------|
| **Phase 0** | **2-3週間** | **なし** ← 今ここ |
| Phase 1 | 2-3週間 | Phase 0完了 ✅ |
| Phase 2 | 1-2ヶ月 | Phase 1完了 |
| Phase 3 | 1ヶ月 | Phase 2完了 |
| Phase 4 | 1ヶ月 | Phase 3完了 |

**Phase 0完了の確認事項**:
- [ ] すべての成果物が完成
- [ ] 成功基準をすべて満たす
- [ ] 単体テストが全てパス
- [ ] ドキュメント更新完了

---

## 関連ドキュメント

- [Core分離提案](./core-separation-proposal.md)
- [GitHub Issue #91](https://github.com/Mega-Gorilla/Live_Cap_v3/issues/91)

---

**Phase 0の完了により、LiveCap Coreは真の意味で「独立したPyPIパッケージ」として配布可能になります。**
