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

## 3. 言語コード調査

各エンジン・サービスが期待する言語コード形式を公式ドキュメントから調査した。

### 3.1 ASR エンジン（現在採用）

| エンジン | 言語コード形式 | サポート言語 | 変換要否 | 公式ドキュメント |
|---------|--------------|-------------|---------|----------------|
| **ReazonSpeech K2 v2** | なし | `ja` のみ（固定） | 不要 | [GitHub](https://github.com/reazon-research/ReazonSpeech) |
| **Parakeet TDT 0.6B v2** | なし | `en` のみ（固定） | 不要 | [HuggingFace](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2) |
| **Parakeet TDT CTC JA** | なし | `ja` のみ（固定） | 不要 | [HuggingFace](https://huggingface.co/nvidia/parakeet-tdt_ctc-0.6b-ja) |
| **Canary 1B Flash** | ISO 639-1 (2文字) | `en`, `de`, `es`, `fr` | **必要** | [HuggingFace](https://huggingface.co/nvidia/canary-1b-flash) |
| **Voxtral Mini 3B** | ISO 639-1 (2文字) | `en`, `es`, `fr`, `pt`, `hi`, `de`, `nl`, `it`, `auto` | **必要** | [HuggingFace](https://huggingface.co/mistralai/Voxtral-Mini-3B-2507) |
| **WhisperS2T** | ISO 639-1 (2文字) | 100言語 | **必要** | [GitHub](https://github.com/openai/whisper/blob/main/whisper/tokenizer.py) |

### 3.2 翻訳サービス（将来対応）

| サービス | 言語コード形式 | 例 | 備考 | 公式ドキュメント |
|---------|--------------|---|------|----------------|
| **Google Translate** | ISO 639-1 / BCP-47 | `zh-CN`, `zh-TW`, `pt-BR` | レガシー: `he`→`iw`, `jv`→`jw` | [Google Cloud](https://cloud.google.com/translate/docs/languages) |
| **NVIDIA RIVA** | BCP-47 (言語-国) | `en-US`, `ja-JP`, `es-ES` | 26言語サポート | [NVIDIA Docs](https://docs.nvidia.com/nim/riva/asr/latest/support-matrix.html) |

### 3.3 言語コード形式の比較

| 形式 | 説明 | 例 | 使用サービス |
|-----|------|---|-------------|
| **ISO 639-1** | 2文字言語コード | `zh`, `pt`, `es` | Whisper, Canary, Voxtral |
| **BCP-47** | 言語-地域コード | `zh-CN`, `pt-BR`, `es-ES` | Google Translate, RIVA |

### 3.4 変換ルール設計

#### ASR エンジン向け変換（`to_asr_code`）

UI/ユーザー入力（BCP-47）から ASR エンジン用（ISO 639-1）への変換：

```python
_ASR_CODE_MAP = {
    # 中国語: 地域コード → 基本コード
    "zh-CN": "zh",
    "zh-TW": "zh",

    # ポルトガル語: 地域コード → 基本コード
    "pt-BR": "pt",
    "pt-PT": "pt",

    # スペイン語: 地域コード → 基本コード
    "es-ES": "es",
    "es-US": "es",

    # フランス語: 地域コード → 基本コード
    "fr-FR": "fr",
    "fr-CA": "fr",

    # 英語: 地域コード → 基本コード
    "en-US": "en",
    "en-GB": "en",
}
```

#### Google Translate 向け変換（将来実装）

```python
# ISO 639-1 → Google レガシーコード
_GOOGLE_LEGACY_CODES = {
    "he": "iw",  # Hebrew
    "jv": "jw",  # Javanese
}
# BCP-47形式はそのまま使用（zh-CN, zh-TW, pt-BR 等）
```

#### NVIDIA RIVA 向け変換（将来実装）

```python
# ISO 639-1 → BCP-47 (デフォルト国コード付与)
_RIVA_DEFAULT_REGION = {
    "en": "en-US",
    "ja": "ja-JP",
    "zh": "zh-CN",
    "pt": "pt-BR",
    "es": "es-ES",
    "fr": "fr-FR",
    "de": "de-DE",
    "it": "it-IT",
    "ko": "ko-KR",
    "ru": "ru-RU",
    "ar": "ar-AR",
    "hi": "hi-IN",
}
```

---

## 4. 設計

### 4.1 統合先

`metadata.py` 内の `EngineMetadata` クラスに言語コード変換機能を追加。

### 4.2 API設計

```python
# 新しいAPI（metadata.py）
EngineMetadata.normalize_language("ZH-TW")  # → "zh-TW"
EngineMetadata.normalize_language("zh")     # → "zh-CN"
EngineMetadata.to_asr_code("zh-CN")         # → "zh"
EngineMetadata.to_asr_code("pt-BR")         # → "pt"
EngineMetadata.get_engines_for_language("zh-CN")  # → ["whispers2t"]
```

### 4.3 設計理由

- 言語コード変換は `get_engines_for_language()` でのみ使用される
- 新しいクラスを増やさずに責務を集約
- シンプルなAPI（`EngineMetadata` が言語・エンジン情報の Single Source of Truth）

---

## 5. 実装計画

### 5.1 修正対象ファイル

| ファイル | 変更内容 |
|---------|----------|
| `livecap_core/languages.py` | **削除** |
| `livecap_core/__init__.py` | `Languages` エクスポート削除 |
| `livecap_core/engines/metadata.py` | 言語コード変換機能を追加 |
| `livecap_core/engines/whispers2t_engine.py` | `EngineMetadata` を使用するよう修正 |
| `docs/architecture/core-api-spec.md` | API ドキュメント更新 |
| `docs/reference/feature-inventory.md` | リファレンス更新 |

### 5.2 metadata.py への追加コード

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
        # UI言語コード → ASR言語コード（ISO 639-1）
        "zh-CN": "zh",
        "zh-TW": "zh",
        "pt-BR": "pt",
        "pt-PT": "pt",
        "es-ES": "es",
        "es-US": "es",
        "fr-FR": "fr",
        "fr-CA": "fr",
        "en-US": "en",
        "en-GB": "en",
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

### 5.3 whispers2t_engine.py の修正

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

### 5.4 get_engines_for_language() の修正

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

## 6. 影響範囲

### 6.1 破壊的変更

| 変更 | 影響 |
|-----|------|
| `languages.py` 削除 | `from livecap_core.languages import Languages` が失敗 |
| `Languages` クラス削除 | 全メソッド使用不可 |
| `LanguageInfo` 削除 | データクラス使用不可 |

### 6.2 移行ガイド

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

### 6.3 削減効果

| 項目 | Before | After |
|-----|--------|-------|
| `languages.py` | 646行 | 0行（削除） |
| `metadata.py` 追加行 | - | ~80行 |
| **純削減** | - | **~566行** |

---

## 7. 完了条件

- [ ] `languages.py` が削除されている
- [ ] `livecap_core/__init__.py` から `Languages` が削除されている
- [ ] `EngineMetadata.normalize_language()` が実装されている
- [ ] `EngineMetadata.to_asr_code()` が実装されている
- [ ] `whispers2t_engine.py` が `EngineMetadata` を使用している
- [ ] `EngineMetadata.get_engines_for_language()` が自己完結している
- [ ] ドキュメントが更新されている
- [ ] 全テストがパス

---

## 8. 関連情報

### 8.1 参考リンク

- Phase 1（asr_code 対応）: PR #171 で完了
- Issue #168: https://github.com/Mega-Gorilla/livecap-core/issues/168

### 8.2 公式ドキュメント

| サービス | URL |
|---------|-----|
| OpenAI Whisper | https://github.com/openai/whisper/blob/main/whisper/tokenizer.py |
| NVIDIA Canary 1B Flash | https://huggingface.co/nvidia/canary-1b-flash |
| MistralAI Voxtral Mini 3B | https://huggingface.co/mistralai/Voxtral-Mini-3B-2507 |
| NVIDIA Parakeet TDT 0.6B v2 | https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2 |
| ReazonSpeech | https://github.com/reazon-research/ReazonSpeech |
| Google Cloud Translation | https://cloud.google.com/translate/docs/languages |
| NVIDIA RIVA ASR | https://docs.nvidia.com/nim/riva/asr/latest/support-matrix.html |

### 8.3 調査で判明した未使用機能一覧

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
