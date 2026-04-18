from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "TraceLens"
    env: str = "development"


def get_settings() -> Settings:
    return Settings()
