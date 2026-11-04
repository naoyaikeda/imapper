import os
import time
from urllib.parse import parse_qs, urlparse

import httpx
from dotenv import load_dotenv

EXCHANGE_SCOPE = "https://outlook.office365.com/IMAP.AccessAsUser.All offline_access"


class ExchangeAuth:
    client_id: str | None
    client_secret: str | None
    tenant_id: str
    redirect_uri: str
    auth_url: str
    token_url: str
    device_code_url: str

    def __init__(self):
        load_dotenv()
        self.client_id = os.getenv("EXCHANGE_CLIENT_ID")
        self.client_secret = os.getenv("EXCHANGE_CLIENT_SECRET") or os.getenv(
            "EXCHANGE_CLIENt_SECRET"
        )
        self.tenant_id = os.getenv("EXCHANGE_TENANT_ID", "common")
        self.redirect_uri = (
            "https://login.microsoftonline.com/common/oauth2/nativeclient"
        )
        base_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0"
        self.auth_url = f"{base_url}/authorize"
        self.token_url = f"{base_url}/token"
        self.device_code_url = f"{base_url}/devicecode"

    def request_device_code(self) -> dict:
        """デバイスコードフローを開始し、user_code と verification_uri を取得する"""
        data = {
            "client_id": self.client_id,
            "scope": EXCHANGE_SCOPE,
        }
        response = httpx.post(self.device_code_url, data=data)
        if response.status_code != 200:
            try:
                err = response.json()
                desc = err.get("error_description") or err.get("error") or response.text
            except ValueError:
                desc = response.text
            raise RuntimeError(f"Failed to request device code: {desc}")
        return response.json()

    def poll_for_token(self, device_code_info: dict) -> dict:
        """ユーザーがブラウザで認証を完了するまでポーリングしてトークンを取得する"""
        device_code = device_code_info["device_code"]
        interval = int(device_code_info.get("interval", 5))
        expires_in = int(device_code_info.get("expires_in", 900))
        deadline = time.monotonic() + expires_in

        while time.monotonic() < deadline:
            time.sleep(interval)
            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": self.client_id,
                "device_code": device_code,
            }
            response = httpx.post(self.token_url, data=data)
            if response.status_code == 200:
                return response.json()

            if response.status_code == 400:
                err_data = response.json()
                error = err_data.get("error")
                if error == "authorization_pending":
                    continue
                if error == "slow_down":
                    interval += 5
                    continue
                desc = err_data.get("error_description") or error
                raise RuntimeError(f"Device code authentication failed: {desc}")

            response.raise_for_status()

        raise TimeoutError("Device code authentication timed out.")

    def get_access_token(self, auth_code: str) -> dict:
        data = {
            "code": auth_code,
            "scope": EXCHANGE_SCOPE,
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }
        response = httpx.post(self.token_url, data=data)
        response.raise_for_status()
        return response.json()

    def refresh_access_token(self, refresh_token: str) -> dict:
        data = {
            "client_id": self.client_id,
            "scope": EXCHANGE_SCOPE,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        response = httpx.post(self.token_url, data=data)
        response.raise_for_status()
        return response.json()

    def get_auth_url(self) -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "response_mode": "query",
            "scope": EXCHANGE_SCOPE,
            "state": "12345",
        }
        request = httpx.Request("GET", self.auth_url, params=params)
        return str(request.url)

    def extract_auth_code(self, redirect_response: str) -> str | None:
        parsed_url = urlparse(redirect_response)
        auth_code = parse_qs(parsed_url.query).get("code", [None])[0]
        return auth_code
