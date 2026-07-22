-- MergeGuard multi-tenant schema
-- Run this once in Supabase: Dashboard -> SQL Editor -> New query -> paste -> Run
--
-- NOTE: named 'mergeguard_users' (not 'users') because this Supabase project
-- already had an unrelated pre-existing 'users' table from something else —
-- don't touch/rename/drop that one, it has real data.

create table if not exists mergeguard_users (
    id uuid primary key default gen_random_uuid(),
    github_id bigint unique not null,
    github_username text not null,
    github_access_token_encrypted text not null,
    created_at timestamptz default now()
);

create table if not exists repo_configs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references mergeguard_users(id) on delete cascade not null,
    repo_full_name text unique not null,       -- e.g. "shaikasadahmed2k23/DevCrew"
    discord_webhook_url text,
    api_key_encrypted text,                    -- null = using the shared trial pool
    trial_requests_used int default 0,
    github_webhook_id bigint,                  -- so we can delete the webhook if the user disconnects
    created_at timestamptz default now()
);

create index if not exists idx_repo_configs_repo_full_name on repo_configs(repo_full_name);
create index if not exists idx_repo_configs_user_id on repo_configs(user_id);
