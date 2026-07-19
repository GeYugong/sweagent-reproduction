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

model_api_call_count() {
  local run_id="$1"
  local log_path="${repo_root}/outputs/logs/${run_id}.log"
  "${eval_python}" - "${log_path}" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    print(0)
    raise SystemExit(0)
matches = re.findall(r"total_api_calls=(\d+)", path.read_text(encoding="utf-8", errors="replace"))
print(matches[-1] if matches else 0)
PY
}

record_nonretry_terminal_failure() {
  local batch_id="$1"
  local instance_id="$2"
  local classification="$3"
  local reason="$4"
  "${eval_python}" - "${nonretry_manifest}" "${batch_id}" "${instance_id}" "${classification}" "${reason}" <<'PY'
import json
import os
import sys
import tempfile
from datetime import date

path, batch_id, instance_id, classification, reason = sys.argv[1:]
with open(path, encoding="utf-8") as handle:
    payload = json.load(handle)
entries = payload.setdefault("entries", [])
if not any(entry.get("batch_id") == batch_id and entry.get("instance_id") == instance_id for entry in entries):
    entries.append({
        "batch_id": batch_id,
        "instance_id": instance_id,
        "classification": classification,
        "date": date.today().isoformat(),
        "reason": reason,
    })
directory = os.path.dirname(path)
fd, temporary = tempfile.mkstemp(prefix=".nonretry-", dir=directory, text=True)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
}

authorize_zero_response_retry() {
  local batch_id="$1"
  local instance_id="$2"
  local original_run_id="$3"
  local retry_run_id="$4"
  local reason="$5"
  "${eval_python}" - "${zero_response_retry_manifest}" "${batch_id}" "${instance_id}" "${original_run_id}" "${retry_run_id}" "${reason}" <<'PY'
import json
import os
import sys
import tempfile
from datetime import date

path, batch_id, instance_id, original_run_id, retry_run_id, reason = sys.argv[1:]
with open(path, encoding="utf-8") as handle:
    payload = json.load(handle)
entries = payload.setdefault("entries", [])
if not any(entry.get("batch_id") == batch_id and entry.get("instance_id") == instance_id for entry in entries):
    entries.append({
        "batch_id": batch_id,
        "instance_id": instance_id,
        "original_run_id": original_run_id,
        "retry_run_id": retry_run_id,
        "classification": "ZERO_MODEL_RESPONSE_INFRASTRUCTURE_FAILURE",
        "date": date.today().isoformat(),
        "reason": reason,
    })
directory = os.path.dirname(path)
fd, temporary = tempfile.mkstemp(prefix=".zero-response-", dir=directory, text=True)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
}

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

  # A previous process can have terminated after model responses but before the
  # trace directory was copied into outputs/.  Inspect the durable run log
  # before launching a replacement container so resuming a batch never repeats
  # already-billed model interaction.
  existing_trace_root="${repo_root}/outputs/traces/${run_id}"
  if [[ ! -s "${existing_trace_root}/all_preds.jsonl" ]]; then
    existing_api_calls="$(model_api_call_count "${run_id}")"
    if [[ "${existing_api_calls}" -gt 0 ]]; then
      record_nonretry_terminal_failure "${batch_id}" "${instance_id}" \
        "MODEL_RESPONSE_NO_PREDICTION_NO_RETRY" \
        "The retained run log contains ${existing_api_calls} persisted model responses but no all_preds.jsonl. The frozen protocol forbids retries after any model response."
      echo "classified_existing_nonretry_no_prediction=${instance_id} api_calls=${existing_api_calls}"
      continue
    fi
  fi

  while true; do
    trace_root="${repo_root}/outputs/traces/${run_id}"
    if ! find "${trace_root}" -maxdepth 1 -name '*.traj' -print -quit 2>/dev/null | grep -q .; then
      if ! SWE_AGENT_MAX_API_CALLS="${max_api_calls}" \
        "${repo_root}/scripts/run_local_api_instance.sh" \
        "${instance_id}" "${model_name}" "${run_id}"; then
        echo "agent_run_failed=${instance_id} run_id=${run_id}"
      fi
    else
      echo "reuse_trajectory=${instance_id}"
    fi

    if [[ ! -s "${trace_root}/all_preds.jsonl" ]]; then
      api_calls="$(model_api_call_count "${run_id}")"
      if [[ "${api_calls}" -gt 0 ]]; then
        record_nonretry_terminal_failure "${batch_id}" "${instance_id}" \
          "MODEL_RESPONSE_NO_PREDICTION_NO_RETRY" \
          "The agent produced ${api_calls} persisted model responses but did not generate all_preds.jsonl before termination. The frozen protocol forbids retries after any model response."
        echo "classified_nonretry_no_prediction=${instance_id} api_calls=${api_calls}"
        break
      fi
      if [[ "${run_id}" == *_attempt_2 ]]; then
        record_nonretry_terminal_failure "${batch_id}" "${instance_id}" \
          "ZERO_MODEL_RESPONSE_RETRY_EXHAUSTED_NO_RETRY" \
          "The original and the single authorized retry both ended without a model response or prediction."
        echo "classified_nonretry_zero_response_retry_exhausted=${instance_id}"
        break
      fi
      retry_run_id="${run_id}_attempt_2"
      authorize_zero_response_retry "${batch_id}" "${instance_id}" "${run_id}" "${retry_run_id}" \
        "The original attempt ended without a model response, trajectory, prediction, or evaluator result. One retained-attempt retry is authorized automatically by the frozen protocol."
      echo "authorized_zero_model_response_retry=${instance_id} run_id=${retry_run_id}"
      run_id="${retry_run_id}"
      continue
    fi

    if ! HTTP_PROXY="${HTTP_PROXY:-http://127.0.0.1:10808}" \
      HTTPS_PROXY="${HTTPS_PROXY:-http://127.0.0.1:10808}" \
      "${eval_python}" "${repo_root}/scripts/run_local_evaluation.py" \
      "${trace_root}/all_preds.jsonl" \
      --results "${repo_root}/outputs/evaluation/${run_id}" \
      --testbed "${eval_testbed}" \
      --timeout 900; then
      api_calls="$(model_api_call_count "${run_id}")"
      record_nonretry_terminal_failure "${batch_id}" "${instance_id}" \
        "MODEL_RESPONSE_EVALUATOR_FAILURE_NO_RETRY" \
        "Evaluation exited non-zero after ${api_calls} persisted model responses. The frozen protocol forbids retries after any model response."
      echo "classified_nonretry_evaluator_failure=${instance_id} api_calls=${api_calls}"
    fi
    break
  done

  started=$((started + 1))
  if [[ "${started}" -ge "${max_new_runs}" ]]; then
    break
  fi
done

echo "new_runs=${started}"
