"""Seed a test user for development."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import UserRepository, get_db


def main():
    db = get_db()
    repo = UserRepository(db=db)

    username = "testuser"
    password = "testpass"

    existing = repo.find_by_username(username)
    if existing:
        print(f"User '{username}' already exists.")
        return

    repo.create_user(username, password)
    print(f"Created test user: {username} / {password}")


if __name__ == "__main__":
    main()
