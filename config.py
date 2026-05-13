from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from google.adk.models import LiteLlm


class Settings(BaseSettings):
    letter_model: str = Field(alias="LETTER_MODEL")
    ollama_base_url: str = Field(
        default="http://localhost:11434", alias="OLLAMA_BASE_URL"
    )
    database_url: str = Field(alias="DATABASE_URL")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()


def create_model(model_name: str) -> LiteLlm:
    return LiteLlm(model=settings.letter_model, api_base=settings.ollama_base_url)


class Config:
    worker_model = create_model(settings.letter_model)
    critic_model = create_model(settings.letter_model)


try:
    settings = Settings()
except ValidationError as e:
    print(e)


config = Config()
