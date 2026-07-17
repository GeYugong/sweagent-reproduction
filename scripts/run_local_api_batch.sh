#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
manifest="${1:-${repo_root}/data/manifests/swebench_lite_dev20_seed42.json}"
model_name="${2:-gpt-5.6-terra}"
batch_id="${3:-dev20_baseline}"
max_new_runs="${4:-1}"
max_api_calls="${5:-25}"
eval_python="${HOME}/.venvs/swebench-paper-eval/bin/python"
eval_testbed="${SWE_AGENT_EVAL_TESTBED:-${HOME}/sb}"
nonretry_manifest="${repo_root}/data/manifests/nonretry_after_model_response.json"
zero_response_retry_manifest="${repo_root}/data/manifests/zero_model_response_retries.json"

if [[ ! -f "${manifest}" ]]; then
  echo "Manifest not found: ${manifest}" >&2
  exit 2
fi
if [[ ! -x "${eval_python}" ]]; then
  echo "Evaluation environment is missing; run scripts/setup_local_eval_env.sh first." >&2
  exit 2
fi
if [[ ! "${batch_id}" =~ ^[A-Za-z0-9_.-]+$ ]] \
  || [[ ! "${max_new_runs}" =~ ^[1-9][0-9]*$ ]] \
  || [[ ! "${max_api_calls}" =~ ^[1-9][0-9]*$ ]]; then
  echo "Batch id, max-new-runs, or API call limit is invalid." >&2
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
  if [[ -f "${nonretry_manifest}" ]] && "${eval_python}" - "${nonretry_manifest}" "${batch_id}" "${instance_id}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    entries = json.load(handle).get("entries", [])
for entry in entries:
    if entry.get("batch_id") == sys.argv[2] and entry.get("instance_id") == sys.argv[3]:
        raise SystemExit(0)
raise SystemExit(1)
PY
  then
    echo "skip_nonretry_after_model_response=${instance_id}"
    continue
  fi

  if "${eval_python}" - "${repo_root}/outputs/traces" "${batch_id}" "${instance_id}" <<'PY'
import json
import pathlib
import sys

for path in pathlib.Path(sys.argv[1]).glob(f"{sys.argv[2]}_*/scorecards.json"):
    for card in json.loads(path.read_text(encoding="utf-8")):
        if card.get("instance_id") == sys.argv[3]:
            raise SystemExit(0)
raise SystemExit(1)
PY
  then
    echo "skip_evaluated=${instance_id}"
    continue
  fi

  run_id="${batch_id}_${instance_id//__/_}"
  if [[ -f "${zero_response_retry_manifest}" ]]; then
    retry_run_id="$("${eval_python}" - "${zero_response_retry_manifest}" "${batch_id}" "${instance_id}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    entries = json.load(handle).get("entries", [])
for entry in entries:
    if entry.get("batch_id") == sys.argv[2] and entry.get("instance_id") == sys.argv[3]:
        print(entry["retry_run_id"])
        break
PY
)"
    if [[ -n "${retry_run_id}" ]]; then
      run_id="${retry_run_id}"
      echo "authorized_zero_model_response_retry=${instance_id} run_id=${run_id}"
    fi
  fi
  trace_root="${repo_root}/outputs/traces/${run_id}"
  if ! find "${trace_root}" -maxdepth 1 -name '*.traj' -print -quit 2>/dev/null | grep -q .; then
    SWE_AGENT_MAX_API_CALLS="${max_api_calls}" \
      "${repo_root}/scripts/run_local_api_instance.sh" \
      "${instance_id}" "${model_name}" "${run_id}"
  else
    echo "reuse_trajectory=${instance_id}"
  fi

  HTTP_PROXY="${HTTP_PROXY:-http://127.0.0.1:10808}" \
  HTTPS_PROXY="${HTTPS_PROXY:-http://127.0.0.1:10808}" \
    "${eval_python}" "${repo_root}/scripts/run_local_evaluation.py" \
    "${trace_root}/all_preds.jsonl" \
    --results "${repo_root}/outputs/evaluation/${run_id}" \
    --testbed "${eval_testbed}" \
    --timeout 900

  started=$((started + 1))
  if [[ "${started}" -ge "${max_new_runs}" ]]; then
    break
  fi
done

echo "new_runs=${started}"
