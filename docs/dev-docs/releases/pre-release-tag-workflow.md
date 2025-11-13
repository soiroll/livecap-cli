# プレリリースタグ運用ガイド

**対象**: LiveCap Core メンテナ  
**最終更新**: 2025-11-13

LiveCap Core の 1.0.0 系プレリリース (alpha/beta/rc) を発行する際の手順をまとめました。  
PEP 440 準拠のバージョンと Git タグを同期し、TestPyPI での検証と Live_Cap_v3 への告知を忘れないようにします。

---

## 1. バージョン & タグ命名規則

| ステージ | `pyproject.toml` の `version` | Git タグ (`core-<semver>`) | 目的 |
| --- | --- | --- | --- |
| Alpha | `1.0.0aN` | `core-1.0.0aN` | API/依存の大枠確認。破壊的変更を許容。 |
| Beta  | `1.0.0bN` | `core-1.0.0bN` | 仕様凍結。バグ修正と安定化が中心。 |
| RC    | `1.0.0rcN` | `core-1.0.0rcN` | 出荷候補。CI と手動検証を全通し。 |
| GA    | `1.0.0`    | `core-1.0.0`    | 正式リリース。 |

### ブランチ運用

- `main` は常に `1.0.0.dev0`。通常開発と依存更新を受け入れる。
- `release/<major.minor>` を切り、上記ステージごとにバージョンを進める。
- 各ステージで TestPyPI アップロードとタグ付けをセットで実施する。

---

## 2. ワークフロー詳細

1. **ブランチ準備**
   ```bash
   git switch main && git pull
   git switch release/1.0 || git switch -c release/1.0
   git merge --ff-only origin/main
   ```

2. **バージョン更新**
   ```bash
   export NEXT=1.0.0a1   # 例: alpha1
   uv version $NEXT      # pyproject.toml / uv.lock を同期
   ```

3. **ロックファイル & 依存確認**
   ```bash
   uv lock --locked
   uv sync --extra dev --extra translation
   uv pip check
   ```

4. **スモークテスト**
   ```bash
   uv run pytest tests
   uv run python -m compileall livecap_core
   uv run livecap-core --dump-config --as-json > artifacts/config-$NEXT.json
   ```

5. **パッケージ検証 (TestPyPI)**
   ```bash
   uv run python -m build
   uv run twine upload --repository testpypi dist/*
   ```

6. **コミット & タグ**
   ```bash
   git status          # 差分確認
   git commit -am "release: bump to $NEXT"
   git tag -s core-$NEXT -m "LiveCap Core $NEXT"
   git push origin release/1.0 --follow-tags
   ```

7. **Live_Cap_v3 調整**
   - `Live_Cap_v3` リポジトリで `pyproject.toml` / `uv.lock` の `livecap-core` 依存を `core-$NEXT` に更新。
   - Discord の `#release` チャンネルと Issue Tracker に告知。

---

## 3. ロールバック手順

1. TestPyPI/CI で不具合を検知したら、該当コミットを `git revert` で取り消す。
2. 公開済みタグは以下で削除:
   ```bash
   git tag -d core-$NEXT
   git push origin :refs/tags/core-$NEXT
   ```
3. `pyproject.toml` の `version` を `1.0.0.dev0` へ戻し、Issue に原因と再発防止策を記載。

---

## 4. 連絡フロー

1. **Internal**: Discord `#licensing` / `#release` で共有し、ブロッカーがないか確認。
2. **Live_Cap_v3**: 依存更新 PR を起票し、テスト結果を添付。
3. **公開告知**: GA のみ GitHub Release を作成し、要約と検証ログを貼付。プレリリース段階では Draft Release を使用。

---

## 5. チェックリスト

### タグ付け前
- [ ] `pyproject.toml` の `version` と予定タグが一致している
- [ ] `uv lock`, `uv pip check`, `pytest`, `compileall`, `livecap-core --dump-config` を完了
- [ ] TestPyPI アップロード結果を確認
- [ ] Live_Cap_v3 で依存 bump PR を準備

### タグ付け後
- [ ] `git push --follow-tags` 済み
- [ ] Discord で告知、質問窓口を案内
- [ ] Issue/PR に検証結果・ログを添付
- [ ] ロールバック手順と責任者を共有

---

このガイドを `docs/dev-docs/releases/pre-release-tag-workflow.md` として更新し続け、リリース担当者が都度チェックできるようにしてください。
