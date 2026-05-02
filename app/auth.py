from fastapi import Header, HTTPException, Depends
from app.config import get_settings
from dataclasses import dataclass
from supabase import create_client, Client
import os
from pathlib import Path

def get_supabase_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_anon_key)

@dataclass
class CurrentUser:
    id: str
    email: str | None = None

def get_current_user(authorization: str = Header(None)) -> CurrentUser | None:
    settings = get_settings()
    if not settings.auth_enabled:
        return None
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    
    token = authorization.split(" ")[1]
    
    try:
        supabase = get_supabase_client()
        user_response = supabase.auth.get_user(token)
        user = user_response.user
        return CurrentUser(id=user.id, email=user.email)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Authentication error: {str(exc)}")

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
        "supabase_url": settings.supabase_url,
        "supabase_anon_key": settings.supabase_anon_key
    }

def count_todays_renders(user_id: str) -> int:
    # Usage tracking disabled to prevent crash
    return 0
