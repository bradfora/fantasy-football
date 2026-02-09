# Scripts

## init_db.py

Initializes MongoDB collections and indexes. Run against a local or remote MongoDB instance.

```bash
# Uses MONGODB_URI from .env or defaults to mongodb://localhost:27017/fantasy_football
python scripts/init_db.py
```

## create_test_user.py

Seeds a test user for development. See Phase 3.

```bash
python scripts/create_test_user.py
```
