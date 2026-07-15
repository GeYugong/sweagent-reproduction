#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
manifest="${1:-${repo_root}/data/manifests/swebench_lite_dev20_seed42.json}"
model_name="${2:-gpt-5.6-terra}"
batch_id="${3:-dev20_baseline}"
max_new_runs="${4:-1}"

if [[ ! -f "${manifest}" ]]; then
  echo "Manifest not found: ${manifest}" >&2
  exit 2
fi
if [[ ! "${batch_id}" =~ ^[A-Za-z0-9_.-]+$ ]] \
  || [[ ! "${max_new_runs}" =~ ^[1-9][0-9]*$ ]]; then
  echo "Batch id or max-new-runs value is invalid." >&2
  exit 2
fi

mapfile -t instance_ids < <(
  "${HOME}/.venvs/sweagent-paper/bin/python" - "${manifest}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    manifest = json.load(handle)
for instance_id in manifest["instances"]:
    print(instance_id)
PY
)

started=0
for instance_id in "${instance_ids[@]}"; do
  run_id="${batch_id}_${instance_id//__/_}"
  trace_root="${repo_root}/outputs/traces/${run_id}"
  if find "${trace_root}" -maxdepth 1 -name '*.traj' -print -quit 2>/dev/null | grep -q .; then
    echo "skip_completed=${instance_id}"
    continue
  fi

  "${repo_root}/scripts/run_local_api_instance.sh" \
    "${instance_id}" "${model_name}" "${run_id}"
  started=$((started + 1))
  if [[ "${started}" -ge "${max_new_runs}" ]]; then
    break
  fi
done

echo "new_runs=${started}"
