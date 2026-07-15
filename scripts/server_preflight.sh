#!/usr/bin/env bash
set -u

printf 'timestamp_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'hostname=%s\n' "$(hostname)"
printf 'user=%s\n' "$(whoami)"
printf 'pwd=%s\n' "$(pwd)"
printf 'git_commit=%s\n' "$(git rev-parse HEAD 2>/dev/null || printf unavailable)"
printf 'python=%s\n' "$(python3 --version 2>&1 || true)"
printf 'git=%s\n' "$(git --version 2>&1 || true)"
printf 'cpu_count=%s\n' "$(nproc 2>/dev/null || true)"

printf '\n[filesystem]\n'
df -h . || true

printf '\n[memory]\n'
free -h || true

printf '\n[gpus]\n'
nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu,driver_version \
  --format=csv,noheader || true

printf '\n[container_backends]\n'
for command_name in docker podman apptainer singularity enroot; do
  if command -v "${command_name}" >/dev/null 2>&1; then
    printf '%s=%s\n' "${command_name}" "$(command -v "${command_name}")"
  else
    printf '%s=unavailable\n' "${command_name}"
  fi
done

printf '\n[schedulers]\n'
for command_name in srun sbatch sinfo; do
  if command -v "${command_name}" >/dev/null 2>&1; then
    printf '%s=%s\n' "${command_name}" "$(command -v "${command_name}")"
  else
    printf '%s=unavailable\n' "${command_name}"
  fi
done
