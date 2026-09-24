from google.oauth2 import id_token
from google.auth.transport import requests
from backend.core.config import Config

CLIENT_ID = Config.GOOGLE_CLIENT_ID

def verify_google_token(token: str):
    try:
        id_info = id_token.verify_oauth2_token(
            token, requests.Request(), CLIENT_ID
        )
        return id_info
    except ValueError:
        return None