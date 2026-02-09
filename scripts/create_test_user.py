"""Seed a test user for development."""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import UserRepository, get_db


def main():
    parser = argparse.ArgumentParser(description="Create a test user")
    parser.add_argument("--username", default=os.environ.get("TEST_USERNAME"),
                        help="Username (or set TEST_USERNAME env var)")
    parser.add_argument("--password", default=os.environ.get("TEST_PASSWORD"),
                        help="Password (or set TEST_PASSWORD env var)")
    args = parser.parse_args()

    if not args.username or not args.password:
        parser.error("Username and password are required via --username/--password or TEST_USERNAME/TEST_PASSWORD env vars")

    db = get_db()
    repo = UserRepository(db=db)

    existing = repo.find_by_username(args.username)
    if existing:
        print(f"User '{args.username}' already exists.")
        return

    repo.create_user(args.username, args.password)
    print(f"Created test user: {args.username}")


if __name__ == "__main__":
    main()
