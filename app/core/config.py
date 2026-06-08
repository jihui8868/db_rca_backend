from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    deepseek_api_key: str = "sk-daeeea054da846e6b40fd721e703484f"
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    db_host: str = "192.168.2.133"
    db_port: int = 15432
    db_username: str = "postgres"
    db_password: str = "111111"
    db_name: str = "db_rca"

    @computed_field
    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    upload_dir: str = "./uploads"

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Nightingale (夜莺) monitoring system
    nightingale_url: str = "http://localhost:17000"
    nightingale_username: str = "root"
    nightingale_password: str = ""
    # Prometheus-compatible query path on Nightingale server
    nightingale_prom_path: str = "/prometheus"


settings = Settings()
