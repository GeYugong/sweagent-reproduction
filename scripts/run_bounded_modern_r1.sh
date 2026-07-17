#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${HOME}/.venvs/sweagent-paper/bin/python"
model_name="${1:-gpt-5.6-terra}"
mode="${2:-plan}"

if [[ "${mode}" != "plan" && "${mode}" != "execute" ]]; then
  echo "Usage: $0 [model] [plan|execute]" >&2
  exit 2
fi
if [[ ! -x "${python_bin}" ]]; then
  echo "SWE-agent Python environment is missing: ${python_bin}" >&2
  exit 2
fi
"${python_bin}" "${repo_root}/scripts/materialize_bounded_modern_r1.py" --check

if [[ "${mode}" == "plan" ]]; then
  "${python_bin}" - "${repo_root}/data/manifests/bounded_modern_r1_plan.json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    plan = json.load(handle)
print(f"status={plan['status']}")
print(f"batches={len(plan['batches'])}")
print(f"new_episode_count={plan['execution']['new_episode_count']}")
print(f"hard_max_api_calls={plan['execution']['hard_max_api_calls']}")
print("model_api_calls=0")
PY
  exit 0
fi
if [[ "${SWE_AGENT_BOUNDED_R1_AUTHORIZATION:-}" != "APPROVED" ]]; then
  echo "Set SWE_AGENT_BOUNDED_R1_AUTHORIZATION=APPROVED to start R1." >&2
  exit 2
fi

while IFS=$'\t' read -r configuration batch_id manifest config_source asset_dir instance_count; do
  echo "starting_batch=${batch_id} configuration=${configuration} instances=${instance_count}"
  if [[ "${config_source}" == "-" ]]; then
    "${repo_root}/scripts/run_local_api_batch.sh" "${repo_root}/${manifest}" "${model_name}" "${batch_id}" "${instance_count}" 25
  else
    SWE_AGENT_CONFIG_SOURCE="${repo_root}/${config_source}" \
    SWE_AGENT_CONFIG_ASSET_DIR="${repo_root}/${asset_dir}" \
      "${repo_root}/scripts/run_local_api_batch.sh" "${repo_root}/${manifest}" "${model_name}" "${batch_id}" "${instance_count}" 25
  fi
  "${python_bin}" "${repo_root}/scripts/assess_bounded_modern_budget.py" --stage R1
done < <("${python_bin}" - "${repo_root}/data/manifests/bounded_modern_r1_plan.json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    plan = json.load(handle)
for batch in plan["batches"]:
    print("\t".join([
        batch["configuration_id"],
        batch["batch_id"],
        batch["instance_manifest"]["path"],
        batch["config_source"] or "-",
        batch["config_asset_dir"] or "-",
        str(batch["instance_count"]),
    ]))
PY
)
