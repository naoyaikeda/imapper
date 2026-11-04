import httpx
from dotenv import load_dotenv
import os

class GoogleAuth:
    client_id: str
    client_secret: str
    redirect_uri: str
    auth_url: str
    token_url: str

    def __init__(self):
        load_dotenv()
        self.client_id = os.getenv("GMAIL_CLIENT_ID")
        self.client_secret = os.getenv("GMAIL_CLIENT_SECRET")
        self.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
        self.auth_url = "https://accounts.google.com/o/oauth2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
    
    def get_access_token(self, auth_code: str) -> dict:
        data = {
            "code": auth_code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code"
        }
        response = httpx.post(self.token_url, data=data)
        response.raise_for_status()
        return response.json()
    
    def refresh_access_token(self, refresh_token: str) -> dict:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        response = httpx.post(self.token_url, data=data)
        response.raise_for_status()
        return response.json()

    def get_auth_url(self, scope: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": scope,
            "access_type": "offline",
            "prompt": "consent"
        }
        request = httpx.Request("GET", self.auth_url, params=params)
        return str(request.url)
