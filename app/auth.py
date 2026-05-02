import firebase_admin
from firebase_admin import credentials, auth
from fastapi import Header, HTTPException, Depends
from app.config import get_settings
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path

def _initialize_firebase():
    settings = get_settings()
    if not settings.auth_enabled:
        return

    try:
        firebase_admin.get_app()
    except ValueError:
        # 1. Try environment variables (best for Vercel)
        if os.getenv("FIREBASE_PRIVATE_KEY"):
            cred_dict = {
                "type": "service_account",
                "project_id": os.getenv("FIREBASE_PROJECT_ID"),
                "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
                "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
                "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        # 2. Fallback to local file
        elif Path("mekm-35d98-firebase-adminsdk-fbsvc-06ce6df159.json").exists():
            cred = credentials.Certificate("mekm-35d98-firebase-adminsdk-fbsvc-06ce6df159.json")
            firebase_admin.initialize_app(cred)
        else:
            print("WARNING: Firebase not initialized. Service account missing.")

_initialize_firebase()

@dataclass
class CurrentUser:
    id: str
    email: str | None = None

def get_current_user(authorization: str = Header(None)) -> CurrentUser | None:
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    
    token = authorization.split(" ")[1]
    last_exc = None
    # Retry up to 5 times with a total wait of 15 seconds to handle clock skew
    for attempt in range(5):
        try:
            decoded_token = auth.verify_id_token(token)
            return CurrentUser(id=decoded_token['uid'], email=decoded_token.get('email'))
        except Exception as exc:
            last_exc = exc
            error_msg = str(exc).lower()
            if "used too early" in error_msg or "issued in the future" in error_msg:
                import time
                # Wait 3 seconds per attempt
                time.sleep(3)
                continue
            break
    
    raise HTTPException(status_code=401, detail=f"Authentication error: {str(last_exc)}")

def require_render_credit(user: CurrentUser | None) -> None:
    settings = get_settings()
    if not settings.auth_enabled:
        return
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required to render clips.")
    
    # Usage tracking disabled to prevent crash (Database not initialized)
    pass

def public_app_config() -> dict[str, object]:
    settings = get_settings()
    return {
        "auth_enabled": settings.auth_enabled,
        "daily_free_renders": settings.daily_free_renders,
        "youtube_api_key": settings.youtube_api_key,
        "firebase_config": {
            "apiKey": settings.firebase_api_key,
            "authDomain": settings.firebase_auth_domain,
            "projectId": settings.firebase_project_id,
            "storageBucket": settings.firebase_storage_bucket,
            "messagingSenderId": settings.firebase_messaging_sender_id,
            "appId": settings.firebase_app_id,
            "measurementId": settings.firebase_measurement_id,
        }
    }

def count_todays_renders(user_id: str) -> int:
    # Usage tracking disabled to prevent crash
    return 0
