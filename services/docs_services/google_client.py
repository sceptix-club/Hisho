from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from config import Settings


class GoogleUserClient:
    def __init__(self, settings: Settings, access_token: str, refresh_token: str):
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.client_id,
            client_secret=settings.client_secret,
        )
        self.service = build("docs", "v1", credentials=creds)