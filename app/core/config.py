from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str

    GOOGLE_CREDENTIALS_PATH: str = "/app/app/credentials/google-sa.json"
    GOOGLE_SHEET_ID: str = ""
    GOOGLE_SHEET_WORKSHEET: str = "Daily"

    REPORT_TIMEZONE: str = "Europe/Moscow"
    REPORT_HOUR: int = 4
    REPORT_MINUTE: int = 50

    # Optional: if set, daily reports are sent only to these Telegram IDs.
    # If empty, all users registered in the bot's users table receive reports.
    REPORT_TELEGRAM_IDS: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
