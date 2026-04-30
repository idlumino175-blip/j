from dataclasses import dataclass
from datetime import datetime, timezone

import requests
from fastapi import Header, HTTPException

from app.config import get_settings


@dataclass
class CurrentUser:
    id: str
    email: str | None = None


def is_auth_enabled() -> bool:
    settings = get_settings()
    return bool(settings.supabase_url and settings.supabase_anon_key and settings.supabase_service_role_key)


def public_app_config() -> dict[str, object]:
    settings = get_settings()
    return {
        "auth_required": is_auth_enabled(),
        "supabase_url": settings.supabase_url,
        "supabase_anon_key": settings.supabase_anon_key,
        "daily_free_renders": settings.daily_free_renders,
    }


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser | None:
    if not is_auth_enabled():
        return None
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Please sign in to render clips.")

    token = authorization.split(" ", 1)[1].strip()
    settings = get_settings()
    response = requests.get(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
        headers={
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {token}",
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")

    data = response.json()
    user_id = data.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    return CurrentUser(id=user_id, email=data.get("email"))


def require_render_credit(user: CurrentUser | None) -> None:
    if not is_auth_enabled() or user is None:
        return

    settings = get_settings()
    used = count_todays_renders(user.id)
    if used >= settings.daily_free_renders:
        raise HTTPException(
            status_code=402,
            detail=f"Daily free render limit reached. You have {settings.daily_free_renders} renders per day.",
        )
    record_render_usage(user.id)


def count_todays_renders(user_id: str) -> int:
    settings = get_settings()
    today = datetime.now(timezone.utc).date().isoformat()
    response = requests.get(
        f"{settings.supabase_url.rstrip('/')}/rest/v1/usage_events",
        headers=supabase_service_headers(count=True),
        params={
            "user_id": f"eq.{user_id}",
            "action": "eq.render",
            "created_at": f"gte.{today}T00:00:00Z",
            "select": "id",
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Could not check daily render limit.")
    content_range = response.headers.get("content-range", "")
    if "/" in content_range:
        return int(content_range.rsplit("/", 1)[1])
    return len(response.json())


def record_render_usage(user_id: str) -> None:
    settings = get_settings()
    response = requests.post(
        f"{settings.supabase_url.rstrip('/')}/rest/v1/usage_events",
        headers=supabase_service_headers(),
        json={"user_id": user_id, "action": "render"},
        timeout=20,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Could not record render usage.")


def supabase_service_headers(count: bool = False) -> dict[str, str]:
    settings = get_settings()
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    if count:
        headers["Prefer"] = "count=exact"
    return headers
