#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
secret_file="${SWE_AGENT_SECRET_FILE:-${repo_root}/secrets/openai.env}"
instance_id="${1:-sqlfluff__sqlfluff-1625}"
model_name="${2:-gpt-5.6-terra}"
run_id="${3:-api_pilot_$(date +%Y%m%d_%H%M%S)}"
max_api_calls="${SWE_AGENT_MAX_API_CALLS:-8}"
container_proxy="${SWE_AGENT_CONTAINER_PROXY:-http://127.0.0.1:10808}"

if [[ ! -f "${secret_file}" ]]; then
  echo "Secret environment file not found: ${secret_file}" >&2
  exit 2
fi

if [[ ! "${instance_id}" =~ ^[A-Za-z0-9_.-]+$ ]] \
  || [[ ! "${model_name}" =~ ^[A-Za-z0-9_.-]+$ ]] \
  || [[ ! "${run_id}" =~ ^[A-Za-z0-9_.-]+$ ]] \
  || [[ ! "${max_api_calls}" =~ ^[1-9][0-9]*$ ]]; then
  echo "Instance, model, run id, or API call limit has an invalid format." >&2
  exit 2
fi

set -a
source "${secret_file}"
set +a

if [[ -z "${OPENAI_API_KEY:-}" || -z "${OPENAI_BASE_URL:-}" ]]; then
  echo "OPENAI_API_KEY and OPENAI_BASE_URL are required." >&2
  exit 2
fi
if [[ ! "${OPENAI_API_KEY}" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "OPENAI_API_KEY contains unsupported characters for keys.cfg materialization." >&2
  exit 2
fi

api_base="${OPENAI_BASE_URL%/}"
if [[ "${api_base}" != */v1 ]]; then
  api_base="${api_base}/v1"
fi

patch_id="$(sha256sum "${repo_root}/patches/sweagent_local_api.patch" | cut -c1-12)"
runtime_root="${repo_root}/tmp/runtime/SWE-agent-local-${patch_id}"
log_dir="${repo_root}/outputs/logs"
trace_dir="${repo_root}/outputs/traces/${run_id}"
setup_log="${log_dir}/${run_id}_runtime_setup.log"
attempt_stamp="$(date -u +%Y%m%dT%H%M%SZ)"
run_log="${log_dir}/${run_id}_${attempt_stamp}.log"
latest_run_log="${log_dir}/${run_id}.log"

mkdir -p "${log_dir}" "${trace_dir}"
trap 'if [[ -f "${run_log}" ]]; then cp -f "${run_log}" "${latest_run_log}"; fi' EXIT
"${repo_root}/scripts/prepare_local_runtime.sh" "${runtime_root}" >"${setup_log}" 2>&1

umask 077
printf "OPENAI_API_KEY: '%s'\nOPENAI_API_BASE_URL: '%s'\n" \
  "${OPENAI_API_KEY}" "${api_base}" >"${runtime_root}/keys.cfg"

export SWE_AGENT_CONTAINER_PROXY="${container_proxy}"
export SWE_AGENT_DOCKER_NETWORK="host"
export SWE_AGENT_COMPAT_YANKED_PACKAGES="1"
export SWE_AGENT_MAX_API_CALLS="${max_api_calls}"

cd "${runtime_root}"
set -o pipefail
"${HOME}/.venvs/sweagent-paper/bin/python" run.py \
  --model_name "${model_name}" \
  --data_path princeton-nlp/SWE-bench_Lite \
  --split dev \
  --instance_filter "^${instance_id}$" \
  --config_file config/default.yaml \
  --per_instance_cost_limit 0 \
  --total_cost_limit 0 \
  --temperature 0.0 \
  --top_p 0.95 \
  --suffix "${run_id}" \
  --skip_existing false \
  2>&1 | tee "${run_log}"

trajectory_root="$(find trajectories -type d -name "*__${run_id}" -print -quit)"
trajectory_file="${trajectory_root}/${instance_id}.traj"
predictions_file="${trajectory_root}/all_preds.jsonl"
if [[ -z "${trajectory_root}" ]] \
  || [[ ! -s "${trajectory_file}" ]] \
  || [[ ! -s "${predictions_file}" ]]; then
  echo "Complete trajectory and predictions were not produced for ${run_id}." >&2
  exit 1
fi

cp -a "${trajectory_root}/." "${trace_dir}/"
printf 'run_id=%s\ninstance_id=%s\nmodel=%s\nmax_api_calls=%s\nruntime_patch=%s\n' \
  "${run_id}" "${instance_id}" "${model_name}" "${max_api_calls}" "${patch_id}" \
  >"${trace_dir}/run_manifest.txt"

echo "run_id=${run_id}"
echo "trace_dir=${trace_dir}"
