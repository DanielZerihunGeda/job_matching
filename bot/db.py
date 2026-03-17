from __future__ import annotations

import asyncpg


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE TABLE IF NOT EXISTS user_job_titles (
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, title)
);

CREATE INDEX IF NOT EXISTS idx_user_job_titles_title
    ON user_job_titles (title);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'title'
    ) THEN
        INSERT INTO user_job_titles (user_id, title)
        SELECT
            user_id,
            trim(title_entry)
        FROM users,
        LATERAL unnest(string_to_array(title, ',')) AS title_entry
        WHERE title IS NOT NULL AND trim(title_entry) <> ''
        ON CONFLICT (user_id, title) DO NOTHING;
    END IF;
END $$;
"""


async def create_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn=dsn,
        min_size=1,
        max_size=10,
        command_timeout=30,
    )


async def init_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
