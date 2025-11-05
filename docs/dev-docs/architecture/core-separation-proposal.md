# LiveCap Core分離提案

**作成日**: 2025-10-26
**ステータス**: 提案中
**対象バージョン**: v3.0.0以降

---

## 📋 目次

1. [背景と課題](#背景と課題)
2. [提案内容](#提案内容)
3. [調査結果](#調査結果)
4. [分離のメリット](#分離のメリット)
5. [想定される課題と対策](#想定される課題と対策)
6. [実装計画](#実装計画)
7. [リスク評価](#リスク評価)

---

## 背景と課題

### 現状の問題

LiveCapは現在、約40,726行のコードベースを持つモノリシックなアプリケーションです。

**主な課題**:
1. **コード管理の複雑化**
   - GUI、STT、翻訳、字幕配信が一体化
   - バグ修正時の影響範囲が不明確
   - テストが困難（GUI依存）

2. **保守性の低下**
   - 40,000行超のコードベース
   - 責務の境界が曖昧
   - リファクタリングのリスクが高い

3. **再利用性の欠如**
   - STT機能を他のプロジェクトで使いたくても、GUI全体が必要
   - CLI版やBot版の開発が困難

4. **コミュニティ貢献の障壁**
   - エンジン開発者がGUIの知識も必要
   - PRレビューが複雑（全体への影響を考慮）

---

## 提案内容

### コンセプト

**LiveCap CoreとしてSTT機能を独立したパッケージに分離**

```
┌─────────────────────────────────────┐
│  LiveCap (GUI Application)          │
│  - PySide6 UI                       │
│  - WebSocket字幕配信                │
│  - OBS/VRChat統合                   │
│  - Steam配布                        │
└──────────┬──────────────────────────┘
           │ pip install livecap-core
┌──────────▼──────────────────────────┐
│  LiveCap Core (PyPI Package)        │
│  - 6種類のASRエンジン               │
│  - 音声処理・VAD                    │
│  - 翻訳機能（Google/Riva） ✨       │
│  - live/fileモード                  │
│  - 設定管理                         │
└─────────────────────────────────────┘
```

### 分離対象

#### LiveCap Core（約20,390行）

```
livecap-core/
├── livecap_core/
│   ├── engines/               (4,532行) - ASRエンジン
│   │   ├── base_engine.py
│   │   ├── reazonspeech_engine.py
│   │   ├── parakeet_engine.py
│   │   ├── canary_engine.py
│   │   ├── whispers2t_engine.py
│   │   ├── voxtral_engine.py
│   │   └── kotoba_whisper_engine.py
│   ├── audio/                 (4,969行) - 音声処理
│   │   ├── multi_source.py
│   │   ├── device_manager.py
│   │   └── processors/
│   ├── vad/                   (2,227行) - 音声検出
│   │   ├── tenvad_wrapper.py
│   │   └── vad_state_machine.py
│   ├── transcription/         (1,849行) - Transcriber
│   │   ├── live_transcribe.py
│   │   └── file_transcribe.py
│   ├── translation/           (2,007行) - 翻訳 ✨
│   │   ├── translator.py
│   │   └── backends/
│   │       ├── google_backend.py    # 軽量（deep-translator）
│   │       └── riva_backend.py      # GPU版（NVIDIA Riva）
│   ├── config/                (~300行) - 設定管理 🔄
│   │   ├── defaults.py        # デフォルト設定（辞書定数）
│   │   └── validator.py       # 設定バリデーション
│   └── core/                  - 共通定義
│       ├── languages.py
│       └── transcription_types.py
├── tests/                     - 単体テスト
├── docs/                      - APIドキュメント
├── setup.py
└── README.md
```

#### LiveCap GUI（約20,710行）

```
livecap/
├── src/
│   ├── gui/                   (19,853行) - UI
│   ├── websocket/             - 字幕配信
│   ├── osc/                   - VRChat統合
│   ├── config/                (~710行) - 設定ファイル管理 🔄
│   │   ├── config_loader.py   # YAML読み込み・統合
│   │   └── defaults.yaml      # GUI設定デフォルト
│   └── gui_main.py
├── requirements.txt           # livecap-core依存
└── pyinstaller_build.py
```

---

## 調査結果

### コードベース分析

| 領域 | 行数 | 割合 | 分類 |
|------|------|------|------|
| GUI | 19,853行 | 48.7% | GUI層 |
| 音声処理 | 4,969行 | 12.2% | Core |
| ASRエンジン | 4,532行 | 11.1% | Core |
| VAD | 2,227行 | 5.5% | Core |
| 翻訳 | 2,007行 | 4.9% | **Core** ✨ |
| コアエンジン | 1,849行 | 4.5% | Core |
| 設定・言語 | 1,441行 | 3.5% | 分割 🔄 |
| WebSocket | ~500行 | 1.2% | GUI層 |
| その他 | 1,848行 | 4.6% | 両方 |

**設定管理の詳細**:
- `config_loader.py` (710行) → GUI層（YAML読み込み）
- `defaults.py` (200行) → Core（デフォルト設定定数）
- `validator.py` (100行) → Core（設定バリデーション）

**Core候補**: 20,390行（50%）
**GUI候補**: 20,710行（50%）

### アーキテクチャ評価

#### ✅ 分離に有利な点

1. **単方向依存**
   ```
   GUI → Core（依存）
   Core ← GUI（依存なし）
   ```

2. **循環依存なし**
   - 明確な層構造
   - Core層はGUIを知らない

3. **インターフェース確立済み**
   - `BaseEngine` - エンジン統一
   - `VADWrapper` - VAD抽象化
   - `LiveTranscriber` - 公開API

4. **疎結合**
   - ファクトリーパターン
   - 設定ベース初期化

#### ⚠️ 注意が必要な点

1. **設定管理の複雑さ**
   - `config.yaml`が大きい
   - Core/GUI設定の分離が必要

2. **依存ライブラリの重複**
   - `torch`, `sounddevice`等
   - PyPIパッケージサイズが大きくなる

3. **モデルファイル管理**
   - 各エンジンのモデル（数GB）
   - ダウンロード機構の再設計

---

## 分離のメリット

### 1. 開発・保守の効率化

| 項目 | Before（モノリス） | After（分離） |
|------|------------------|--------------|
| **バグ修正範囲** | 40,726行全体を考慮 | Core: 18,800行のみ |
| **テスト** | GUI込みで複雑 | Core単体テスト可能 |
| **CI/CD** | 遅い（GUI依存） | 高速（Coreのみ） |
| **リリース** | 一体化 | Core/GUI独立 |
| **影響範囲分析** | 困難 | 明確（API境界） |

### 2. 再利用性の向上

LiveCap Coreを使える新プロジェクト：

```python
# CLI版LiveCap（STT + 翻訳統合）- 設定ファイルレス設計 ✨
from livecap_core import LiveTranscriber
from livecap_core.translation import TranslationService
from livecap_core.config.defaults import get_default_config

# 辞書データで設定を渡す
config = get_default_config()
config['transcription']['engine'] = 'reazonspeech'
config['transcription']['input_language'] = 'ja'

transcriber = LiveTranscriber(config=config)
translator = TranslationService(
    service='google',
    source_lang='ja',
    target_lang='en',
    config=config
)

def on_transcription(text):
    translated = translator.translate(text)
    print(f"[JA] {text}")
    print(f"[EN] {translated}")

transcriber.start_transcription(callback=on_transcription)

# Discord Bot（多言語対応）- 最小設定で起動
config = {
    'transcription': {
        'engine': 'parakeet',
        'input_language': 'en',
    },
    'audio': {
        'sample_rate': 16000,
    }
}

transcriber = LiveTranscriber(config=config)
translator = TranslationService(service='google', source_lang='en', target_lang='ja')

@bot.event
async def on_voice_state_update(member, before, after):
    audio = await voice_client.record()
    text = transcriber.transcribe(audio)
    translated = translator.translate(text)
    await channel.send(f"{text}\n→ {translated}")

# Podcast自動文字起こし（環境変数から設定）
import os
from livecap_core import FileTranscriber

config = {
    'transcription': {
        'engine': os.getenv('ASR_ENGINE', 'whispers2t_base'),
        'input_language': os.getenv('INPUT_LANG', 'en'),
    }
}

file_transcriber = FileTranscriber(config=config)
result = file_transcriber.transcribe_file("podcast.mp3")
```

### 3. コミュニティ貢献の促進

| 貢献タイプ | Before | After |
|-----------|--------|-------|
| **エンジン開発** | GUI知識必要 | Core知識のみ |
| **UI改善** | STT理解必要 | GUI知識のみ |
| **PRレビュー** | 全体への影響考慮 | 担当領域のみ |
| **Issue切り分け** | 曖昧 | Core/GUI明確 |

### 4. 配布戦略の柔軟性

```bash
# 開発者向け: pip経由（軽量、依存管理簡単）
pip install livecap-core

# エンドユーザー向け: Steam/実行ファイル
# Windows: .exe (PyInstaller)
# Linux: AppImage（将来）
# macOS: .app（将来）
```

### 5. テスタビリティの向上

```python
# Core単体テスト（GUI不要）
def test_reazonspeech_engine():
    engine = create_engine('reazonspeech', config)
    audio = load_test_audio("test.wav")
    result = engine.transcribe(audio)
    assert "こんにちは" in result

# 高速CI/CD
# - Coreテスト: 5分
# - GUIテスト: 15分（分離実行）
```

---

## 想定される課題と対策

### 課題1: 翻訳機能の位置づけ

**問題**: 翻訳はCoreに含めるべきか？

**結論**: ✅ Coreに含める

**理由**:

1. **GPUメモリ管理の統合が必須**
   - NVIDIA Riva翻訳は4.5GBモデル（`nvidia/Riva-Translate-4B-Instruct`）を使用
   - ASRエンジンとGPUメモリを共有する必要がある
   - Core層で一元管理しないとGPUメモリ競合・OOMリスクが高い
   - 現在の実装（`src/translation/backends/riva_backend.py:164-189`）:
     ```python
     if self.device.type == 'cuda':
         from utils.gpu_memory import check_memory_for_model, get_gpu_memory_info

         # ASR用に予約するメモリ量を設定から取得
         reserve_gb = self.config.get('translation', {}).get(
             'riva_settings', {}
         ).get('reserve_memory_gb', 2.0)

         can_use_gpu, message = check_memory_for_model('riva', reserve_gb)

         if not can_use_gpu:
             logger.warning(f"Insufficient GPU memory, falling back to CPU: {message}")
             self.device = torch.device('cpu')
     ```

2. **torch依存は既にCore層に存在**
   - 多くのASRエンジンがPyTorchを使用（Parakeet、Canary、Whisper、Voxtral等）
   - 翻訳だけ分離しても依存削減にならない
   - むしろGPU管理の分散化で複雑性が増す

3. **バックエンド統一設計**
   - Google翻訳（軽量、Webスクレイピング）とRiva翻訳（GPU）の両方をサポート
   - バックエンド切り替えロジックが統一されている
   - 分離すると設計の一貫性が失われる

4. **再利用性の向上**
   - CLI版やBot版でもRiva翻訳を使いたいニーズがある
   - STT+翻訳の一貫したパイプラインを提供できる
   - GPU管理を含めて再利用可能

**対応**: オプショナル依存でパッケージサイズ問題を解決

```python
# setup.py
setup(
    name="livecap-core",
    install_requires=[
        "sounddevice",
        "numpy",
        "torch",  # ASR用に既に必須
    ],
    extras_require={
        # 翻訳バックエンド別
        "translation-google": [
            "deep-translator>=1.11.4",  # Apache License 2.0
        ],
        "translation-riva": [
            "transformers>=4.30.0",
            "sentencepiece",
        ],

        # エンジン別
        "reazonspeech": [...],
        "parakeet": [...],

        # 全部入り
        "all": [
            # 全依存を含む
        ],
    }
)
```

**インストール例**:
```bash
# Google翻訳のみ（軽量）
pip install livecap-core[translation-google]

# Riva翻訳（GPU使用）
pip install livecap-core[translation-riva]

# 翻訳なし（STT特化）
pip install livecap-core
```

**使用例**:
```python
# Core: STT + 翻訳の統合パイプライン
from livecap_core import LiveTranscriber
from livecap_core.translation import TranslationService

transcriber = LiveTranscriber(config)
translator = TranslationService(
    service='riva',  # or 'google'
    source_lang='ja',
    target_lang='en',
    config=config
)

# GPU管理は内部で統合されている
def on_transcription(text):
    translated = translator.translate(text)
    print(f"Original: {text}")
    print(f"Translated: {translated}")

transcriber.start_transcription(callback=on_transcription)
```

### 課題2: WebSocket/字幕配信の位置づけ

**問題**: 字幕出力はCoreの責務か？

**結論**: ❌ Coreには含めない

**理由**:
- 字幕出力は「配信方法」の話（STTではない）
- OBS/VRChat統合はGUI層の責任

**対応**:
```python
# Core: コールバック提供のみ
def on_transcription_update(text):
    print(f"Transcribed: {text}")

transcriber = LiveTranscriber(config, callback=on_transcription_update)

# GUI: 字幕配信実装
class SubtitleManager:
    def __init__(self, transcriber):
        transcriber.callback = self.send_subtitle

    def send_subtitle(self, text):
        websocket_server.broadcast(text)
```

### 課題3: 設定管理の分離

**問題**: `config.yaml`が複雑（Core/GUI混在）、設定ファイルに依存するとモジュール性が損なわれる

**結論**: ✅ 設定ファイルレス設計を採用

**理由**:
1. **モジュール性の向上**: Coreは純粋なPythonオブジェクトのみに依存
2. **柔軟性**: 設定の供給元を選ばない（YAML、JSON、環境変数、DB等）
3. **シンプル**: 設定ファイル読み込みはGUI層の責務

**対応**:

```python
# Core: 辞書データで設定を受け取る
from livecap_core import LiveTranscriber
from livecap_core.config.defaults import get_default_config

# デフォルト設定を取得
config = get_default_config()

# 必要に応じてカスタマイズ
config['transcription']['engine'] = 'reazonspeech'
config['transcription']['input_language'] = 'ja'
config['translation']['service'] = 'google'

transcriber = LiveTranscriber(config=config)

# GUI: YAMLファイルを読み込んで辞書に変換
from livecap_core.config.defaults import get_default_config
from livecap.config import ConfigLoader
import yaml

# ファイルから読み込み
with open('config.yaml') as f:
    user_config = yaml.safe_load(f)

# デフォルト設定とマージ
config = get_default_config()
config.update(user_config)

# GUI設定を追加
config['subtitle'] = user_config.get('subtitle', {})
config['gui'] = user_config.get('gui', {})

# Coreに辞書として渡す
transcriber = LiveTranscriber(config=config)
```

**設定の配置**:
- `livecap-core/config/defaults.py`: デフォルト設定定数（辞書）
- `livecap-core/config/validator.py`: 設定バリデーション
- `livecap/config/config_loader.py`: YAML読み込み（GUI層）

### 課題4: モデルファイル管理

**問題**: 各エンジンのモデル（数GB）をどう配布するか？

**対応**: オンデマンドダウンロード

```python
# 初回起動時に自動ダウンロード
from livecap_core import create_engine

engine = create_engine('reazonspeech', config)
# ↓ モデル未ダウンロードなら自動取得
# Downloading model: reazonspeech-k2-v2 (600MB)...
```

### 課題5: 依存ライブラリの重複

**問題**: torch, sounddevice等の大きな依存

**対応**: エンジン別オプション依存

```bash
# 最小インストール（依存なし）
pip install livecap-core

# ReazonSpeech使用
pip install livecap-core[reazonspeech]

# 全エンジン
pip install livecap-core[all]
```

---

## 実装計画

### ⚠️ 重要: Phase 0の必要性

Core分離を実施する前に、**Phase 0（前提条件整備）が必須**です。

**理由**: 現状のコード構造では以下の問題があり、「pip install livecap-core だけで動作する」パッケージとして成立しません：

1. **Qt依存が残っている** (`file_transcriber.py:71`)
2. **設定・翻訳への直参照** (`engine_factory.py:8, 15`)
3. **リソース解決が脆弱** (`sys.path`書き換え、相対パス依存)

詳細は [Phase 0ドキュメント](./phase0-prerequisites.md) を参照してください。

---

### Phase 0: 前提条件整備（2-3週間） 🔧 NEW

**Phase 1の前に完了必須**

#### Phase 0.1: Qt非依存のAPI化（1週間）

- [ ] TranscriptionWorkerをコールバックベースに変更
- [ ] LiveTranscriberのQt Signal依存を除去
- [ ] GUI側にQtアダプタパターンを実装
- [ ] Core層からPySide6インポートを完全除去

**成果物**:
- `livecap_core/transcription/worker.py` - Qt非依存
- `livecap/gui/adapters/qt_transcription_adapter.py` - Qtアダプタ

#### Phase 0.2: 設定・翻訳の境界整理（1週間）

- [ ] engine_factoryから翻訳・config_loader依存を除去
- [ ] config/defaults.pyを作成（デフォルト設定定数）
- [ ] config/validator.pyを作成（設定バリデーション）
- [ ] GUI層でYAML読み込み → 辞書変換

**成果物**:
- `livecap_core/config/defaults.py` - デフォルト設定
- `livecap_core/config/validator.py` - バリデーション
- `livecap_core/engines/engine_factory.py` - 翻訳非依存

#### Phase 0.3: リソース解決の再設計（1週間）

- [ ] ModelManagerを実装（モデル自動ダウンロード）
- [ ] FFmpegManagerを実装（バイナリ自動ダウンロード）
- [ ] sys.path書き換えを削除
- [ ] importlib.resources + appdirs に移行
- [ ] XDG Base Directory仕様準拠のキャッシュディレクトリ

**成果物**:
- `livecap_core/resources/model_manager.py` - モデル管理
- `livecap_core/resources/ffmpeg_manager.py` - FFmpeg管理

#### Phase 0の成功基準

- [ ] Core層からPySide6インポートがゼロ
- [ ] Core層が辞書データのみで初期化可能
- [ ] `pip install livecap-core`のみで動作（モデルは初回自動DL）

---

### Phase 1: アーキテクチャ設計（2-3週間）

**前提条件**: Phase 0完了 ✅

- [ ] LiveCap Coreのパッケージ構造設計
- [ ] 公開APIの明確化（`__init__.py`）
- [ ] 依存関係の整理（requirements分離）
- [ ] 設定スキーマの分離（core/gui）

**成果物**:
- `docs/dev-docs/architecture/core-api-spec.md`
- `livecap-core/setup.py`（草案）
- `livecap-core/requirements.txt`

### Phase 2: Core分離実装（1-2ヶ月）

- [ ] 新しいリポジトリ作成（`livecap-core`）
- [ ] Core部分のコピー＋リファクタリング
- [ ] 公開API実装（`LiveTranscriber`, `FileTranscriber`）
- [ ] 単体テスト作成（pytest、カバレッジ80%以上）
- [ ] ドキュメント作成（Sphinx）

**成果物**:
- `livecap-core` リポジトリ
- 単体テスト群
- API ドキュメント

### Phase 3: GUI側の統合（1ヶ月）

- [ ] LiveCap GUIを`livecap-core`依存に変更
- [ ] 翻訳・字幕機能をGUI層に移動
- [ ] 統合テスト
- [ ] 動作確認（Windows/Linux/macOS）

**成果物**:
- 更新された`livecap`（GUI版）
- 統合テストスイート

### Phase 4: 公開準備（1ヶ月）

- [ ] PyPI登録（`livecap-core`）
- [ ] GitHub Actions（CI/CD）
- [ ] ドキュメントサイト構築（Read the Docs）
- [ ] サンプルプロジェクト作成

**成果物**:
- PyPI: `livecap-core` v1.0.0
- ドキュメントサイト
- サンプルコード集

---

## 推奨スケジュール

### 実装スケジュール

| 時期 | Phase | 作業内容 |
|------|-------|---------|
| **2026年Q1** | **Phase 0** | **前提条件整備** 🔧 NEW |
|  | Phase 0.1 | Qt非依存のAPI化 |
|  | Phase 0.2 | 設定・翻訳の境界整理 |
|  | Phase 0.3 | リソース解決の再設計 |
| **2026年Q2** | Phase 1 | Core分離設計 |
| **2026年Q3** | Phase 2 | Core実装 |
| **2026年Q4** | Phase 3 | GUI統合 |
| **2027年Q1** | Phase 4 | PyPI公開 |

**実装期間**: 約9-12ヶ月（Phase 0から公開まで）

### スケジュールの前提

1. **Phase 0が最優先**: Core分離の成否を左右する重要な前提条件
2. **設計フェーズの重要性**: API設計ミスを防ぐため十分な期間を確保
3. **段階的実装**: Core部分から順次リファクタリング
4. **テスト充実**: 各Phaseで包括的なテストを実施

---

## リスク評価

### 高リスク

| リスク | 影響 | 確率 | 対策 |
|--------|------|------|------|
| **Core API設計ミス** | 大 | 中 | 入念な設計フェーズ、プロトタイプ検証 |
| **パフォーマンス劣化** | 中 | 低 | ベンチマーク、プロファイリング |
| **既存機能の破壊** | 大 | 中 | 包括的な統合テスト |

### 中リスク

| リスク | 影響 | 確率 | 対策 |
|--------|------|------|------|
| **依存関係の複雑化** | 中 | 中 | 依存グラフの可視化、ドキュメント化 |
| **モデル配布の問題** | 中 | 中 | CDN活用、ミラーサーバー |
| **設定互換性** | 小 | 高 | マイグレーションスクリプト |

### 低リスク

| リスク | 影響 | 確率 | 対策 |
|--------|------|------|------|
| **PyPI登録の失敗** | 小 | 低 | 事前テスト（TestPyPI） |
| **ドキュメント不足** | 小 | 中 | 段階的に充実 |

---

## 評価指標

### 成功基準

- [ ] Core単体でCI/CD実行時間 < 5分
- [ ] Core単体テストカバレッジ > 80%
- [ ] サンプルプロジェクト > 3個作成

### KPI

| 指標 | 目標値 | 測定方法 |
|------|--------|---------|
| **バグ修正速度** | 50%向上 | Issue平均解決時間 |
| **テスト実行時間** | 30%短縮 | CI/CD実行時間 |
| **コード再利用** | 3プロジェクト以上 | サンプルプロジェクト数 |
| **開発効率** | 影響範囲の明確化 | 変更ファイル数削減 |

---

## 参考資料

### 類似プロジェクトの分離事例

1. **Flask** (Web Framework)
   - Core: `werkzeug`, `jinja2`
   - Framework: `flask`

2. **TensorFlow**
   - Core: `tensorflow-core`
   - Full: `tensorflow` (with GPU support)

3. **Whisper**
   - Core: `openai-whisper`
   - Wrappers: `faster-whisper`, `whisper-timestamped`

### 技術スタック

- **パッケージング**: setuptools, wheel
- **テスト**: pytest, pytest-cov
- **ドキュメント**: Sphinx, Read the Docs
- **CI/CD**: GitHub Actions
- **配布**: PyPI, TestPyPI

---

## 改訂履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2025-10-26 | 1.0 | 初版作成 |
| 2025-10-26 | 1.1 | **翻訳機能をCoreに含める方針に変更**（GPU管理統合のため） |
| 2025-10-26 | 1.2 | **設定ファイルレス設計を採用**（モジュール性向上のため）<br>- Core: 辞書データで設定を受け取る<br>- `config_loader.py`（710行）をGUI層に配置<br>- Core: `defaults.py` + `validator.py`（~300行）のみ<br>- Core候補: 20,390行（50%） |
| 2025-10-26 | 1.3 | **Phase 0（前提条件整備）を追加**（実装懸念点への対応）<br>- Qt非依存のAPI化<br>- 設定・翻訳の境界整理<br>- リソース解決の再設計<br>- スケジュール: 9-12ヶ月（Phase 0含む） |

---

## 関連ドキュメント

- **[Phase 0: 前提条件整備](./phase0-prerequisites.md)** ← 必読！
- コードベース分析結果（本提案書内）
- GitHub Issue: [#91 LiveCap Coreとしてのパッケージ分離](https://github.com/Mega-Gorilla/Live_Cap_v3/issues/91)
