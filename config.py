from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from google.adk.models import LiteLlm


class Settings(BaseSettings):
    letter_model: str = Field(alias="LETTER_MODEL")
    ollama_base_url: str = Field(
        default="http://localhost:11434", alias="OLLAMA_BASE_URL"
    )
    database_url: str = Field(alias="DATABASE_URL")
    client_id: str = Field(alias="CLIENT_ID")
    client_secret: str = Field(alias="CLIENT_SECRET")
    google_access_token: str | None = Field(default=None, alias="GOOGLE_ACCESS_TOKEN")
    google_refresh_token: str | None = Field(default=None, alias="GOOGLE_REFRESH_TOKEN")
    jwt_auth_secret: str | None = Field(default=None, alias="JWT_AUTH_SECRET")
    embedding_model: str = Field(default="nomic-embed-text", alias="EMBEDDING_MODEL")
    letters_doc_id: str | None = Field(default=None, alias="LETTERS_DOC_ID")
    admin_email: str = Field(alias="ADMIN_EMAIL")
    frontend_url: str = Field(alias="FRONTEND_URL")
    google_redirect_uri: str = Field(alias="GOOGLE_REDIRECT_URI")

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
