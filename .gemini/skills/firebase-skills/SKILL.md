---
name: firebase-skills
description: Firebase and Supabase development tools. Use for database schema design, Auth configuration, and backend service integration.
---

# Firebase / Supabase Skill

This skill provides specialized procedures for working with Firebase and Supabase services.

## Authentication

### Magic Link Best Practices
- **Persistence**: Always ensure `onAuthStateChange` is used to sync sessions with `localStorage`.
- **Handling Redirects**: Clean the URL hash (`window.history.replaceState`) after a login callback to avoid infinite redirect loops.
- **Session Checking**: Always check `supabase.auth.getSession()` on app load before triggering the sign-in modal.

## Database & Usage

### Supabase Usage Events
- Use `supabase_service_role_key` for administrative tasks (like recording usage events) to bypass Row Level Security (RLS).
- Always use `headers: { Prefer: 'count=exact' }` when querying usage counts.

## Development

### Bypassing Auth for Testing
- Use `is_auth_enabled() -> False` in `auth.py` for local development.
- Always use environment variables in `.env` for production, and use the `pydantic-settings` pattern for loading.
