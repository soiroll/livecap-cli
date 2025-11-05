# 文字起こし辞書フォーマット統一リファクタリング計画（改訂版）

## 概要

現在、文字起こしデータの辞書フォーマットが複数箇所で異なる形式で定義されており、一貫性が欠如している。これを単一の統一フォーマットに標準化することで、保守性と拡張性を向上させる。

### 改訂履歴
- v2.0 (2025-01-03): イベント型別の型定義を導入し、status/errorイベントとの整合性を改善

## 現状の問題点

### 1. フォーマット定義の分散
- **エンジンレベル**: 最小限のフィールド（text, confidence）
- **SharedEngineManager**: source_id, timestamp, is_finalを追加
- **MultiSourceTranscriber**: event_type, phase, languageを追加
- **TranscriptionDataDict (TypedDict)**: 部分的な型定義のみ

### 2. 暗黙的なフィールド追加
各層で必要に応じてフィールドが追加され、全体像が不明確：
```python
# エンジンレベル
{'text': '...', 'confidence': 0.95}
    ↓
# SharedEngineManager
{'text': '...', 'confidence': 0.95, 'source_id': 'source1', 'timestamp': 123.456, 'is_final': True}
    ↓
# MultiSourceTranscriber  
{'text': '...', 'source_id': 'source1', 'is_final': True, 'timestamp': 123.456, 
 'confidence': 0.95, 'language': 'ja', 'event_type': 'transcription', 'phase': 'final'}
```

### 3. 型安全性の欠如
- 辞書のキーや値の型が実行時まで保証されない
- IDEの補完が効かない
- タイポによるバグが発生しやすい

## 提案する解決策（改訂版）

### 1. イベント型別の統一インターフェース定義

**新規ファイル**: `livecap_core/transcription_types.py`

```python
"""
文字起こしデータの統一型定義（改訂版）

イベント型ごとに適切な必須フィールドを定義し、
全レイヤーで使用される標準的な辞書フォーマットを提供
"""

from typing import TypedDict, Optional, Literal, Any, Dict, Union
from dataclasses import dataclass, field
from datetime import datetime


# === イベント型別の型定義 ===

class TranscriptionEventDict(TypedDict, total=False):
    """
    文字起こしイベントの標準辞書フォーマット
    
    実際のテキスト認識結果を表すイベント。
    """
    
    # === 必須フィールド（transcriptionイベント） ===
    text: str                    # 認識されたテキスト（ソースIDなし）
    source_id: str              # ソース識別子 (source1, source2, etc.)
    is_final: bool              # 確定済みフラグ
    timestamp: float            # Unix timestamp
    event_type: Literal['transcription']  # イベントタイプは固定
    
    # === 基本的な任意フィールド ===
    confidence: Optional[float]  # 信頼度スコア (0.0-1.0)
    language: Optional[str]      # 言語コード (ja, en, zh, etc.)
    phase: Optional[Literal['interim', 'final']]  # 処理フェーズ
    
    # === 表示用フィールド ===
    display_text: Optional[str]  # フォーマット済みテキスト
    
    # === VAD関連フィールド ===
    vad_state: Optional[Literal['silence', 'speech', 'uncertain']]
    speech_probability: Optional[float]  # 0.0-1.0
    
    # === 品質指標 ===
    audio_quality: Optional[float]  # 音声品質スコア
    noise_level: Optional[float]    # ノイズレベル
    
    # === 拡張用 ===
    metadata: Optional[Dict[str, Any]]  # その他のメタデータ


class StatusEventDict(TypedDict, total=False):
    """
    ステータスイベントの標準辞書フォーマット
    
    処理状態の変更を通知するイベント。
    """
    
    # === 必須フィールド（statusイベント） ===
    event_type: Literal['status']      # イベントタイプは固定
    status_code: str                   # ステータスコード
    message: str                       # ステータスメッセージ
    timestamp: float                   # Unix timestamp
    source_id: str                     # ソース識別子
    
    # === 任意フィールド ===
    phase: Optional[Literal['processing', 'ready', 'idle']]
    metadata: Optional[Dict[str, Any]]


class ErrorEventDict(TypedDict, total=False):
    """
    エラーイベントの標準辞書フォーマット
    
    エラー発生を通知するイベント。
    """
    
    # === 必須フィールド（errorイベント） ===
    event_type: Literal['error']       # イベントタイプは固定
    error_code: str                    # エラーコード
    message: str                       # エラーメッセージ
    timestamp: float                   # Unix timestamp
    source_id: str                     # ソース識別子
    
    # === 任意フィールド ===
    error_details: Optional[str]       # 詳細なエラー情報
    metadata: Optional[Dict[str, Any]]


# === 統合型定義 ===
UiEventDict = Union[TranscriptionEventDict, StatusEventDict, ErrorEventDict]


# === 互換性のための旧型定義（段階的削除予定） ===
class MinimalTranscriptionDict(TypedDict):
    """エンジンレベルの最小限の辞書（後方互換性）"""
    text: str
    confidence: float


# === バリデーション ===

def validate_event_dict(data: dict) -> bool:
    """
    辞書が有効なイベント形式かを検証
    
    Args:
        data: 検証する辞書
        
    Returns:
        有効な場合 True
    """
    event_type = data.get('event_type')
    
    if event_type == 'transcription':
        required = ['text', 'source_id', 'is_final', 'timestamp', 'event_type']
    elif event_type == 'status':
        required = ['event_type', 'status_code', 'message', 'timestamp', 'source_id']
    elif event_type == 'error':
        required = ['event_type', 'error_code', 'message', 'timestamp', 'source_id']
    else:
        # 未知のイベントタイプまたはevent_typeが無い場合
        # 後方互換性のため、transcriptionとして扱う
        required = ['text', 'source_id']
    
    return all(field in data for field in required)


# === ヘルパー関数 ===

def create_transcription_event(
    text: str,
    source_id: str,
    is_final: bool = True,
    timestamp: Optional[float] = None,
    **kwargs
) -> TranscriptionEventDict:
    """
    標準的な TranscriptionEventDict を作成
    
    Args:
        text: 認識されたテキスト
        source_id: ソース識別子
        is_final: 確定済みフラグ
        timestamp: タイムスタンプ（省略時は現在時刻）
        **kwargs: その他の任意フィールド
        
    Returns:
        TranscriptionEventDict形式の辞書
    """
    if timestamp is None:
        timestamp = datetime.now().timestamp()
    
    result: TranscriptionEventDict = {
        'event_type': 'transcription',
        'text': text,
        'source_id': source_id,
        'is_final': is_final,
        'timestamp': timestamp
    }
    
    # 任意フィールドを追加
    valid_optional = ['confidence', 'language', 'phase', 'display_text',
                     'vad_state', 'speech_probability', 'audio_quality', 
                     'noise_level', 'metadata']
    for key, value in kwargs.items():
        if key in valid_optional and value is not None:
            result[key] = value
    
    # phaseのデフォルト値設定
    if 'phase' not in result:
        result['phase'] = 'final' if is_final else 'interim'
    
    return result


def create_status_event(
    status_code: str,
    message: str,
    source_id: str,
    timestamp: Optional[float] = None,
    **kwargs
) -> StatusEventDict:
    """
    標準的な StatusEventDict を作成
    
    Args:
        status_code: ステータスコード
        message: ステータスメッセージ
        source_id: ソース識別子
        timestamp: タイムスタンプ（省略時は現在時刻）
        **kwargs: その他の任意フィールド
        
    Returns:
        StatusEventDict形式の辞書
    """
    if timestamp is None:
        timestamp = datetime.now().timestamp()
    
    result: StatusEventDict = {
        'event_type': 'status',
        'status_code': status_code,
        'message': message,
        'source_id': source_id,
        'timestamp': timestamp
    }
    
    # 任意フィールドを追加
    if 'phase' in kwargs:
        result['phase'] = kwargs['phase']
    if 'metadata' in kwargs:
        result['metadata'] = kwargs['metadata']
    
    return result


def create_error_event(
    error_code: str,
    message: str,
    source_id: str,
    timestamp: Optional[float] = None,
    **kwargs
) -> ErrorEventDict:
    """
    標準的な ErrorEventDict を作成
    
    Args:
        error_code: エラーコード
        message: エラーメッセージ
        source_id: ソース識別子
        timestamp: タイムスタンプ（省略時は現在時刻）
        **kwargs: その他の任意フィールド
        
    Returns:
        ErrorEventDict形式の辞書
    """
    if timestamp is None:
        timestamp = datetime.now().timestamp()
    
    result: ErrorEventDict = {
        'event_type': 'error',
        'error_code': error_code,
        'message': message,
        'source_id': source_id,
        'timestamp': timestamp
    }
    
    # 任意フィールドを追加
    if 'error_details' in kwargs:
        result['error_details'] = kwargs['error_details']
    if 'metadata' in kwargs:
        result['metadata'] = kwargs['metadata']
    
    return result
```

### 2. 各レイヤーでの実装修正

#### Phase 1: SharedEngineManager の修正
```python
# src/engines/shared_engine_manager.py
from livecap_core.transcription_types import create_transcription_event

# 変更前
return {
    'text': result.get('text', ''),
    'confidence': result.get('confidence', 1.0),
    'source_id': request.source_id,
    'timestamp': request.timestamp,
    'is_final': True
}

# 変更後
return create_transcription_event(
    text=result.get('text', ''),
    source_id=request.source_id,
    is_final=True,
    timestamp=request.timestamp,
    confidence=result.get('confidence', 1.0),
    language=result.get('language')
)
```

#### Phase 2: MultiSourceTranscriber の修正
```python
# src/audio/transcription/multi_source_transcriber.py
from livecap_core.transcription_types import (
    TranscriptionEventDict, StatusEventDict, 
    create_transcription_event, create_status_event
)

def _on_transcription_result(self, result: Dict[str, Any]):
    # 変更前
    result_dict = {
        'text': result.get('text', ''),
        'source_id': source_id,
        # ...
    }
    
    # 変更後
    result_dict = create_transcription_event(
        text=result.get('text', ''),
        source_id=source_id,
        is_final=result.get('is_final', True),
        timestamp=result.get('timestamp', time.time()),
        confidence=result.get('confidence', 1.0),
        language=result.get('language')
    )
    
    # コールバック
    if self.result_callback:
        self.result_callback(result_dict)

def _on_source_status_change(self, source_id: str, status_code: str, message: str):
    """ステータス変更イベントの送信"""
    # 変更後：create_status_eventを使用
    status_event = create_status_event(
        status_code=status_code,
        message=message,
        source_id=source_id,
        phase='processing' if status_code == 'active' else 'idle'
    )
    
    if self.result_callback:
        self.result_callback(status_event)
```

#### Phase 3: DisplayManager の修正
```python
# src/gui/widgets/transcriber/display_manager.py
from livecap_core.transcription_types import UiEventDict, validate_event_dict

def display_event(self, event: UiEventDict) -> bool:
    """
    統一されたイベント処理の入口（改訂版）
    
    Args:
        event: UiEventDict型のイベント辞書
        
    Returns:
        処理成功時True
    """
    if not validate_event_dict(event):
        logger.warning(f"Invalid event format: {event}")
        return False
    
    event_type = event.get('event_type')
    
    if event_type == 'transcription':
        # TranscriptionDataに変換して表示
        from .transcription_data import TranscriptionData
        transcription_data = TranscriptionData.from_dict(event)
        return self.display_transcription(transcription_data)
    
    elif event_type == 'status':
        # ステータス表示
        message = event.get('message', '')
        self.realtime_text.setPlainText(f"[Status] {message}")
        return True
    
    elif event_type == 'error':
        # エラー表示
        message = event.get('message', '')
        error_code = event.get('error_code', 'UNKNOWN')
        self.realtime_text.setPlainText(f"[Error {error_code}] {message}")
        return True
    
    return False
```

#### Phase 4: TranscriptionData の修正
```python
# src/gui/widgets/transcriber/transcription_data.py
from livecap_core.transcription_types import TranscriptionEventDict, validate_event_dict

@classmethod
def from_dict(cls, data: Dict[str, Any]) -> 'TranscriptionData':
    """
    辞書から生成（改訂版）
    
    TranscriptionEventDict形式の辞書のみ受け付ける
    """
    # イベント型の検証
    if data.get('event_type') != 'transcription' and data.get('event_type') is not None:
        raise ValueError(f"TranscriptionData only accepts transcription events, got: {data.get('event_type')}")
    
    # 必須フィールドの確認
    if 'text' not in data:
        raise ValueError("'text' field is required")
    if 'source_id' not in data:
        raise ValueError("'source_id' field is required")
    
    return cls(
        text=data['text'],
        source_id=data['source_id'],
        is_final=data.get('is_final', False),
        timestamp=data.get('timestamp', datetime.now().timestamp()),
        language=data.get('language'),
        confidence=data.get('confidence'),
        vad_state=data.get('vad_state'),
        speech_probability=data.get('speech_probability'),
        audio_quality=data.get('audio_quality'),
        noise_level=data.get('noise_level'),
        display_text=data.get('display_text'),
        metadata=data.get('metadata', {})
    )
```

### 3. 改訂版の移行戦略

#### Phase 1: 準備フェーズ（影響なし）
1. `livecap_core/transcription_types.py` を作成
   - イベント型別の型定義（TranscriptionEventDict, StatusEventDict, ErrorEventDict）
   - ヘルパー関数（create_transcription_event, create_status_event, create_error_event）
   - バリデーション関数（validate_event_dict）
2. 単体テストを作成
3. ドキュメントを更新

#### Phase 2: 生成側の段階的移行
1. **Step 1**: SharedEngineManager で `create_transcription_event` を使用開始
2. **Step 2**: MultiSourceTranscriber の更新
   - `_on_transcription_result` を `create_transcription_event` に移行
   - `_on_source_status_change` を `create_status_event` に移行
3. **Step 3**: エラーイベントのサポート追加

#### Phase 3: GUI側の統一
1. **Step 1**: DisplayManager に `display_event` メソッドを追加（第一級API）
2. **Step 2**: TranscriptionWidget の更新
   - `on_multi_source_transcription_update` から `DisplayManager.display_event` を呼ぶ
3. **Step 3**: TranscriptionData を内部表現として限定
   - `from_dict` を TranscriptionEventDict 専用に
   - status/error イベントでは TranscriptionData を作成しない

#### Phase 4: 後方互換性の削除
1. 旧形式のTranscriptionDataDictを削除
2. 旧シグナルの削除
3. 未使用のコールバックを整理

## メリット

### 1. 型安全性の向上
- TypedDictによる静的型チェック
- IDEの補完機能が有効に
- 実行前にエラーを検出

### 2. 保守性の向上
- フォーマットが一箇所で定義
- 変更時の影響範囲が明確
- ドキュメントが自動生成可能

### 3. 拡張性の確保
- 新フィールドの追加が容易
- 後方互換性の維持が簡単
- バージョン管理が可能

## 改訂版での主要な改善点

### 1. イベント型別の型定義
- **TranscriptionEventDict**: 文字起こし結果（text必須）
- **StatusEventDict**: ステータス変更（message/status_code必須、text不要）
- **ErrorEventDict**: エラー通知（error_code/message必須）
- **UiEventDict**: 上記の統合型（Union）

### 2. 必須フィールドの適切な分離
- イベント型ごとに異なる必須フィールドを定義
- statusイベントでtext=''の問題を解消
- validate_event_dict()でイベント型に応じた検証

### 3. GUI APIの統一
- DisplayManager.display_event()を第一級APIとして確立
- イベント型による適切な分岐処理
- TranscriptionDataは文字起こしイベント専用の内部表現に

## リスクと対策

### リスク1: 既存コードの破壊
**対策**: 
- 段階的な移行（Phase 1-4）
- 後方互換性の維持（event_typeがない場合はtranscriptionとして扱う）
- 包括的なテストの実施

### リスク2: パフォーマンスへの影響
**対策**:
- バリデーションは軽量に実装
- 必要な箇所のみで型チェック
- ヘルパー関数で効率的な辞書生成

### リスク3: 外部連携への影響
**対策**:
- WebSocket送信部分は変更なし
- 既存のAPIは維持
- 移行期間を設ける

## 実装チェックリスト（改訂版）

### Phase 1: 型定義の追加
- [ ] `livecap_core/transcription_types.py` の作成
  - [ ] TranscriptionEventDict, StatusEventDict, ErrorEventDict の定義
  - [ ] UiEventDict (Union型) の定義
  - [ ] create_transcription_event, create_status_event, create_error_event の実装
  - [ ] validate_event_dict の実装
- [ ] 単体テストの作成

### Phase 2: 生成側の更新
- [ ] SharedEngineManager の更新（create_transcription_event使用）
- [ ] MultiSourceTranscriber の更新
  - [ ] _on_transcription_result の更新
  - [ ] _on_source_status_change の更新

### Phase 3: GUI側の統一
- [ ] DisplayManager.display_event の実装（第一級API）
- [ ] TranscriptionWidget の更新（display_event呼び出し）
- [ ] TranscriptionData.from_dict の更新（TranscriptionEventDict専用）

### Phase 4: 検証と後片付け
- [ ] 統合テストの実施
- [ ] パフォーマンステスト
- [ ] ドキュメントの更新
- [ ] 旧形式サポートの削除

## スケジュール

| フェーズ | 期間 | 作業内容 |
|---------|------|----------|
| 準備 | 1日 | 型定義とテスト作成 |
| 実装 | 3日 | 各レイヤーの修正 |
| テスト | 2日 | 統合テストと検証 |
| 移行 | 1週間 | 段階的な本番適用 |
| 完了 | - | 旧形式の削除 |

## 成功指標

1. **型エラーの削減**: TypeScript同様の型安全性を実現
2. **バグの減少**: フィールド名のタイポによるバグをゼロに
3. **開発効率の向上**: IDE補完により開発速度20%向上
4. **保守コストの削減**: フォーマット変更時の作業時間50%削減

## 関連ドキュメント

- [transcription_pipeline_flow.md](../core-systems/transcription_pipeline_flow.md)
- [simplify_transcription_pipeline.md](./simplify_transcription_pipeline.md) - 実装済み
- TranscriptionData クラス設計書
