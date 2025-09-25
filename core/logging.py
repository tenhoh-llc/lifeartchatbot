"""
ロギング設定モジュール
loguruを使用して統一的なログ出力を提供
"""
import sys
from pathlib import Path
from loguru import logger
from typing import Optional


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
    enable_console: bool = True,
    enable_file: bool = True,
    rotation: str = "100 MB",
    retention: str = "30 days",
    privacy_mode: bool = True
) -> None:
    """
    アプリケーション全体のロギング設定
    
    Args:
        log_level: ログレベル (DEBUG, INFO, WARNING, ERROR)
        log_file: ログファイルのパス
        enable_console: コンソール出力の有効/無効
        enable_file: ファイル出力の有効/無効
        rotation: ログローテーションの条件（サイズまたは時間）
        retention: ログファイルの保持期間
        privacy_mode: プライバシー保護モード（クエリの一部マスキング）
    
    loguruの特徴:
    - 色付きコンソール出力
    - 自動ローテーション
    - 構造化ログ
    - 例外の詳細トレース
    """
    # 既存のハンドラーをクリア
    logger.remove()
    
    # フォーマット設定
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    
    # コンソール出力の設定
    if enable_console:
        logger.add(
            sys.stderr,
            format=log_format,
            level=log_level,
            colorize=True
        )
    
    # ファイル出力の設定
    if enable_file and log_file:
        # ログディレクトリの作成
        log_dir = log_file.parent if log_file else Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # ファイル用のフォーマット（色なし）
        file_format = (
            "{time:YYYY-MM-DD HH:mm:ss} | "
            "{level: <8} | "
            "{name}:{function}:{line} - "
            "{message}"
        )
        
        logger.add(
            log_file or log_dir / "app.log",
            format=file_format,
            level=log_level,
            rotation=rotation,
            retention=retention,
            encoding="utf-8",
            enqueue=True  # マルチスレッド対応
        )
    
    # プライバシー保護用フィルター
    if privacy_mode:
        @logger.patch
        def privacy_filter(record):
            """
            センシティブ情報をマスクする
            - クエリの後半部分を隠す
            - パスワードやAPIキーをマスク
            """
            message = record["message"]
            
            # クエリのマスキング（16文字以降を隠す）
            if "query:" in message.lower():
                parts = message.split(":", 1)
                if len(parts) == 2 and len(parts[1]) > 16:
                    record["message"] = f"{parts[0]}:{parts[1][:16]}..."
            
            # パスワードのマスキング
            for keyword in ["password", "api_key", "secret"]:
                if keyword in message.lower():
                    import re
                    record["message"] = re.sub(
                        f"{keyword}[=:]\\s*\\S+",
                        f"{keyword}=****",
                        message,
                        flags=re.IGNORECASE
                    )
    
    logger.info(f"ロギング設定完了: level={log_level}")


def get_logger(name: str) -> logger:
    """
    モジュール固有のロガーを取得
    
    Args:
        name: モジュール名（通常は__name__を渡す）
    
    Returns:
        設定済みのロガーインスタンス
    """
    return logger.bind(name=name)


# 使用例を含むヘルパー関数
def log_function_call(func_name: str, **kwargs):
    """
    関数呼び出しをログに記録
    デバッグ時に便利
    """
    logger.debug(f"Function called: {func_name}", **kwargs)


def log_error_with_context(error: Exception, context: dict):
    """
    エラーを詳細なコンテキストと共に記録
    """
    logger.error(
        f"Error occurred: {type(error).__name__}: {str(error)}",
        exception=error,
        **context
    )