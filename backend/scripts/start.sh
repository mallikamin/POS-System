#!/usr/bin/env bash
set -euo pipefail

# Use PostgreSQL advisory lock to ensure only one replica runs migrations
echo "==> Running database migrations (with advisory lock)..."
python3 -c "
import asyncio, sys
from sqlalchemy import text
from app.database import async_session_factory

async def migrate():
    async with async_session_factory() as session:
        # pg_try_advisory_lock returns true if lock acquired
        result = await session.execute(text('SELECT pg_try_advisory_lock(1)'))
        got_lock = result.scalar()
        if got_lock:
            print('  Got migration lock, running alembic upgrade head...')
            import subprocess
            proc = subprocess.run(['alembic', 'upgrade', 'head'], check=True)
            await session.execute(text('SELECT pg_advisory_unlock(1)'))
            print('  Migration complete, lock released.')
        else:
            print('  Another instance holds the migration lock, skipping.')

asyncio.run(migrate())
"

echo "==> Starting uvicorn..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    "$@"
