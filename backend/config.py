from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    llm_provider: str = "claude"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3.5-27b"
    wiki_path: str = "./wiki"
    db_path: str = "./data/raw.db"
    google_client_id: str = ""
    google_client_secret: str = ""

    class Config:
        env_file = ".env"

    @property
    def wiki_dir(self) -> Path:
        return Path(self.wiki_path)

    @property
    def db_file(self) -> Path:
        return Path(self.db_path)


settings = Settings()
