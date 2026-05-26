import ssl  # 预加载以尝试解决 Windows OpenSSL 链接问题
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    app_name: str = "BrushFlow"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    db_path: str = str(DATA_DIR / "brush_flow.db")
    db_echo: bool = False

    default_concurrency: int = 5
    global_max_concurrency: int = 50
    chunk_size: int = 131072  # 128KB
    flush_interval: int = 5  # 秒
    max_retries: int = 3

    class Config:
        env_prefix = "BF_"
        env_file = str(BASE_DIR / ".env")
        extra = "ignore"


settings = Settings()
