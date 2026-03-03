"""
Seed the first local admin user.

Creates a single local user with `it-admin` role — enough to log in via
credentials and access /admin/users to create additional users.

Usage:
    cd backend
    PYTHONPATH=. .venv/bin/python scripts/seed_local_admin.py
    PYTHONPATH=. .venv/bin/python scripts/seed_local_admin.py --username admin --email admin@blitz.local --password 'MyStr0ng!'

Idempotent: skips creation if the username already exists.
"""
import argparse
import asyncio
import secrets
import string
import sys
import uuid

from sqlalchemy import select

# Bootstrap path so core.* imports work without the full app startup
sys.path.insert(0, ".")

from core.db import async_session
from core.models.local_auth import LocalUser, LocalUserRole
from security.local_auth import hash_password

_ALPHABET = string.ascii_letters + string.digits


def _generate_password() -> str:
    """Generate a random 20-char password guaranteed to satisfy complexity rules."""
    while True:
        pwd = "".join(secrets.choice(_ALPHABET) for _ in range(20))
        if any(c.isupper() for c in pwd) and any(c.islower() for c in pwd) and any(c.isdigit() for c in pwd):
            return pwd


async def seed(username: str, email: str, password: str) -> None:
    # Validate complexity before any DB operation
    try:
        pw_hash = hash_password(password)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    async with async_session() as session:
        # Check if user already exists
        existing = await session.scalar(
            select(LocalUser).where(LocalUser.username == username)
        )
        if existing:
            print(f"User '{username}' already exists (id={existing.id}) — skipping.")
            return

        # Insert user
        user_id = uuid.uuid4()
        user = LocalUser(
            id=user_id,
            username=username,
            email=email,
            password_hash=pw_hash,
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
    parser.add_argument(
        "--password",
        default=None,
        help="Password (auto-generated if not provided)",
    )
    args = parser.parse_args()
    password: str = args.password or _generate_password()

    asyncio.run(seed(args.username, args.email, password))


if __name__ == "__main__":
    main()
