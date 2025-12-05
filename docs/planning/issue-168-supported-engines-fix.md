# Issue #168: languages.py 廃止と EngineMetadata への統合

> **Status**: PLANNING
> **作成日:** 2025-12-05
> **更新日:** 2025-12-05
> **関連 Issue:** #168
> **前提:** Phase 1（asr_code 対応）は PR #171 で完了済み
> **方針:** 破壊的変更を許容

---

## 1. 目的

`languages.py`（646行）を廃止し、必要最小限の機能のみを `metadata.py` に統合する。

---

## 2. 背景

### 2.1 調査結果

`languages.py` の利用状況を調査した結果：

| 機能 | 実コード利用 |
|-----|-------------|
| `Languages.normalize()` | 1箇所 |
| `Languages.get_info()` | 2箇所 |
| `LanguageInfo.asr_code` | 2箇所 |
| **その他全てのメソッド** | **0箇所** |
| **その他全てのフィールド** | **0箇所** |
| **テストでの利用** | **0箇所** |

### 2.2 実質的に必要な機能

646行のモジュールで実際に必要なのは：

1. **言語コード正規化**: `"ZH-TW"` → `"zh-TW"`, `"zh"` → `"zh-CN"`
2. **ASRコード変換**: `"zh-CN"` → `"zh"`, `"pt-BR"` → `"pt"`

これらは**単純なマッピングテーブル**で実現可能。

### 2.3 廃止対象（未使用機能）

| 機能 | 行数 | 状態 |
|-----|------|------|
| `LanguageInfo` 16言語分のメタデータ | ~250行 | 未使用 |
| `Languages.get_display_name()` | ~15行 | 未使用 |
| `Languages.get_google_code()` | ~10行 | 未使用 |
| `Languages.from_windows_lcid()` | ~10行 | 未使用 |
| `Languages.get_supported_codes()` | ~5行 | 未使用 |
| `Languages.get_engines_for_language()` | ~5行 | 未使用 |
| `Languages.is_auto()` | ~5行 | 未使用 |
| `Languages.is_valid()` | ~10行 | 未使用 |
| `Languages.get_languages_for_translation_service()` | ~15行 | 未使用 |
| 非推奨メソッド2つ | ~30行 | 非推奨 |

---

## 3. 設計

### 3.1 統合先

`metadata.py` 内に言語コード変換機能を追加。

### 3.2 クラス設計

**案A: 独立したユーティリティクラス**

```python
# metadata.py

class LanguageUtils:
    """言語コード変換ユーティリティ"""

    _ALIASES: Dict[str, str] = {
        "zh": "zh-CN", "cn": "zh-CN", "tw": "zh-TW",
        "zh-hk": "zh-TW", "zh-hans": "zh-CN", "zh-hant": "zh-TW",
        "en-us": "en", "en-gb": "en",
    }

    _ASR_CODE_MAP: Dict[str, str] = {
        "zh-CN": "zh", "zh-TW": "zh",
        "pt-BR": "pt", "es-ES": "es", "es-US": "es",
    }

    @classmethod
    def normalize(cls, code: str) -> Optional[str]:
        """言語コードを正規化"""
        ...

    @classmethod
    def to_asr_code(cls, code: str) -> str:
        """UI言語コード → ASR言語コードに変換"""
        ...
```

**案B: EngineMetadata に統合（推奨）**

```python
# metadata.py

class EngineMetadata:
    # 既存の _ENGINES 定義...

    # 言語コード変換テーブル
    _LANG_ALIASES: Dict[str, str] = {...}
    _ASR_CODE_MAP: Dict[str, str] = {...}

    @classmethod
    def normalize_language(cls, code: str) -> Optional[str]:
        """言語コードを正規化"""
        ...

    @classmethod
    def to_asr_code(cls, code: str) -> str:
        """UI言語コード → ASR言語コードに変換"""
        ...
```

**推奨: 案B**

理由:
- 言語コード変換は `get_engines_for_language()` でのみ使用される
- 新しいクラスを増やさずに責務を集約
- シンプルなAPI（`EngineMetadata` が言語・エンジン情報の Single Source of Truth）

### 3.3 API設計

```python
# 新しいAPI（metadata.py）
EngineMetadata.normalize_language("ZH-TW")  # → "zh-TW"
EngineMetadata.normalize_language("zh")     # → "zh-CN"
EngineMetadata.to_asr_code("zh-CN")         # → "zh"
EngineMetadata.to_asr_code("pt-BR")         # → "pt"
EngineMetadata.get_engines_for_language("zh-CN")  # → ["whispers2t"]
```

---

## 4. 実装計画

### 4.1 修正対象ファイル

| ファイル | 変更内容 |
|---------|----------|
| `livecap_core/languages.py` | **削除** |
| `livecap_core/__init__.py` | `Languages` エクスポート削除 |
| `livecap_core/engines/metadata.py` | 言語コード変換機能を追加 |
| `livecap_core/engines/whispers2t_engine.py` | `EngineMetadata` を使用するよう修正 |
| `docs/architecture/core-api-spec.md` | API ドキュメント更新 |
| `docs/reference/feature-inventory.md` | リファレンス更新 |

### 4.2 metadata.py への追加コード

```python
class EngineMetadata:
    """エンジンメタデータの中央管理"""

    # === 言語コード変換 ===

    _LANG_ALIASES: Dict[str, str] = {
        # 短縮形 → 標準形
        "zh": "zh-CN",
        "cn": "zh-CN",
        "tw": "zh-TW",
        "hk": "zh-TW",
        "zh-hk": "zh-TW",
        "zh-hans": "zh-CN",
        "zh-hant": "zh-TW",
        "en-us": "en",
        "en-gb": "en",
    }

    _ASR_CODE_MAP: Dict[str, str] = {
        # UI言語コード → ASR言語コード
        "zh-CN": "zh",
        "zh-TW": "zh",
        "pt-BR": "pt",
        "es-ES": "es",
        "es-US": "es",
    }

    # サポートされるUI言語コード（正規化の対象）
    _UI_LANGUAGE_CODES: Set[str] = {
        "ja", "en", "zh-CN", "zh-TW", "ko", "de", "fr", "es",
        "es-ES", "es-US", "ru", "ar", "pt", "pt-BR", "it", "hi", "nl",
    }

    @classmethod
    def normalize_language(cls, code: str) -> Optional[str]:
        """
        言語コードを正規化

        Args:
            code: 入力言語コード（"ja", "ZH-TW", "zh" 等）

        Returns:
            正規化された言語コード、または None

        Examples:
            >>> EngineMetadata.normalize_language("JA")
            "ja"
            >>> EngineMetadata.normalize_language("zh-TW")
            "zh-TW"
            >>> EngineMetadata.normalize_language("zh")
            "zh-CN"
        """
        if not code:
            return None

        code_lower = code.lower().strip()

        # 完全一致（大文字小文字無視）
        for ui_code in cls._UI_LANGUAGE_CODES:
            if ui_code.lower() == code_lower:
                return ui_code

        # エイリアス
        if code_lower in cls._LANG_ALIASES:
            return cls._LANG_ALIASES[code_lower]

        # セパレータ正規化（zh_tw → zh-tw）
        normalized = code_lower.replace("_", "-")
        if normalized in cls._LANG_ALIASES:
            return cls._LANG_ALIASES[normalized]

        return None

    @classmethod
    def to_asr_code(cls, code: str) -> str:
        """
        UI言語コード → ASR言語コードに変換

        Args:
            code: UI言語コード（"zh-CN", "pt-BR" 等）

        Returns:
            ASR言語コード（"zh", "pt" 等）

        Examples:
            >>> EngineMetadata.to_asr_code("zh-CN")
            "zh"
            >>> EngineMetadata.to_asr_code("ja")
            "ja"
        """
        normalized = cls.normalize_language(code) or code
        return cls._ASR_CODE_MAP.get(normalized, normalized)
```

### 4.3 whispers2t_engine.py の修正

```python
# Before
from livecap_core.languages import Languages
...
lang_info = Languages.get_info(language)
asr_language = lang_info.asr_code if lang_info else language

# After
from livecap_core.engines.metadata import EngineMetadata
...
asr_language = EngineMetadata.to_asr_code(language)
```

### 4.4 get_engines_for_language() の修正

```python
# Before（現在の実装）
from livecap_core.languages import Languages
normalized = Languages.normalize(lang_code) or lang_code
lang_info = Languages.get_info(normalized)
asr_code = lang_info.asr_code if lang_info else normalized

# After（自己完結）
normalized = cls.normalize_language(lang_code) or lang_code
asr_code = cls.to_asr_code(normalized)
```

---

## 5. 影響範囲

### 5.1 破壊的変更

| 変更 | 影響 |
|-----|------|
| `languages.py` 削除 | `from livecap_core.languages import Languages` が失敗 |
| `Languages` クラス削除 | 全メソッド使用不可 |
| `LanguageInfo` 削除 | データクラス使用不可 |

### 5.2 移行ガイド

```python
# Before
from livecap_core.languages import Languages
Languages.normalize("zh-TW")
info = Languages.get_info("ja")
asr_code = info.asr_code

# After
from livecap_core.engines.metadata import EngineMetadata
EngineMetadata.normalize_language("zh-TW")
asr_code = EngineMetadata.to_asr_code("ja")
```

### 5.3 削減効果

| 項目 | Before | After |
|-----|--------|-------|
| `languages.py` | 646行 | 0行（削除） |
| `metadata.py` 追加行 | - | ~80行 |
| **純削減** | - | **~566行** |

---

## 6. 完了条件

- [ ] `languages.py` が削除されている
- [ ] `livecap_core/__init__.py` から `Languages` が削除されている
- [ ] `EngineMetadata.normalize_language()` が実装されている
- [ ] `EngineMetadata.to_asr_code()` が実装されている
- [ ] `whispers2t_engine.py` が `EngineMetadata` を使用している
- [ ] `EngineMetadata.get_engines_for_language()` が自己完結している
- [ ] ドキュメントが更新されている
- [ ] 全テストがパス

---

## 7. 関連情報

- Phase 1（asr_code 対応）: PR #171 で完了
- Issue #168: https://github.com/Mega-Gorilla/livecap-core/issues/168

### 7.1 調査で判明した未使用機能一覧

```
Languages.get_display_name()           # 0箇所
Languages.get_google_code()            # 0箇所
Languages.from_windows_lcid()          # 0箇所
Languages.get_supported_codes()        # 0箇所
Languages.get_engines_for_language()   # 0箇所
Languages.is_auto()                    # 0箇所
Languages.is_valid()                   # 0箇所
Languages.get_all_codes()              # 0箇所
Languages.get_aliases()                # 0箇所
Languages.get_name()                   # 0箇所
Languages.get_languages_for_translation_service()  # 0箇所
Languages.get_translation_languages_dict()         # 非推奨
Languages.get_transcription_languages_dict()       # 非推奨

LanguageInfo.display_name              # 0箇所（外部）
LanguageInfo.english_name              # 0箇所（外部）
LanguageInfo.native_name               # 0箇所（外部）
LanguageInfo.flag                      # 0箇所（外部）
LanguageInfo.iso639_1                  # 0箇所（外部）
LanguageInfo.iso639_3                  # 0箇所（外部）
LanguageInfo.windows_lcid              # 0箇所（外部）
LanguageInfo.google_code               # 0箇所（外部）
LanguageInfo.translation_code          # 0箇所（外部）
LanguageInfo.supported_engines         # 0箇所
LanguageInfo.translation_services      # 0箇所（外部）
```
