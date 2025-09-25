"""
設定管理モジュール
環境変数から設定を読み込み、Pydanticでバリデーションする
"""
from pydantic import BaseModel, Field, validator
from pathlib import Path
from typing import Literal, Optional
import os
from dotenv import load_dotenv


class AppConfig(BaseModel):
    """
    アプリケーション全体の設定クラス
    
    Pydanticを使用することで:
    - 型の自動変換とバリデーション
    - 設定値の検証
    - エラーメッセージの自動生成
    が可能になります
    """
    app_password: str = Field(..., min_length=1, description="アプリケーション認証用パスワード")
    pdf_dir: Path = Field(default=Path("./data/pdfs"), description="PDFファイルの格納ディレクトリ")
    index_path: Path = Field(default=Path("./data/index.sqlite"), description="SQLiteデータベースのパス")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", 
        description="ログレベル"
    )
    llm_provider: Literal["none", "openai", "anthropic"] = Field(
        default="none",
        description="使用するLLMプロバイダー"
    )
    llm_api_key: Optional[str] = Field(default=None, description="LLM APIキー")
    tz: str = Field(default="Asia/Tokyo", description="タイムゾーン")
    allowed_files: str = Field(default="就業規則,給与", description="検索対象ファイル制限")

    @validator("pdf_dir", "index_path", pre=False)
    def ensure_paths_exist(cls, v: Path) -> Path:
        """
        パスが存在しない場合は親ディレクトリを作成
        """
        if not v.parent.exists():
            v.parent.mkdir(parents=True, exist_ok=True)
        return v

    @validator("llm_api_key")
    def validate_api_key(cls, v: Optional[str], values: dict) -> Optional[str]:
        """
        LLMプロバイダーが設定されている場合はAPIキーが必要
        """
        provider = values.get("llm_provider")
        if provider and provider != "none" and not v:
            raise ValueError(f"LLM provider '{provider}' requires an API key")
        return v

    @classmethod
    def load(cls) -> "AppConfig":
        """
        環境変数から設定を読み込む
        .envファイルがある場合は自動的に読み込まれる
        """
        # .envファイルを読み込む（存在する場合）
        load_dotenv()
        
        # 環境変数から設定を取得
        config_dict = {
            "app_password": os.getenv("APP_PASSWORD", ""),
            "pdf_dir": Path(os.getenv("PDF_DIR", "./data/pdfs")),
            "index_path": Path(os.getenv("INDEX_PATH", "./data/index.sqlite")),
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
            "llm_provider": os.getenv("LLM_PROVIDER", "none"),
            "llm_api_key": os.getenv("LLM_API_KEY"),
            "tz": os.getenv("TZ", "Asia/Tokyo"),
            "allowed_files": os.getenv("ALLOWED_FILES", "就業規則,給与"),
        }
        
        try:
            return cls(**config_dict)
        except Exception as e:
            # エラーメッセージをわかりやすく表示
            error_msg = f"設定エラー: {str(e)}\n"
            error_msg += "必要な環境変数を.envファイルまたは環境変数に設定してください。"
            raise ValueError(error_msg) from e

    class Config:
        # Pydanticの設定
        validate_assignment = True  # 代入時にもバリデーションを実行