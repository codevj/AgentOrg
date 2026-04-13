#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${1:-$(pwd)}"
PROJECT_ID="${2:-$(basename "$REPO_ROOT")}"

echo "Resolution order:"
echo "1) ~/.agent-org (global defaults)"
echo "2) $REPO_ROOT/fleet (repo config)"
echo "3) ~/.agent-org/projects/$PROJECT_ID (personal extension)"
echo "4) task overrides"
