"""NeMo フレームワーク用の共通ユーティリティ

Canary, Parakeet エンジンで共有される NeMo 関連の機能を提供。

PyInstaller 互換性:
    NeMo をインポートすると datasets ライブラリの循環インポートエラーが発生するため、
    check_nemo_availability() ではインポートを行わず、importlib.util.find_spec() で
    存在確認のみを行う。実際のインポートは prepare_nemo_environment() を呼び出した後、
    各エンジンの関数内で行う。
"""
import importlib.util
import os
import sys
import logging

logger = logging.getLogger(__name__)

# NeMo framework - 遅延インポート
NEMO_AVAILABLE = None  # 初期状態は未確認
_NEMO_ENVIRONMENT_PREPARED = False  # 環境準備済みフラグ


def check_nemo_availability() -> bool:
    """NeMo の利用可能性をチェック（インポートは行わない）

    PyInstaller 環境での循環インポート問題を回避するため、
    実際のインポートは行わず、パッケージの存在確認のみを行う。

    Returns:
        bool: NeMo パッケージがインストールされている場合 True
    """
    global NEMO_AVAILABLE
    if NEMO_AVAILABLE is not None:
        return NEMO_AVAILABLE

    try:
        # インポートせずにパッケージの存在を確認
        NEMO_AVAILABLE = importlib.util.find_spec("nemo") is not None
        if NEMO_AVAILABLE:
            logger.debug("NeMo パッケージが検出されました")
        else:
            logger.warning("NeMo パッケージがインストールされていません")
    except Exception as e:
        NEMO_AVAILABLE = False
        logger.warning(f"NeMo の可用性チェックに失敗: {e}")

    return NEMO_AVAILABLE


def prepare_nemo_environment() -> None:
    """NeMo インポート前の環境準備

    NeMo を実際にインポートする前に呼び出す。以下の設定を行う:
    - matplotlib バックエンドを非対話的に設定
    - PyInstaller 互換性のための JIT パッチを適用
    - PyInstaller 環境での追加設定（torch._dynamo, TorchScript 無効化）

    この関数は複数回呼び出しても安全（冪等性あり）。
    """
    global _NEMO_ENVIRONMENT_PREPARED
    if _NEMO_ENVIRONMENT_PREPARED:
        return

    # matplotlib backend issue を回避（Parakeet 用）
    try:
        import matplotlib
        matplotlib.use('Agg')  # 非対話的バックエンドを使用
    except ImportError:
        pass  # matplotlib がない場合は無視

    # PyInstaller 互換性のための JIT パッチを適用
    try:
        from . import nemo_jit_patch
    except ImportError:
        logger.debug("nemo_jit_patch モジュールが見つかりません")

    # PyInstaller 環境での追加設定
    if getattr(sys, 'frozen', False):
        # torch._dynamo を無効化
        os.environ['TORCHDYNAMO_DISABLE'] = '1'
        # TorchScript を無効化
        os.environ['PYTORCH_JIT'] = '0'
        logger.debug("PyInstaller 環境用の設定を適用しました")

    _NEMO_ENVIRONMENT_PREPARED = True
    logger.debug("NeMo 環境準備が完了しました")
