# LiveCap Core Configuration Boundary Proposal

> **Status:** Phase 1 draft  
> **Related issues:** #91 (Phase 0 archive), #105 (Phase 1 kickoff)

## 1. Background
- Phase 0 で `livecap_core/config/defaults.py` と `validator.py` を導入し、GUI 側 YAML に依存しない起動を実現した。  
- Phase 1 では Core パッケージと GUI アプリの責務境界を明確にし、設定スキーマの分離と配布形態を定義する必要がある。  
- 現状の `DEFAULT_CONFIG` は GUI 向けパラメータも含んでおり、Core-only デプロイ時に不要な項目まで抱えている。

## 2. Goal
1. Core パッケージが必須とする設定キーの最小集合を定義する。  
2. GUI 固有の設定（例: 多言語 UI、OBS/VRChat 連携、GUI 表示設定）を別スキーマとして切り出す。  
3. YAML などファイルフォーマットのロード責務を GUI / アプリ層に限定し、Core は辞書を受け取る API に統一する。

## 3. Current State Audit

| Section | 主なキー | Core 依存 | GUI 依存 | 備考 |
| --- | --- | --- | --- | --- |
| `audio` | `sample_rate`, `chunk_duration`, `input_device` | ✅ | △ (入力デバイス選択 UI) | Core が直接使用。GUI は候補一覧を表示。 |
| `multi_source` | VAD/ノイズゲート既定値、`sources` | ✅ | ✅ | Core のマルチソース処理。GUI はフォームで編集。 |
| `silence_detection` | VAD 関連閾値 | ✅ | ❌ | Core のファイル/ライブ両モードで利用。 |
| `transcription` | `engine`, `language_engines`, engine 個別設定 | ✅ | ✅ (UI で編集) | Core で実際に参照。GUI はプリセット管理。 |
| `translation` | `enabled`, `service`, `target_language`, `riva_settings` | ✅ (Core translation pipeline) | ✅ (UI) | Core では将来的に optional。 |
| `engines` | モデル名等 | ✅ | ❌ | Core 側エンジン初期化に使用。 |
| `logging` / `queue` / `debug` | ログ出力先, デバッグフラグ | ✅ | ✅ | Core が実際のロギングに使用。GUI は設定 UI を持つ。 |
| `file_mode` | VAD 使用有無など | ✅ | ❌ | Core の FileTranscriptionPipeline が使用。 |

### 観察
- Core 必須の設定群と、UI 表示/選択用のメタデータが同居している。  
- Validator は最小限（`audio.sample_rate` 等）しか検証しておらず、より詳細な型チェックが Phase 1 で必要。

## 4. Proposed Separation

### 4.1 Core Schema (`core_config`)
- **必須セクション**: `audio`, `transcription`, `engines`, `silence_detection`, `multi_source`, `file_mode`, `queue`。  
- **Optional**: `translation`（翻訳機能を使う場合のみ）、`logging`, `debug`.  
- **型**: `TypedDict` を導入し、`ConfigValidator` は typed schema に基づくバリデーションへ拡張。  
- **ロード方針**: Core は辞書/JSON のみ受け取る。ファイル I/O は呼び出し側責務。

### 4.2 GUI Schema (`gui_config`)
- **責務**: UI 表記、テーマ、ウィンドウ位置、OBS/VRChat 接続情報、言語切り替え、ショートカット設定など。  
- **変換**: GUI が YAML → dict へロードし、Core 用キーのみ `core_config` にマッピング。  
- **相互作用**: GUI 設定の一部は Core に派生値を渡す（例: 入力デバイス ID → `audio.input_device`）。

### 4.3 Shared Metadata
- **例**: 言語一覧、エンジンプリセット、翻訳ターゲット候補など。  
- **置き場**: `livecap_core/languages.py` や `config/presets.py`（新設）に移し、UI も Core も参照できる定数として管理。

### 4.4 Typed schema draft (`livecap_core/config/schema.py`)

`livecap_core/config/schema.py` に TypedDict 定義を配置し、Phase 1 の議論用リファレンスとしてコミット済み。

- `AudioConfig` / `MultiSourceConfig` / `TranslationConfig` などは Phase 0 の `DEFAULT_CONFIG` に含まれる追加フィールド（`processing`, `defaults`, `performance` 等）を許容するよう拡張している。  
- `TranscriptionConfig` は `language_engines` / `reazonspeech_config` のみを扱い、モデルごとの詳細はトップレベル `EnginesConfig` で管理する。  
- `EnginesConfig` を必須セクションとして含め、モデルプリセット定義（`engines.*`）も Phase 1 スキーマから参照可能とした。  
- Phase 1 では `Required` / `NotRequired` を併用して Core が必須とする最小キー（例: `audio.sample_rate`, `transcription.engine`, `transcription.input_language`）を TypedDict 上に明示した。  
- `multi_source.sources` は現行の GUI / Core 実装が dict を渡すため、Phase 1 では `Sequence | MutableMapping` の Union として扱い、両方の形を許容する。
- `ConfigValidator` は `CoreConfig` TypedDict を再帰的に走査し、必須キー欠落や型不一致（リテラル/Mapping/Sequence 含む）を `ValidationError(path, message)` として収集するよう更新済み。（2025-10-29）
- 未定義のキーが CoreConfig へ渡された場合は `ValidationError` を生成し、GUI/CLI どちらからでも Core 側に存在しない設定が紛れ込まないよう境界検証を行う。（2025-10-30）

### 4.5 GUI adapter flow (draft)

1. GUI が YAML / JSON をロードして柔軟な辞書 (`dict[str, Any]`) を得る。  
2. `gui.config.adapter.CoreConfigBuilder`（新規）でユーザー入力を正規化し、`CoreConfig` に準拠する構造体を生成。  
3. `ConfigValidator.validate(core_config)` を呼び出し、TypedDict に沿った詳細なエラーを取得。  
   - CoreConfig に定義されていないキーは `ValidationError(path, "Unexpected key …")` として弾かれる。  
   - 型不一致やリテラル不一致は `ValidationError(path, "Expected …")` で報告される。  
   - `multi_source.sources` は dict / sequence の両方を許容し、GUI アダプタ整備までは従来の dict 形を継続サポートする。  
4. GUI は `ValidationError` を捕捉し、フィールド名・期待値・実際値を含む国際化メッセージへ変換。  
5. 検証済み `core_config` を `livecap_core` API（`FileTranscriptionPipeline` 等）へ渡す。

### 4.6 Validation flow (Phase 1 implementation)

1. エントリーポイント（CLI/GUI）が設定辞書を構築する。  
2. `ConfigValidator.validate` を呼び出し、戻り値の `List[ValidationError]` を確認する。  
   - エラーが空のときは CoreConfig との適合が保証される。  
   - エラーが存在する場合、GUI はユーザー通知に変換し、CLI は `validate_or_raise` を利用して即時に `ValueError` を送出する。  
3. Core 層は検証済みの辞書のみを受け付けるため、GUI/CLI どちらの流路でも同一境界条件を維持できる。

補足:
- CLI など GUI 以外のエントリーポイントも `ConfigValidator.validate_or_raise` を通じて同一ロジックを共有し、ユーザー表示が不要なケースでは例外経由で失敗を伝える。  
- GUI アダプタは `DEFAULT_CONFIG` を基盤としつつ、`multi_source.sources` のように dict/sequence どちらの入力も許容できるよう事前正規化を担う。  

### 4.7 GUI adapter responsibilities (Phase 1 scope)

`gui.config.adapter.CoreConfigBuilder`（仮称）は、ユーザー設定（YAML/JSON）を CoreConfig に準拠する辞書へ変換する責務を持つ。Phase 1 では以下の項目を最小要件として扱い、実装計画をドキュメントで合意する。

1. **ロードとマージ**  
   - `config.yaml` / プロファイルごとの YAML を読み込み、GUI 固有セクションと Core セクションを分離する。  
   - Core 用ブロックは `livecap_core.config.defaults.DEFAULT_CONFIG` を基にマージし、欠損キーを補完する。
2. **正規化ルール**  
   - `multi_source.sources`: Phase 1 では辞書形式を維持しつつ、GUI 内部では ID ごとの設定辞書を引き続き利用する。将来の CLI/SDK 連携を見据え、`Sequence[MultiSourceInputConfig]` への変換ヘルパー (`normalize_sources_dict`) を用意し、ドキュメントに TODO として残す。  
   - `audio.input_device`: GUI で `None` か文字列 ID を返す。CLI 等でのデバイス選択フローと整合を取るため、型は `str | None` に統一する。  
   - `translation`: GUI 上の `enabled` / `service` / `target_language` のフィールド名を Core が期待するキー (`translation.enabled` 等) にマッピングする。  
   - フラットな GUI 設定（例: `subtitle.*`, `vrchat.*`）は `gui_config` に残し、CoreConfig に渡さない。
3. **バリデーションとエラーハンドリング**  
   - `ConfigValidator.validate(core_config)` の結果を GUI 用エラーオブジェクトへ変換し、入力フォームにフィードバックする。  
   - 型変換エラー（例: 文字列数値、bool 表現）はアダプタ側でキャッチし、可能であれば自動補正（`"true"` → `True` 等）を行う。
4. **将来の TODO / Phase 2 以降の検討事項**  
   - `multi_source.sources` をシーケンス形式へ統一し、Core/CLI/SDK が同一インターフェイスで扱えるよう移行ステップを定義する。  
   - GUI 設定と Core 設定の schema を個別ファイルに分離し、アダプタが双方の TypedDict を参照できる構成へ整理する。  
   - GUI 設定の保存フォーマット（YAML/JSON）のバージョニングを導入し、アダプタでマイグレーションを実装する。  
   - CLI 向けの簡易アダプタ（環境変数やコマンドライン上書き）を共有ユーティリティとして切り出す。

## 5. Migration Plan
1. **Schema 定義の明文化**: `core_config_schema.py`（仮）に TypedDict を定義し、生成関数 `build_core_config(raw_config)` を提供。  
2. **Validator 拡張**: 型検証と値範囲チェックを追加し、エラーメッセージを国際化対応できる形式に整理。  
3. **GUI アダプタ更新**:  
   - GUI 側で YAML → dict 変換後、`build_core_config` を呼び出して Core へ渡す。  
   - 不足キーや型エラーは GUI でユーザー向けエラーメッセージに変換。  
4. **Doctrine/Docs 更新**: README / Dev docs に設定境界図とフローを掲示。  
5. **互換保持**: 既存 YAML を破壊しないよう、Deprecated フィールドは Phase 2 で段階的に削除する。

## 6. Open Questions
- 翻訳設定 (`translation.*`) を Core に残すか、GUI や別サービス層へ完全に移譲するか。  
- Core の CLI サンプルで必要な設定セット（最低限何のキーが求められるか）をどこまで固定するか。  
- 複数プロファイル（例: CLI モード vs GUI モード）をサポートする際の設定ファイル構造。

- [x] `livecap_core/config/schema.py` に TypedDict ドラフトを追加し、`DEFAULT_CONFIG` の構造と同期する（`transcription` は `language_engines` / `reazonspeech_config` を中心に扱い、モデル個別設定はトップレベル `engines` で管理）。（2025-10-29 更新）
- [x] `ConfigValidator` を TypedDict ベースの検証に拡張し、具体的なエラーメッセージ仕様を整理する。（2025-10-29 更新）  
- GUI 側 YAML ローダー→Core config 変換フローを `gui.config.adapter` モジュール案として設計メモ化し、Issue #105 に添付する。  
- Phase 2 での移行ステップ（Deprecated フィールドの削除、GUI 設定の専用ファイル化）をバックログに追加し、互換モードの廃止条件を明文化する。
