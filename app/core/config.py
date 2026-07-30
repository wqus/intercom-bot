from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str

    GOOGLE_CREDENTIALS_PATH: str = "credentials/google-sa.json"
    GOOGLE_SHEET_ID: str
    GOOGLE_SHEET_WORKSHEET: str = "Sheet1"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()