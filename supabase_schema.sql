create table if not exists public.usage_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  action text not null,
  created_at timestamptz not null default now()
);

create index if not exists usage_events_user_action_created_idx
  on public.usage_events (user_id, action, created_at desc);

alter table public.usage_events enable row level security;
