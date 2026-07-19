#!/usr/bin/env bash
# Idempotent R2--R4 supervisor. Safe to rerun after a terminal or host restart.
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${HOME}/.venvs/sweagent-paper/bin/python"
model_name="${1:-gpt-5.6-terra}"
mode="${2:-plan}"
max_batch_restarts="${SWE_AGENT_MAX_BATCH_RESTARTS:-3}"

if [[ "${mode}" != "plan" && "${mode}" != "execute" ]]; then
  echo "Usage: $0 [model] [plan|execute]" >&2
  exit 2
fi
if [[ ! -x "${python_bin}" || ! "${max_batch_restarts}" =~ ^[1-9][0-9]*$ ]]; then
  echo "Missing Python runtime or invalid batch restart limit." >&2
  exit 2
fi
if [[ "${mode}" == "execute" && "${SWE_AGENT_BOUNDED_R1_AUTHORIZATION:-}" != "APPROVED" ]]; then
  echo "Set SWE_AGENT_BOUNDED_R1_AUTHORIZATION=APPROVED to start R2--R4." >&2
  exit 2
fi

for stage in R2 R3 R4; do
  "${python_bin}" "${repo_root}/scripts/materialize_bounded_modern_stage.py" --stage "${stage}"
  plan_path="${repo_root}/data/manifests/bounded_modern_${stage,,}_plan.json"
  if [[ "${mode}" == "plan" ]]; then
    echo "stage=${stage} plan=${plan_path} model_api_calls=0"
    continue
  fi
  while IFS=$'\t' read -r configuration batch_id manifest config_source asset_dir instance_count; do
    attempt=1
    while true; do
      echo "starting_stage=${stage} batch=${batch_id} configuration=${configuration} supervisor_attempt=${attempt}"
      if [[ "${config_source}" == "-" ]]; then
        "${repo_root}/scripts/run_local_api_batch.sh" "${repo_root}/${manifest}" "${model_name}" "${batch_id}" "${instance_count}" 25 && break
      else
        SWE_AGENT_CONFIG_SOURCE="${repo_root}/${config_source}" SWE_AGENT_CONFIG_ASSET_DIR="${repo_root}/${asset_dir}" \
          "${repo_root}/scripts/run_local_api_batch.sh" "${repo_root}/${manifest}" "${model_name}" "${batch_id}" "${instance_count}" 25 && break
      fi
      if [[ "${attempt}" -ge "${max_batch_restarts}" ]]; then
        echo "batch_restart_exhausted stage=${stage} batch=${batch_id}" >&2
        exit 1
      fi
      attempt=$((attempt + 1))
      echo "batch_restart_scheduled stage=${stage} batch=${batch_id} next_attempt=${attempt}" >&2
      sleep 60
    done
  done < <("${python_bin}" - "${plan_path}" <<'PY'
import json
import sys
for batch in json.load(open(sys.argv[1], encoding="utf-8"))["batches"]:
    print("\t".join([
        batch["configuration_id"], batch["batch_id"], batch["instance_manifest"]["path"],
        batch["config_source"] or "-", batch["config_asset_dir"] or "-", str(batch["instance_count"]),
    ]))
PY
)
  "${python_bin}" "${repo_root}/scripts/assess_bounded_modern_budget.py" --stage "${stage}"
  echo "completed_stage=${stage}"
done
