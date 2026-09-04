#!/usr/bin/env bash
set -euo pipefail

# Build all Flask projects with PyInstaller
# Usage: ./build_all.sh [--clean]

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../" && pwd)"
DIST_ROOT="$ROOT/dist"
VENV_DIR=".venv-pyinstaller"
PYTHON_VERSION=${PYTHON_VERSION:-3}
CLEAN=false

if [[ "${1:-}" == "--clean" ]]; then
  CLEAN=true
fi

mkdir -p "$DIST_ROOT"

# Projects to build (name:path)
declare -A PROJECTS=(
  [bfc]="$ROOT/projects/bfc"
  [diarix]="$ROOT/projects/diarix"
  [vd]="$ROOT/projects/vd"
)

# Ensure pyinstaller available
install_venv() {
  if [[ ! -d "$ROOT/$VENV_DIR" ]]; then
    python3 -m venv "$ROOT/$VENV_DIR"
  fi
  # shellcheck source=/dev/null
  source "$ROOT/$VENV_DIR/bin/activate"
  pip install --upgrade pip setuptools wheel
  pip install pyinstaller
}

build_project() {
  local name="$1"
  local path="$2"

  echo "\n=== Building $name from $path ==="
  pushd "$path" > /dev/null

  if [[ -f requirements.txt ]]; then
    pip install -q -r requirements.txt || true
  fi

  # Prepare add-data flags for templates/static if present
  local add_data_args=()
  if [[ -d "$path/templates" ]]; then
    add_data_args+=("--add-data" "templates:templates")
  fi
  if [[ -d "$path/static" ]]; then
    add_data_args+=("--add-data" "static:static")
  fi

  # Clean previous build artifacts
  rm -rf build dist "${name}.spec"

  # Dist output dir specific per project
  local outdir="$DIST_ROOT/${name}-$RUNNER_OS"
  mkdir -p "$outdir"

  # Build one-file executable
  pyinstaller --noconfirm --onefile --name "$name" "app.py" --distpath "$outdir" "${add_data_args[@]:+${add_data_args[@]}}"

  popd > /dev/null
}

main() {
  echo "Using root: $ROOT"
  install_venv

  for name in "${!PROJECTS[@]}"; do
    build_project "$name" "${PROJECTS[$name]}"
  done

  echo "\nBuild complete. Artifacts are in: $DIST_ROOT"
  ls -la "$DIST_ROOT" || true
}

main "$@"
