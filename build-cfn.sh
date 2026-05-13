#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${REPO_ROOT}/upload/cfn-ecr-aws-soci-index-builder"
FUNCTIONS_SOURCE="${REPO_ROOT}/functions/source"
FUNCTIONS_PACKAGES="${REPO_ROOT}/functions/packages"

build_function() {
  local func_name="$1"
  local func_path="${FUNCTIONS_SOURCE}/${func_name}"
  local output_path="${FUNCTIONS_PACKAGES}/${func_name}"

  if [[ ! -d "${func_path}" ]]; then
    echo "error: function directory not found: ${func_path}" >&2
    return 1
  fi

  echo "Building ${func_name}..."

  if [[ -f "${func_path}/Dockerfile" ]]; then
    # Docker-based build (Go lambda)
    local image_tag="lambda-build-$(date +%s)"
    docker build --platform linux/amd64 -t "${image_tag}" "${func_path}" >/dev/null
    mkdir -p "${output_path}"
    docker run --rm --platform linux/amd64 \
      -v "${output_path}:/output" \
      "${image_tag}"
    docker rmi "${image_tag}"
    echo "  ✓ extracted to ${output_path}"
  else
    # Direct zip (no build)
    mkdir -p "${output_path}"
    cd "${func_path}"
    zip -r "${output_path}/lambda.zip" . >/dev/null
    cd - >/dev/null
    echo "  ✓ zipped to ${output_path}/lambda.zip"
  fi
}

main() {
  mkdir -p "${FUNCTIONS_PACKAGES}"
  for func_dir in "${FUNCTIONS_SOURCE}"/*; do
    if [[ -d "${func_dir}" ]]; then
      func_name=$(basename "${func_dir}")
      build_function "${func_name}" || exit 1
    fi
  done

  mkdir -p "${TARGET_DIR}/functions/packages"
  cp -r "${FUNCTIONS_PACKAGES}/." "${TARGET_DIR}/functions/packages"
  cp -r templates "${TARGET_DIR}/"

  echo "Done. Upload the contents of ${TARGET_DIR} to an S3 bucket for CFN deployment."
}

main "$@"
