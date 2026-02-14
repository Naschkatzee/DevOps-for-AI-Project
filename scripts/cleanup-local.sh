#!/usr/bin/env bash
set -euo pipefail
RELEASE="vacation-agent"
helm uninstall "$RELEASE" || true
echo "Removed Helm release $RELEASE"
