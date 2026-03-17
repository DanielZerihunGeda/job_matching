from __future__ import annotations

import asyncpg


async def upsert_user_titles(
    pool: asyncpg.Pool,
    user_id: int,
    titles: list[str],
) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO users (user_id, updated_at)
                VALUES ($1, NOW())
                ON CONFLICT (user_id) DO UPDATE
                SET updated_at = NOW();
                """,
                user_id,
            )
            await conn.execute(
                "DELETE FROM user_job_titles WHERE user_id = $1;",
                user_id,
            )
            if titles:
                await conn.executemany(
                    """
                    INSERT INTO user_job_titles (user_id, title)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id, title) DO NOTHING;
                    """,
                    [(user_id, title) for title in titles],
                )


async def find_matching_user_ids(
    pool: asyncpg.Pool,
    titles: list[str],
) -> list[int]:
    if not titles:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT user_id
            FROM user_job_titles
            WHERE title = ANY($1::text[])
            ORDER BY user_id;
            """,
            titles,
        )
    return [row["user_id"] for row in rows]
