#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_repo="${repo_root}/code/SWE-agent"
runtime_root="${1:-${repo_root}/tmp/runtime/SWE-agent-local}"
patch_file="${repo_root}/patches/sweagent_local_api.patch"
venv_root="${HOME}/.venvs/sweagent-paper"

snapshot="$(git -C "${source_repo}" rev-parse HEAD)"

if [[ ! -e "${runtime_root}/.git" ]]; then
  mkdir -p "$(dirname "${runtime_root}")"
  git -C "${source_repo}" worktree add --detach "${runtime_root}" "${snapshot}"
fi

if git -C "${runtime_root}" apply --check "${patch_file}"; then
  git -C "${runtime_root}" apply "${patch_file}"
elif ! git -C "${runtime_root}" apply --reverse --check "${patch_file}"; then
  echo "Runtime patch is neither applicable nor already applied." >&2
  exit 1
fi

"${HOME}/.local/bin/uv" pip install \
  --python "${venv_root}/bin/python" \
  --editable "${runtime_root}"

printf 'snapshot=%s\nruntime=%s\n' "${snapshot}" "${runtime_root}"
