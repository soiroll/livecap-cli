# Phase 1: アーキテクチャ設計計画

## 目的
- Phase 0 で整備した `livecap_core` の前提条件を基に、Core パッケージとして公開できる API/モジュール構成を正式に定義する。
- GUI アプリケーションと Core の責務境界を文書化し、今後の Phase 2 以降の実装フェーズが迷子にならない設計基準を用意する。
- 依存関係や設定スキーマを整理し、`livecap-core` を単体で配布する際の運用モデル（セットアップ方法・テストポリシー）を決める。

## 成果物
- `docs/dev-docs/architecture/core-api-spec.md` 草案（公開 API・イベント・設定エントリーポイントの一覧と利用例）
- `livecap-core/setup.py`（配布時のメタデータとエントリポイント定義）
- `livecap-core/requirements.txt`（Core と GUI で分離された依存関係リスト）
- インターフェイス図と責務境界図（Issue 連携用の添付資料）

## スコープ
- Core パッケージに含めるモジュールと、GUI 側で持つべきアダプタ／翻訳／設定ロードの境界を定義する。
- API として公開するクラス・ファクトリ・ユーティリティを選定し、命名規則とドキュメント方針を固める。
- Core テストと GUI テストを分離するためのテストディレクトリ構造案、CI 実行パスの草案をまとめる。
- 依存パッケージの分類（hard / optional / extra）とバージョンポリシーを決める。

## 対象外（Phase 2 以降に回す項目）
- Core リポジトリの物理作成とコピー作業（Phase 2）
- GUI 側コードの livecap-core 依存への全面移行
- CI/CD の整備および PyPI リリース手順
- GUI 自動テストの整備

## タスクブレークダウン（初期案）
1. **API インベントリ作成**  
   - Phase 0 で抽出済みの Core モジュールを棚卸しし、公開対象／内部実装を分類  
   - 既存コードのインポート状況を `rg` で調査し、GUI から参照している API を洗い出す  
   - 結果を `docs/dev-docs/architecture/core-api-spec.md` に反映し最新版を維持する
2. **コア設定スキーマ整理**  
   - `livecap_core/config/defaults.py`/`validator.py` を中心に、GUI 側設定との境界を明文化（`docs/dev-docs/architecture/core-config-boundaries.md` に反映）  
   - YAML 依存を削減するためのインターフェイス（辞書入力、オプションの Environment Overrides）を定義
3. **依存関係マトリクス作成 / パッケージ草案**  
   - 現在の `requirements.txt` を Core / GUI / 共通に分類（`docs/dev-docs/architecture/dependency-matrix-phase1.md` に記録）  
   - `uv lock` ベースで Core だけで動作させるためのサブセットを抽出  
   - `livecap-core/setup.py` / `livecap-core/requirements.txt` のドラフトに分類結果を反映し、レビュー用メモを添付
4. **ドキュメントドラフト作成**  
   - `core-api-spec.md` の目次と章立てを決め、レビュー用の骨子を Issue に添付  
   - 責務境界の図やフローを作成（mermaid 図の利用を検討）
5. **レビュー/キックオフ準備**  
   - 新規 Issue（Phase 1 トラッキング）でサブタスクと責任者を割り当て  
   - キックオフミーティング用アジェンダ（課題・リスク・マイルストーン）をまとめる

## 成功基準
- Core API と GUI アダプタの境界がドキュメントで合意されている（レビュー完了サインオフ）
- Core パッケージを `pip install` した場合の依存セットが明確で、サンプル CLI の初期設計が提示されている
- Phase 2 で扱う項目（リポジトリ分離、実装リファクタ）の ToDo リストが用意され、見積もりと優先度が付与されている

## リスクと対策
- **API 設計の迷走**: 既存 GUI コードに依存している非公開 API の整理不足 → 早期に API インベントリを作成しレビューを挟む
- **依存関係の抜け漏れ**: Core と GUI の分離後に不足依存が発覚 → `uv` プロファイルを複数用意し実験的にインストールテスト実施
- **設計ドキュメントの肥大化**: 情報が散逸する可能性 → Issue のサマリとこのドキュメントを常に同期させ、不要な項目を Phase 2 へ切り出す

## スケジュール目安
- Week 1: API/モジュール棚卸し、依存マトリクス初版、`core-api-spec.md` 骨子ドラフト
- Week 2: 設定スキーマ仕様の確定、CI 実行パス案作成、レビュー会議
- Week 3（バッファ）: フィードバック反映、Phase 2 バックログ作成、キックオフ資料整備

## 次のアクション
- Phase 1 トラッキング用の新 Issue を作成し、本ドキュメントへのリンクとサブタスク一覧を掲載する。
- `core-api-spec.md` のリファレンスコードと `core-config-boundaries.md` の TypedDict 草案（`livecap_core/config/schema.py` に反映済み）をチームレビューに回し、フィードバック受付用のテンプレートを用意する。
- GUI 設定アダプタ (`gui.config.adapter.CoreConfigBuilder`) の責務を整理し、`core-config-boundaries.md` に Phase 1 で合意した正規化ルール（`multi_source.sources` dict/sequence 両対応など）を明記、将来の正規化 TODO を列挙する。
- `livecap-core/setup.py` / `requirements.txt` のドラフトを Issue #105 に添付し、依存グループの抜け漏れ確認を実施する。
- Windows/Linux 双方の追加 QA（Phase 0 の残フォロー）が完了したタイミングで Phase 1 キックオフミーティングをセットする。

### CI/テストロードマップ (Phase 1)

| プロファイル | 利用 extras | トリガー / 頻度 | コマンド例 | 備考 |
| --- | --- | --- | --- | --- |
| core-only | なし | PR / main push ごと (自動) | `uv run pytest tests/core` | 最小依存セットでの回帰チェック |
| gui + engines-torch | `gui`, `engines-torch` | 任意タイミングで必要に応じて実行 (Nightly 的運用) | `uv run --with gui --with engines-torch pytest tests/gui tests/audio` | GPU 非依存。GUI アダプタと PyTorch 系エンジンの組み合わせ検証 |
| engines-nemo | `engines-nemo` | 必要に応じて手動実行 | `uv run --with engines-nemo pytest tests/transcription` | 現状テストは CPU でも実行可。Phase 2 で GPU 前提の Nemo smoke テストを整備予定 |
| build | `build` | PR ごと | `uv run --with build python -m build` | Core パッケージのビルド確認。PyInstaller は LiveCap (GUI) リリース工程で別管理 |

詳細なコマンド例と補足は [dependency-matrix-phase1.md の UV プロファイル表](./dependency-matrix-phase1.md#5-next-steps) を参照。  
`translation` extra は Phase 2 で導入予定のため、追加時に `uv run --with translation ...` プロファイルを再検討する。
