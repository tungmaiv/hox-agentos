"""
Seed the first local admin user.

Creates a single local user with `it-admin` role — enough to log in via
credentials and access /admin/users to create additional users.

Usage:
    cd backend
    PYTHONPATH=. .venv/bin/python scripts/seed_local_admin.py
    PYTHONPATH=. .venv/bin/python scripts/seed_local_admin.py --username admin --email admin@blitz.local --password secret

Idempotent: skips creation if the username already exists.
"""
import argparse
import asyncio
import sys
import uuid

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Bootstrap path so core.* imports work without the full app startup
sys.path.insert(0, ".")

from core.db import async_session
from core.models.local_auth import LocalUser, LocalUserRole


async def seed(username: str, email: str, password: str) -> None:
    async with async_session() as session:
        # Check if user already exists
        existing = await session.scalar(
            select(LocalUser).where(LocalUser.username == username)
        )
        if existing:
            print(f"User '{username}' already exists (id={existing.id}) — skipping.")
            return

        # Hash password
        password_hash = bcrypt.hashpw(
            password.encode(), bcrypt.gensalt()
        ).decode()

        # Insert user
        user_id = uuid.uuid4()
        user = LocalUser(
            id=user_id,
            username=username,
            email=email,
            password_hash=password_hash,
            is_active=True,
        )
        session.add(user)

        # Assign it-admin role directly (grants registry:manage → /admin access)
        session.add(LocalUserRole(user_id=user_id, role="it-admin"))

        await session.commit()

    print(f"Created local admin user:")
    print(f"  username : {username}")
    print(f"  email    : {email}")
    print(f"  password : {password}")
    print(f"  roles    : it-admin")
    print()
    print(f"Log in at: http://localhost:3000/login")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed first local admin user")
    parser.add_argument("--username", default="admin", help="Username (default: admin)")
    parser.add_argument("--email", default="admin@blitz.local", help="Email (default: admin@blitz.local)")
    parser.add_argument("--password", default="admin", help="Password (default: admin)")
    args = parser.parse_args()

    asyncio.run(seed(args.username, args.email, args.password))


if __name__ == "__main__":
    main()
