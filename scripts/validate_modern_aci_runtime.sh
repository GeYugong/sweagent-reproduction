#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${HOME}/.venvs/sweagent-paper/bin/python"
patch_id="$(sha256sum "${repo_root}/patches/sweagent_local_api.patch" | cut -c1-12)"
runtime_root="${repo_root}/tmp/runtime/SWE-agent-local-${patch_id}"

if [[ ! -x "${python_bin}" ]]; then
  echo "SWE-agent Python environment is missing: ${python_bin}" >&2
  exit 2
fi

"${python_bin}" "${repo_root}/scripts/materialize_modern_aci_variants.py"
"${repo_root}/scripts/prepare_local_runtime.sh" "${runtime_root}"

mkdir -p "${runtime_root}/config/modern_aci" "${runtime_root}/config/commands"
cp "${repo_root}"/conf/modern_aci/generated/*.yaml \
  "${runtime_root}/config/modern_aci/"
cp "${repo_root}"/conf/modern_aci/commands/*.sh \
  "${runtime_root}/config/commands/"

"${python_bin}" "${repo_root}/scripts/validate_modern_aci_runtime.py" \
  --runtime-root "${runtime_root}"
"${python_bin}" "${repo_root}/scripts/materialize_modern_aci_variants.py"
"${python_bin}" "${repo_root}/scripts/materialize_modern_aci_variants.py" --check

echo "runtime_validation=data/manifests/modern_aci_runtime_validation.json"
echo "pairing_manifest=data/manifests/modern_aci_dev20_pairing.json"
