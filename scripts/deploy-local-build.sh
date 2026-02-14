#!/usr/bin/env bash
set -euo pipefail

CLUSTER="${1:-devops-ai}"
IMAGE="vacation-agent-api:local"
RELEASE="vacation-agent"
CHART="./helm/vacation-agent"

echo "Building Docker image: $IMAGE"
docker build -t "$IMAGE" .

echo "Importing image into k3d cluster: $CLUSTER"
k3d image import "$IMAGE" -c "$CLUSTER"

echo "Deploying Helm with local image..."
helm upgrade --install "$RELEASE" "$CHART" \
  --set image.repository="vacation-agent-api" \
  --set image.tag="local" \
  --set image.pullPolicy="IfNotPresent"

kubectl rollout status deployment/"$RELEASE" --timeout=180s
echo "Done."
