# Handoff: Phase 2 - Add Persistence Layer

## What Was Done
- **docker-compose.yaml**: Added MongoDB service (mongo:7), volume, MONGODB_URI for Flask
- **k8s/mongodb-deployment.yaml**: MongoDB pod with PVC and secret refs
- **k8s/mongodb-service.yaml**: ClusterIP service for internal access
- **k8s/mongodb-pvc.yaml**: 1Gi PersistentVolumeClaim
- **k8s/mongodb-secret.yaml.example**: Template for MongoDB credentials
- **requirements.txt**: Added pymongo==4.16.0
- **requirements-dev.txt**: Added mongomock==4.3.0
- **.env.example**: Added MONGODB_URI
- **k8s/deployment.yaml**: Added MONGODB_URI env var referencing MongoDB secret
- **SCHEMA.md**: Documented users and leagues collections with indexes
- **scripts/init_db.py**: Creates collections and indexes
- **db.py**: UserRepository and LeagueRepository with full CRUD
- **test_db.py**: 20 tests using mongomock for all repository operations
- **README.md**: Added MongoDB Setup section

## Verification Results
- 54/54 tests pass (34 app + 20 db)
- db.py is NOT imported by app.py yet (will be wired in Phase 3/4)

## Known Issues / Deferred Items
- None

## Next Step Prerequisites
- Phase 3 will add flask-login, User model, and auth routes
