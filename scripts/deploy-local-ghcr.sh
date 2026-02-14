#!/usr/bin/env bash
set -euo pipefail

CLUSTER="${1:-devops-ai}"
RELEASE="vacation-agent"
CHART="./helm/vacation-agent"

echo "Using k3d cluster: $CLUSTER"
kubectl config use-context "k3d-$CLUSTER" >/dev/null 2>&1 || true

echo "Deploying Helm release: $RELEASE"
helm upgrade --install "$RELEASE" "$CHART"

echo "Waiting for rollout..."
kubectl rollout status deployment/"$RELEASE" --timeout=180s

echo "Done. Check:"
echo "  kubectl get pods"
echo "  kubectl get svc"
echo "  kubectl get ingress"
