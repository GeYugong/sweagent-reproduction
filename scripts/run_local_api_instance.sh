#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
secret_file="${SWE_AGENT_SECRET_FILE:-${repo_root}/secrets/openai.env}"
instance_id="${1:-sqlfluff__sqlfluff-1625}"
model_name="${2:-gpt-5.6-terra}"
run_id="${3:-api_pilot_$(date +%Y%m%d_%H%M%S)}"
max_api_calls="${SWE_AGENT_MAX_API_CALLS:-8}"
container_proxy="${SWE_AGENT_CONTAINER_PROXY:-http://127.0.0.1:10808}"
config_file="${SWE_AGENT_CONFIG_FILE:-config/default.yaml}"
config_source="${SWE_AGENT_CONFIG_SOURCE:-}"
config_asset_dir="${SWE_AGENT_CONFIG_ASSET_DIR:-}"

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

repo_root_abs="$(realpath "${repo_root}")"
config_source_record="upstream_default"
if [[ -n "${config_source}" ]]; then
  if [[ ! -f "${config_source}" ]]; then
    echo "SWE-agent config source not found: ${config_source}" >&2
    exit 2
  fi
  config_source_abs="$(realpath "${config_source}")"
  case "${config_source_abs}" in
    "${repo_root_abs}"/*) ;;
    *)
      echo "SWE-agent config source must remain under the project root." >&2
      exit 2
      ;;
  esac
  cp "${config_source_abs}" "${runtime_root}/config/local_experiment.yaml"
  config_file="config/local_experiment.yaml"
  config_source_record="$(realpath --relative-to="${repo_root_abs}" "${config_source_abs}")"
fi

config_asset_records=()
if [[ -n "${config_asset_dir}" ]]; then
  if [[ ! -d "${config_asset_dir}" ]]; then
    echo "SWE-agent config asset directory not found: ${config_asset_dir}" >&2
    exit 2
  fi
  config_asset_dir_abs="$(realpath "${config_asset_dir}")"
  case "${config_asset_dir_abs}" in
    "${repo_root_abs}"/*) ;;
    *)
      echo "SWE-agent config assets must remain under the project root." >&2
      exit 2
      ;;
  esac
  shopt -s nullglob
  config_assets=("${config_asset_dir_abs}"/*.sh)
  shopt -u nullglob
  if [[ "${#config_assets[@]}" -eq 0 ]]; then
    echo "No shell command assets found in ${config_asset_dir_abs}." >&2
    exit 2
  fi
  for asset in "${config_assets[@]}"; do
    asset_name="$(basename "${asset}")"
    if [[ ! "${asset_name}" =~ ^[A-Za-z0-9._-]+\.sh$ ]]; then
      echo "Unsupported command asset name: ${asset_name}" >&2
      exit 2
    fi
    cp "${asset}" "${runtime_root}/config/commands/${asset_name}"
    config_asset_records+=("${asset_name}=$(sha256sum "${asset}" | cut -d' ' -f1)")
  done
fi

umask 077
printf "OPENAI_API_KEY: '%s'\nOPENAI_API_BASE_URL: '%s'\n" \
  "${OPENAI_API_KEY}" "${api_base}" >"${runtime_root}/keys.cfg"

export SWE_AGENT_CONTAINER_PROXY="${container_proxy}"
export SWE_AGENT_DOCKER_NETWORK="host"
export SWE_AGENT_COMPAT_YANKED_PACKAGES="1"
export SWE_AGENT_MAX_API_CALLS="${max_api_calls}"

cd "${runtime_root}"
if [[ ! -f "${config_file}" ]]; then
  echo "SWE-agent config file not found: ${config_file}" >&2
  exit 2
fi
config_sha256="$(sha256sum "${config_file}" | cut -d' ' -f1)"
set -o pipefail
"${HOME}/.venvs/sweagent-paper/bin/python" run.py \
  --model_name "${model_name}" \
  --data_path princeton-nlp/SWE-bench_Lite \
  --split dev \
  --instance_filter "^${instance_id}$" \
  --config_file "${config_file}" \
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
{
  printf 'run_id=%s\ninstance_id=%s\nmodel=%s\nmax_api_calls=%s\nruntime_patch=%s\n' \
    "${run_id}" "${instance_id}" "${model_name}" "${max_api_calls}" "${patch_id}"
  printf 'config_source=%s\nconfig_sha256=%s\n' \
    "${config_source_record}" "${config_sha256}"
  for asset_record in "${config_asset_records[@]}"; do
    printf 'config_asset=%s\n' "${asset_record}"
  done
} >"${trace_dir}/run_manifest.txt"

echo "run_id=${run_id}"
echo "trace_dir=${trace_dir}"
