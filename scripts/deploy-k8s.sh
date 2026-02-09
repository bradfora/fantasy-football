#!/usr/bin/env bash
# Deploy the fantasy-football app to local Kubernetes (Docker Desktop).
# Usage: ./scripts/deploy-k8s.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "==> Building Docker image..."
docker build -t fantasy-football:latest "$PROJECT_DIR"

echo "==> Applying Kubernetes manifests..."
kubectl apply -f "$PROJECT_DIR/k8s/mongodb-secret.yaml"
kubectl apply -f "$PROJECT_DIR/k8s/secret.yaml"
kubectl apply -f "$PROJECT_DIR/k8s/mongodb-pvc.yaml"
kubectl apply -f "$PROJECT_DIR/k8s/mongodb-deployment.yaml"
kubectl apply -f "$PROJECT_DIR/k8s/mongodb-service.yaml"
kubectl apply -f "$PROJECT_DIR/k8s/deployment.yaml"
kubectl apply -f "$PROJECT_DIR/k8s/service.yaml"

echo "==> Restarting fantasy-football deployment to pick up new image..."
kubectl rollout restart deployment/fantasy-football

echo "==> Waiting for pods to be ready..."
kubectl rollout status deployment/mongodb --timeout=60s
kubectl rollout status deployment/fantasy-football --timeout=120s

echo "==> Current pod status:"
kubectl get pods

echo ""
echo "App is available at http://localhost:30500"
echo "Run tests with: pytest tests/e2e/ -v"
