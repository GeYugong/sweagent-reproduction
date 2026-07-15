#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tool_root="${HOME}/.local"
venv_root="${HOME}/.venvs/sweagent-paper"
uv_bin="${tool_root}/bin/uv"

export UV_CACHE_DIR="${HOME}/.cache/uv"
export UV_PYTHON_INSTALL_DIR="${tool_root}/share/uv/python"

if [[ ! -x "${uv_bin}" ]]; then
  installer="$(mktemp)"
  curl -LsSf https://astral.sh/uv/0.11.28/install.sh -o "${installer}"
  UV_INSTALL_DIR="${tool_root}/bin" UV_NO_MODIFY_PATH=1 sh "${installer}"
  rm -f "${installer}"
fi

"${uv_bin}" python install 3.9
"${uv_bin}" venv --python 3.9 "${venv_root}"
"${uv_bin}" pip install \
  --python "${venv_root}/bin/python" \
  --constraint "${repo_root}/conf/paper_requirements_constraints.txt" \
  --editable "${repo_root}/code/SWE-agent" \
  pytest

"${venv_root}/bin/python" --version
"${uv_bin}" --version
"${venv_root}/bin/python" "${repo_root}/scripts/verify_paper_snapshot.py"
