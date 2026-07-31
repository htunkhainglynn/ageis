#!/usr/bin/env python3
"""Verify the local development database accepts the current .env credentials."""

from __future__ import annotations

import asyncio
import os
import sys

import asyncpg


async def main() -> int:
    try:
        connection = await asyncpg.connect(
            host="localhost",
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user="aegis",
            password=os.environ["POSTGRES_PASSWORD"],
            database="aegis",
        )
    except Exception as exc:  # noqa: BLE001 - user-facing dev preflight
        print("Cannot connect to the local Aegis Postgres database with .env credentials.", file=sys.stderr)
        print(f"Reason: {exc}", file=sys.stderr)
        print("For a stale local dev volume, run: make reset-dev", file=sys.stderr)
        return 2

    await connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
