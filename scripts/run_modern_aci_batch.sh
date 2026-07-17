#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${HOME}/.venvs/sweagent-paper/bin/python"
variant_id="${1:-}"
model_name="${2:-gpt-5.6-terra}"
max_new_runs="${3:-1}"
max_api_calls="${4:-25}"
mode="${5:-plan}"
definitions="${repo_root}/conf/modern_aci/variants.yaml"
pairing="${repo_root}/data/manifests/modern_aci_dev20_pairing.json"

if [[ ! "${variant_id}" =~ ^[a-z0-9_]+$ ]] \
  || [[ ! "${max_new_runs}" =~ ^[1-9][0-9]*$ ]] \
  || [[ ! "${max_api_calls}" =~ ^[1-9][0-9]*$ ]] \
  || [[ "${mode}" != "plan" && "${mode}" != "execute" ]]; then
  echo "Usage: $0 <variant> [model] [max-new-runs] [max-api-calls] [plan|execute]" >&2
  exit 2
fi
if [[ ! -x "${python_bin}" ]]; then
  echo "SWE-agent Python environment is missing: ${python_bin}" >&2
  exit 2
fi

"${python_bin}" "${repo_root}/scripts/materialize_modern_aci_variants.py" --check
config_relative="$("${python_bin}" - "${definitions}" "${variant_id}" <<'PY'
import sys
import yaml

with open(sys.argv[1], encoding="utf-8") as handle:
    definitions = yaml.safe_load(handle)
for variant in definitions["variants"]:
    if variant["id"] == sys.argv[2]:
        print(variant["config"])
        raise SystemExit(0)
raise SystemExit(f"Unknown modern ACI variant: {sys.argv[2]}")
PY
)"
config_source="${repo_root}/${config_relative}"
batch_id="modern_aci_${variant_id}"

"${python_bin}" - "${pairing}" "${variant_id}" "${max_new_runs}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    pairing = json.load(handle)
variant_id = sys.argv[2]
requested = int(sys.argv[3])
rows = [row for row in pairing["planned_runs"] if row["variant_id"] == variant_id]
if pairing["status"] != "READY_BLOCKED_PRICE_AND_BUDGET":
    raise SystemExit(f"Pairing manifest is not technically ready: {pairing['status']}")
if len(rows) != 20:
    raise SystemExit(f"Expected 20 planned rows for {variant_id}, found {len(rows)}")
if requested > len(rows):
    raise SystemExit(f"max-new-runs cannot exceed {len(rows)}")
projection = pairing["baseline_projection_lower_bounds"]
print(f"variant={variant_id}")
print(f"planned_instances={len(rows)}")
print(f"requested_new_runs={requested}")
print(f"projected_input_tokens_per_episode_lower_bound={projection['projected_input_tokens'] / 160:.2f}")
print(f"projected_output_tokens_per_episode_lower_bound={projection['projected_output_tokens'] / 160:.2f}")
print("pricing_status=UNKNOWN_IN_FROZEN_MANIFEST")
PY

if [[ "${mode}" == "plan" ]]; then
  echo "mode=plan"
  echo "model_api_calls=0"
  echo "execution requires explicit prices, a per-invocation budget ceiling, and SWE_AGENT_PAID_RUN_AUTHORIZATION=APPROVED"
  exit 0
fi

if [[ "${SWE_AGENT_PAID_RUN_AUTHORIZATION:-}" != "APPROVED" ]]; then
  echo "Paid execution is not authorized for this invocation." >&2
  exit 2
fi
for name in SWE_AGENT_INPUT_PRICE_PER_MILLION SWE_AGENT_OUTPUT_PRICE_PER_MILLION SWE_AGENT_INVOCATION_BUDGET_USD; do
  value="${!name:-}"
  if [[ ! "${value}" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    echo "${name} must be a non-negative numeric value." >&2
    exit 2
  fi
done

budget_check="$("${python_bin}" - \
  "${SWE_AGENT_INPUT_PRICE_PER_MILLION}" \
  "${SWE_AGENT_OUTPUT_PRICE_PER_MILLION}" \
  "${SWE_AGENT_INVOCATION_BUDGET_USD}" \
  "${max_new_runs}" <<'PY'
from decimal import Decimal
import sys

input_price, output_price, ceiling = map(Decimal, sys.argv[1:4])
episodes = Decimal(sys.argv[4])
input_tokens = Decimal("274847.35") * episodes
output_tokens = Decimal("3520.25") * episodes
estimate = input_tokens / Decimal(1_000_000) * input_price
estimate += output_tokens / Decimal(1_000_000) * output_price
guarded = estimate * Decimal("1.25")
if ceiling < guarded:
    raise SystemExit(
        f"Invocation ceiling ${ceiling} is below the 1.25x projected lower-bound cost ${guarded:.4f}"
    )
print(f"projected_cost_lower_bound_usd={estimate:.4f}")
print(f"guarded_projection_usd={guarded:.4f}")
print(f"invocation_budget_ceiling_usd={ceiling:.4f}")
PY
)"
echo "${budget_check}"

SWE_AGENT_CONFIG_SOURCE="${config_source}" \
SWE_AGENT_CONFIG_ASSET_DIR="${repo_root}/conf/modern_aci/commands" \
  "${repo_root}/scripts/run_local_api_batch.sh" \
  "${repo_root}/data/manifests/swebench_lite_dev20_seed42.json" \
  "${model_name}" "${batch_id}" "${max_new_runs}" "${max_api_calls}"
