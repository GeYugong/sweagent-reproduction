#!/usr/bin/env bash
set -euo pipefail

uv_bin="${HOME}/.local/bin/uv"
venv_root="${HOME}/.venvs/swebench-paper-eval"

if [[ ! -x "${uv_bin}" ]]; then
  echo "uv is not installed; run scripts/setup_local_wsl_env.sh first." >&2
  exit 1
fi

if [[ ! -x "${venv_root}/bin/python" ]]; then
  "${uv_bin}" venv --python 3.9 "${venv_root}"
fi
"${uv_bin}" pip install \
  --python "${venv_root}/bin/python" \
  "swebench==1.0.2" \
  "unidiff==0.7.5"

"${venv_root}/bin/python" - <<'PY'
import swebench
import unidiff
from swebench import get_eval_refs, run_evaluation

print(f"swebench={swebench.__version__}")
print("paper_evaluator_imports=PASS")
PY
