#!/bin/sh
# Publish the sample-mode demo to a Hugging Face Space (Docker SDK). Needs HF_TOKEN (write access) and
# HF_SPACE (owner/name). Called by the deploy job in .gitlab-ci.yml; also works by hand.
set -eu
: "${HF_TOKEN:?set HF_TOKEN}"
: "${HF_SPACE:?set HF_SPACE, e.g. hoongyu/gouji}"
out=$(mktemp -d)
git archive HEAD Dockerfile .dockerignore pyproject.toml uv.lock LICENSE run.py gouji data/sample | tar -x -C "$out"
cp deploy/hf-space/README.md "$out/README.md"
uvx --from "huggingface_hub[cli]>=0.34" hf upload "$HF_SPACE" "$out" . --repo-type space \
  --commit-message "deploy ${CI_COMMIT_SHORT_SHA:-$(git rev-parse --short HEAD)}"
echo "deployed to https://huggingface.co/spaces/$HF_SPACE"
