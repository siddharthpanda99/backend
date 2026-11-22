#!/usr/bin/env bash
# One-shot "stop → install → start" for the Nexus Runtime Execution Fabric on the HOST.
#
# The fabric is a *separate* server from the platform backend (clean_start.sh):
# it lives in toolchains/ as isolated per-modality venvs so wildly different
# dependency universes (image diffusion, audio TTS/music, voice) never fight each
# other or the backend. This script therefore manages ONLY the venvs under
# toolchains/ and NEVER the backend .venv or any Docker image.
#
# Layout it provisions:
#   toolchains/fabric/.venv    — control-plane venv (fastapi/uvicorn/httpx/pydantic
#                                + editable common_lib --no-deps); serves :8001
#   toolchains/image-sdcli/.venv — GGUF/Vulkan image worker venv (sd-cli does the
#                                diffusion work; no torch — fastapi/uvicorn/httpx/pydantic
#                                + editable common_lib --no-deps)
#   toolchains/image/.venv     — native image worker venv (torch+diffusers):
#                                torch 2.6+cu124, torchvision, editable common_lib
#   toolchains/{ace-step,cosyvoice,fish-speech,seed-vc,stable-audio}/.venv
#                             — created/empty; deps are NOT auto-installed unless
#                               --install-toolchains is passed (audio stacks are
#                               multi-GB and GPU/CUDA-index sensitive)
#
# Usage: ./run_fabric_host.sh [OPTIONS]
#   -p, --port PORT       Port to bind (default 8001, or $PORT).
#       --host HOST       Bind address (default 0.0.0.0, or $HOST).
#       --skip-install    Do not create/sync any venv (fast start for iteration).
#       --install-only    Provision venvs, print a status table, then exit.
#       --status          Print a disk/venv report and exit (no stop/install/start).
#       --install-toolchains
#                         Also attempt each audio toolchain's manifest
#                         (requirements.txt / pyproject -e) with torch pinned
#                         to the shared cu124 build via a constraints file.
#                         Best-effort: failures warn, they do not abort.
#   -h, --help            Show this help.
#
# Every default remains overridable by exporting the matching variable
# (NEXUS_TOOLCHAIN_VENVS, NEXUS_IMAGE_PYTHON, NEXUS_CONTROL_VENV, MOSS_SD_CLI, ...).

set -uo pipefail

PORT="${PORT:-8001}"
HOST="${HOST:-0.0.0.0}"
SKIP_INSTALL=0
INSTALL_ONLY=0
INSTALL_TOOLCHAINS=0
STATUS=0

usage() {
    cat <<'USAGE'
Usage: ./run_fabric_host.sh [OPTIONS]

One-shot "stop → install → start" for the fabric server (host mode).
Manages ONLY the venvs under toolchains/ — never the backend .venv.

Options:
  -p, --port PORT       Port to bind (default 8001).
      --host HOST       Bind address (default 0.0.0.0).
      --skip-install    Do not create/sync any venv (fast start for iteration).
      --install-only    Provision venvs, print a status report, then exit.
      --status          Print a disk/venv sharing report and exit
                        (nothing is stopped or started).
      --install-toolchains
                        Also provision the audio toolchain venvs
                        (requirements.txt / pyproject -e) with torch pinned
                        to the shared cu124 build via a generated constraints
                        file, so wheels hardlink from the uv cache instead of
                        duplicating CUDA libraries per toolchain.
                        Best-effort; failures warn only.
  -h, --help            Show this help.

Disk model: uv's cache is the single content-addressed store; every venv is
a view of it via hardlinks (UV_LINK_MODE=hardlink, enforced — uv fails rather
than silently copy). Shared wheels cost ~0 beyond the cache. Different
versions of the same package are what actually cost space; this script keeps
one index (cu124) and one torch across the venvs so sharing holds.

USAGE
}

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -p|--port)
            [[ "$#" -lt 2 ]] && { echo "ERROR: $1 requires a port number" >&2; exit 2; }
            PORT="$2"; shift ;;
        --port=*) PORT="${1#*=}" ;;
        --host)
            [[ "$#" -lt 2 ]] && { echo "ERROR: --host requires a value" >&2; exit 2; }
            HOST="$2"; shift ;;
        --host=*) HOST="${1#*=}" ;;
        --skip-install) SKIP_INSTALL=1 ;;
        --install-only) INSTALL_ONLY=1 ;;
        --status) STATUS=1 ;;
        --install-toolchains) INSTALL_TOOLCHAINS=1 ;;
        -h|--help) usage; exit 0 ;;
        -*) echo "ERROR: unknown option '$1'" >&2; usage >&2; exit 2 ;;
        *) echo "ERROR: unexpected argument '$1'" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

# --- Path resolution (location-independent) ------------------------------------
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
BACKEND_DIR="$SCRIPT_DIR"
MONOREPO="$(cd -- "$BACKEND_DIR/../.." && pwd -P)"
COMMON_LIB_PROJECT="$MONOREPO/Backend Monorepo/Python Libs/common_lib"
COMMON_LIB_SRC="$COMMON_LIB_PROJECT/src"
TOOLCHAINS_ROOT="$MONOREPO/toolchains"

export RESOURCES_ROOT="${RESOURCES_ROOT:-$MONOREPO/resources}"
export PORT HOST
export NEXUS_TOOLCHAIN_VENVS="${NEXUS_TOOLCHAIN_VENVS:-$TOOLCHAINS_ROOT}"
# echo/whisper workers run on the committed lightweight control venv
# (fastapi+uvicorn+httpx+pydantic + editable common_lib), never on the backend venv
export NEXUS_CONTROL_VENV="${NEXUS_CONTROL_VENV:-$TOOLCHAINS_ROOT/fabric/.venv}"
export COSYVOICE_MODEL_DIR="${COSYVOICE_MODEL_DIR:-$RESOURCES_ROOT/ai_models/audio/cosyvoice2-0.5b}"
export FISH_SPEECH_MODEL_DIR="${FISH_SPEECH_MODEL_DIR:-$RESOURCES_ROOT/ai_models/audio/fish-s2-pro}"
export NEXUS_TOOLCHAINS_ROOT="${NEXUS_TOOLCHAINS_ROOT:-$TOOLCHAINS_ROOT}"
export NEXUS_WORKDIR="${NEXUS_WORKDIR:-$MONOREPO}"
export NEXUS_CONTROL_SRC="${NEXUS_CONTROL_SRC:-$COMMON_LIB_SRC}"
export NEXUS_LOG_DIR="${NEXUS_LOG_DIR:-$MONOREPO/logs/runtime_fabric}"
export NEXUS_IMAGE_PYTHON="${NEXUS_TOOLCHAIN_VENVS}/image/.venv/bin/python"
export NEXUS_IMAGE_OUTPUT_DIR="${NEXUS_IMAGE_OUTPUT_DIR:-$MONOREPO/output/final-check}"
export NEXUS_AUDIO_OUTPUT_DIR="${NEXUS_AUDIO_OUTPUT_DIR:-$MONOREPO/output/audio}"
export NEXUS_CONTROL_URL="${NEXUS_CONTROL_URL:-http://127.0.0.1:8000}"
export PYTHONPATH="$COMMON_LIB_SRC:${PYTHONPATH:-}"

export MOSS_SD_CLI="${MOSS_SD_CLI:-$RESOURCES_ROOT/bin/sd-vulkan/sd-cli}"
export HF_HOME="${HF_HOME:-$RESOURCES_ROOT/hf-cache}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export MODEL_CPU_OFFLOAD="${MODEL_CPU_OFFLOAD:-1}"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
export no_proxy="127.0.0.1,localhost,::1${no_proxy:+,$no_proxy}"
export NO_PROXY="127.0.0.1,localhost,::1${NO_PROXY:+,$NO_PROXY}"
# uv's content-addressed cache makes same-version wheels ~free across venvs
# (hardlinks). This MUST stay hardlink for the venvs to share torch/CUDA bits.
export UV_LINK_MODE="${UV_LINK_MODE:-hardlink}"

FABRIC_VENV="$TOOLCHAINS_ROOT/fabric"
IMAGE_VENV="$TOOLCHAINS_ROOT/image"
IMAGE_SDCLI_VENV="$TOOLCHAINS_ROOT/image-sdcli"
AUDIO_TOOLCHAINS=(ace-step cosyvoice fish-speech seed-vc stable-audio)
PYTORCH_INDEX="https://download.pytorch.org/whl/cu124"
IMAGE_MARKER="$IMAGE_VENV/.fabric-image-synced"
SDCLI_MARKER="$IMAGE_SDCLI_VENV/.fabric-image-sdcli-synced"
SDCLI_VENV_DIR="$IMAGE_SDCLI_VENV/.venv"
SDCLI_PY="$SDCLI_VENV_DIR/bin/python"

echo "!!! FABRIC ONE-SHOT START (host mode) !!!"
echo "Toolchains:    $TOOLCHAINS_ROOT"
echo "Resources:     $RESOURCES_ROOT"
echo "Repo root:     $MONOREPO"
echo "Port:          $PORT"

status_report() {
    echo ""
    echo "=== Fabric toolchain venv status (toolchains/) ==="
    local total=0
    for d in "$TOOLCHAINS_ROOT"/*/; do
        [[ -d "$d" ]] || continue
        n=$(basename "$d")
        if [[ -x "$d/.venv/bin/python" ]]; then
            szk=$(du -sk "$d/.venv" 2>/dev/null | cut -f1)
            total=$((total + ${szk:-0}))
            marker=""
            [[ -f "$d/.fabric-image-synced" ]] && marker=" (image synced)"
            printf '  %-14s .venv present  %s%s\n' "$n" "$(du -sh "$d/.venv" 2>/dev/null | cut -f1)" "$marker"
        else
            printf '  %-14s no .venv\n' "$n"
        fi
    done
    echo "  (venv dirs total: $((total / 1024)) MB apparent; blocks largely shared via hardlinks)"
    echo ""
    echo "=== Sharing / space ==="
    echo "  UV_LINK_MODE=${UV_LINK_MODE:-hardlink}"
    echo "  uv cache:     $(du -sh "${UV_CACHE_DIR:-$HOME/.cache/uv}" 2>/dev/null | cut -f1 || echo unavailable)"
    df -h / | tail -1
    echo "  Hardlinks only work same-filesystem; everything here lives on /."
    echo "  Space hogs to watch: 'uv cache prune' (drops unreferenced wheels; safe),"
    echo "  and per-toolchain torch versions that differ from 2.6.0+cu124."
}

if [[ "$STATUS" -eq 1 ]]; then
    status_report
    exit 0
fi

cleanup() {
    echo ""
    echo "!!! FABRIC SERVER EXITING !!!"
}
trap cleanup SIGINT SIGTERM EXIT

# ── [1/7] Terminate stale fabric processes ────────────────────────────────────
echo "[1/7] Terminating stale fabric processes on port $PORT..."
if command -v fuser >/dev/null 2>&1; then
    fuser -k "${PORT}/tcp" 2>/dev/null || true
fi
pkill -f "fabric.server" 2>/dev/null || true
# Orphaned workers keep VRAM allocated; terminate them too.
pkill -f "common_lib.nexus_workers" 2>/dev/null || true
sleep 1

have_uv() { command -v uv >/dev/null 2>&1; }
venv_python() { printf '%s/bin/python' "$1/.venv"; }

# ── [2/7] Control-plane venv (toolchains/fabric) ───────────────────────────────
FABRIC_PY="$(venv_python "$FABRIC_VENV")"
if [[ "$SKIP_INSTALL" -eq 1 ]]; then
    echo "[2/7] --skip-install: keeping existing venvs"
else
    echo "[2/7] Provisioning control-plane venv: $FABRIC_VENV"
    if ! have_uv; then
        echo "WARNING: 'uv' not found — cannot provision venvs." >&2
    else
        if [[ ! -x "$FABRIC_PY" ]]; then
            uv venv "$FABRIC_VENV/.venv" --python 3.11 || echo "WARNING: could not create $FABRIC_VENV/.venv" >&2
        fi
        if [[ -x "$FABRIC_PY" ]]; then
            uv pip install --python "$FABRIC_PY" fastapi "uvicorn[standard]" httpx pydantic \
                python-multipart \
                || echo "WARNING: control-plane dep install failed" >&2
            uv pip install --python "$FABRIC_PY" --no-deps -e "$COMMON_LIB_PROJECT" \
                || echo "WARNING: editable common_lib install failed" >&2
        fi
    fi
fi
if [[ ! -x "$FABRIC_PY" ]]; then
    echo "CRITICAL: control-plane venv not usable: $FABRIC_PY" >&2
    echo "          re-run without --skip-install, or create it manually." >&2
    exit 1
fi
if ! (cd "$BACKEND_DIR" && "$FABRIC_PY" -c "import fabric.server" 2>/tmp/fabric_import_error.log); then
    echo "CRITICAL: fabric control-plane import failed:" >&2
    cat /tmp/fabric_import_error.log >&2
    exit 1
fi
echo "        control plane OK: $FABRIC_PY"

# ── [3/7] GGUF/Vulkan image worker venv (toolchains/image-sdcli) ───────────────
SDCLI_PY="$SDCLI_VENV_DIR/bin/python"
if [[ "$SKIP_INSTALL" -eq 1 ]]; then
    echo "[3/7] --skip-install: keeping existing image-sdcli venv"
else
    echo "[3/7] Provisioning GGUF/Vulkan image worker venv: $IMAGE_SDCLI_VENV"
    if ! have_uv; then
        echo "WARNING: 'uv' not found — cannot provision image-sdcli venv." >&2
    else
        mkdir -p "$IMAGE_SDCLI_VENV"
        if [[ ! -x "$SDCLI_PY" ]]; then
            uv venv "$SDCLI_VENV_DIR" --python 3.11 || echo "WARNING: could not create $SDCLI_VENV_DIR" >&2
        fi
        if [[ -x "$SDCLI_PY" ]] && { [[ ! -f "$SDCLI_MARKER" ]] || ! "$SDCLI_PY" -c "import fastapi, pydantic, PIL, common_lib" >/dev/null 2>&1; }; then
            # sd-cli (Vulkan) does the diffusion work; the worker only needs
            # the HTTP plumbing + Pillow (image post-processing) — no torch,
            # ~60 MB total (hardlinked).
            uv pip install --python "$SDCLI_PY" fastapi "uvicorn[standard]" httpx pydantic pillow \
                || echo "WARNING: sdcli dep install failed" >&2
            uv pip install --python "$SDCLI_PY" --no-deps -e "$COMMON_LIB_PROJECT" \
                || echo "WARNING: editable common_lib install failed" >&2
            touch "$SDCLI_MARKER"
        else
            echo "        image-sdcli venv already provisioned (marker present, imports OK)"
        fi
    fi
fi
if [[ ! -x "$SDCLI_PY" ]]; then
    echo "CRITICAL: image-sdcli worker venv missing: $SDCLI_PY" >&2
    echo "          re-run without --skip-install so it can be provisioned." >&2
    exit 1
fi
if ! ("$SDCLI_PY" -c "import common_lib.nexus_workers.image_gen" 2>/tmp/fabric_sdcli_import_error.log); then
    echo "CRITICAL: image-sdcli worker failed to import in $SDCLI_PY:" >&2
    cat /tmp/fabric_sdcli_import_error.log >&2
    echo "          fix the venv above (or remove $SDCLI_MARKER and re-run) and try again." >&2
    exit 1
fi
echo "        image-sdcli worker OK: $SDCLI_PY"

# ── [4/7] Image worker venv (toolchains/image) ─────────────────────────────────
IMAGE_PY="$(venv_python "$IMAGE_VENV")"
mkdir -p "$IMAGE_VENV"
if [[ "$SKIP_INSTALL" -eq 1 ]]; then
    echo "[4/7] --skip-install: keeping existing image venv"
else
    echo "[4/7] Provisioning image worker venv: $IMAGE_VENV"
    if ! have_uv; then
        echo "WARNING: 'uv' not found — cannot provision image venv." >&2
    else
        if [[ ! -x "$IMAGE_PY" ]]; then
            uv venv "$IMAGE_VENV/.venv" --python 3.11 || echo "WARNING: could not create $IMAGE_VENV/.venv" >&2
        fi
        if [[ -x "$IMAGE_PY" ]] && { [[ ! -f "$IMAGE_MARKER" ]] || ! "$IMAGE_PY" -c "import torch, diffusers, transformers, PIL, uvicorn, gguf, common_lib; from diffusers import ZImagePipeline" >/dev/null 2>&1; }; then
            echo "        installing torch 2.6.0+cu124 from $PYTORCH_INDEX (first run: several GB)..."
            uv pip install --python "$IMAGE_PY" torch==2.6.0+cu124 torchvision==0.21.0+cu124 \
                --index-url "$PYTORCH_INDEX" || echo "WARNING: torch cu124 install failed" >&2
            uv pip install --python "$IMAGE_PY" "uvicorn[standard]" "diffusers==0.36.0" "huggingface-hub<1.0" transformers==4.57.6 \
                accelerate==0.26.0 safetensors sentencepiece pillow gguf \
                || echo "WARNING: image engine dep install failed" >&2
            uv pip install --python "$IMAGE_PY" -e "$COMMON_LIB_PROJECT" \
                || echo "WARNING: editable common_lib install failed" >&2
            touch "$IMAGE_MARKER"
        else
            echo "        image venv already provisioned (marker present, imports OK)"
        fi
    fi
fi
if [[ ! -x "$IMAGE_PY" ]]; then
    echo "CRITICAL: image worker venv missing: $IMAGE_PY" >&2
    echo "          re-run without --skip-install so it can be provisioned." >&2
    exit 1
fi
if ! ("$IMAGE_PY" -c "import common_lib.nexus_workers.image_gen" 2>/tmp/fabric_image_import_error.log); then
    echo "CRITICAL: image worker failed to import in $IMAGE_PY:" >&2
    cat /tmp/fabric_image_import_error.log >&2
    echo "          fix the venv above (or remove $IMAGE_MARKER and re-run) and try again." >&2
    exit 1
fi
echo "        image worker OK: $IMAGE_PY"

# ── [5/7] Audio toolchain venvs (report; provision only on --install-toolchains) ─
CONSTRAINTS="$TOOLCHAINS_ROOT/constraints.txt"
cat > "$CONSTRAINTS" <<'EOF'
# Generated by run_fabric_host.sh — keeps cosyvoice on the SAME wheels as the
# image toolchain so uv hardlinks from the cache instead of duplicating torch.
# CosyVoice predates transformers 5.x — pin 4.57.6 or it breaks at import.
torch==2.6.0+cu124
torchvision==0.21.0+cu124
numpy<2
transformers==4.57.6
EOF

provision_audio_venv() {
    local name="$1" constraints="$2"
    local tdir="$TOOLCHAINS_ROOT/$name"
    local tpy="$tdir/.venv/bin/python"
    if [[ ! -d "$tdir" ]]; then
        echo "        $name: SKIP (no such toolchain directory)"
        return
    fi
    if ! have_uv; then
        echo "        $name: WARNING uv missing — cannot provision" >&2
        return
    fi
    if [[ ! -x "$tpy" ]]; then
        uv venv "$tdir/.venv" --python 3.11 >/dev/null 2>&1 \
            && echo "        $name: created .venv" \
            || { echo "        $name: WARNING could not create .venv" >&2; return; }
    fi
    # Worker plumbing first: the nexus_workers adapters are FastAPI services and
    # import fastapi/pydantic (+ uvicorn to serve) — install before the manifest.
    uv pip install --python "$tpy" fastapi "uvicorn[standard]" httpx pydantic \
        || echo "        $name: WARNING worker plumbing install failed" >&2
    uv pip install --python "$tpy" --no-deps -e "$COMMON_LIB_PROJECT" \
        || echo "        $name: WARNING editable common_lib install failed" >&2
    local -a args=(--python "$tpy")
    if [[ -n "$constraints" ]]; then
        args+=(--constraint "$constraints" --extra-index-url "$PYTORCH_INDEX")
    fi
    if [[ -f "$tdir/requirements.txt" ]]; then
        echo "        $name: installing requirements.txt (best effort)..."
        uv pip install "${args[@]}" -r "$tdir/requirements.txt" \
            || echo "        $name: WARNING install failed — worker may be incomplete" >&2
    elif [[ -f "$tdir/pyproject.toml" ]]; then
        echo "        $name: installing pyproject (-e, best effort)..."
        uv pip install "${args[@]}" -e "$tdir" \
            || echo "        $name: WARNING install failed — worker may be incomplete" >&2
    else
        echo "        $name: no pip-installable manifest (see its Dockerfile) — skipped"
    fi
    "$tpy" -c "import torch; print('        $name: torch', torch.__version__, 'OK')" 2>/dev/null \
        || echo "        $name: WARNING torch import check failed" >&2
}

if [[ "$INSTALL_TOOLCHAINS" -eq 1 ]]; then
    echo "[5/7] Provisioning audio toolchain venvs (per-toolchain manifests)..."

    # cosyvoice: 2 phases — torch from the cu124 index first, then the manifest
    # from PyPI only (no extra index → no tqdm downgrade trap).
    echo "        cosyvoice: torch 2.6.0+cu124 (cu124 index)..."
    provision_audio_venv "cosyvoice" "" 2>&1 | tail -2
    uv pip install --python "$TOOLCHAINS_ROOT/cosyvoice/.venv/bin/python" \
        torch==2.6.0+cu124 torchaudio==2.6.0+cu124 --index-url "$PYTORCH_INDEX" 2>&1 | tail -3 \
        || echo "        cosyvoice: WARNING torch cu124 install failed" >&2
    uv pip install --python "$TOOLCHAINS_ROOT/cosyvoice/.venv/bin/python" \
        -r "$TOOLCHAINS_ROOT/cosyvoice/requirements.txt" --constraint "$CONSTRAINTS" 2>&1 | tail -6 \
        || echo "        cosyvoice: WARNING requirements install failed (see above)" >&2
    # Enforce CosyVoice-compatible transformers even if the resolver drifted
    uv pip install --python "$TOOLCHAINS_ROOT/cosyvoice/.venv/bin/python" "transformers==4.57.6" 2>&1 | tail -3 \
        || echo "        cosyvoice: WARNING transformers pin failed" >&2
    "$TOOLCHAINS_ROOT/cosyvoice/.venv/bin/python" -c "import torch; print('        cosyvoice: torch', torch.__version__, 'OK')" 2>/dev/null \
        || echo "        cosyvoice: WARNING torch import check failed" >&2

    # ace-step: requirements pin torch 2.10.0+cu128 via the file's own index; do NOT
    # constrain. flash-attn is filtered out: its setup.py imports torch without declaring
    # it (build dies on every host without nvcc+headers) and AceStep runs fine with eager
    # attention. Everything else installs best-effort.
    echo "        ace-step: torch 2.10.0+cu128 (cu128 index, from manifest)..."
    provision_audio_venv "ace-step" "" 2>&1 | tail -2
    uv pip install --python "$TOOLCHAINS_ROOT/ace-step/.venv/bin/python" \
        torch==2.10.0+cu128 torchvision==0.25.0+cu128 torchaudio==2.10.0+cu128 \
        --index-url https://download.pytorch.org/whl/cu128 2>&1 | tail -4 \
        || { echo "        ace-step: cu128 index failed — retrying against default PyPI" >&2; \
             uv pip install --python "$TOOLCHAINS_ROOT/ace-step/.venv/bin/python" \
                 torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 2>&1 | tail -4; } \
        || echo "        ace-step: WARNING torch install failed on both indexes" >&2
    grep -vE '^flash-attn' "$TOOLCHAINS_ROOT/ace-step/requirements.txt" > /tmp/acestep-req.txt
    uv pip install --python "$TOOLCHAINS_ROOT/ace-step/.venv/bin/python" -r /tmp/acestep-req.txt 2>&1 | tail -6 \
        || echo "        ace-step: WARNING requirements install failed (see above)" >&2
    "$TOOLCHAINS_ROOT/ace-step/.venv/bin/python" -c "import torch; print('        ace-step: torch', torch.__version__, 'OK')" 2>/dev/null \
        || echo "        ace-step: WARNING torch import check failed" >&2

    # fish-speech: manifest pins torch==2.8.0 (default PyPI cu128 wheels) and is
    # self-conflicting (protobuf>=3.20 vs descript-audio-codec <3.20) — drop the
    # protobuf pin so the codec's constraint wins. Best effort.
    echo "        fish-speech: torch==2.8.0 + pyaudio (needs portaudio, present)..."
    provision_audio_venv "fish-speech" "" 2>&1 | tail -2
    uv pip install --python "$TOOLCHAINS_ROOT/fish-speech/.venv/bin/python" torch==2.8.0 torchaudio==2.8.0 2>&1 | tail -4 \
        || echo "        fish-speech: WARNING torch 2.8.0 install failed" >&2
    grep -vE '^protobuf' "$TOOLCHAINS_ROOT/fish-speech/requirements.txt" > /tmp/fishspeech-req.txt
    uv pip install --python "$TOOLCHAINS_ROOT/fish-speech/.venv/bin/python" -r /tmp/fishspeech-req.txt 2>&1 | tail -8 \
        || echo "        fish-speech: WARNING requirements install failed (see above)" >&2
    "$TOOLCHAINS_ROOT/fish-speech/.venv/bin/python" -c "import torch; print('        fish-speech: torch', torch.__version__, 'OK')" 2>/dev/null \
        || echo "        fish-speech: WARNING torch import check failed" >&2

    # Skipped deliberately:
    #   seed-vc      — no model weights on disk (seed_vc worker would have nothing to run)
    #   stable-audio — no fabric worker adapter exists for stable-audio (venv would be dead code)
else
    echo "[5/7] Audio toolchains (report only — pass --install-toolchains to provision):"
    for tc in "${AUDIO_TOOLCHAINS[@]}"; do
        tdir="$TOOLCHAINS_ROOT/$tc"
        if [[ -x "$tdir/.venv/bin/python" ]]; then
            echo "        $tc: .venv present ($(du -sh "$tdir/.venv" 2>/dev/null | cut -f1))"
        else
            echo "        $tc: no .venv (provision with --install-toolchains)"
        fi
    done
fi

# ── [6/7] GPU sanity (informational) ──────────────────────────────────────────
echo "[6/7] Checking GPU visibility (informational only)..."
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader || true
else
    echo "WARNING: nvidia-smi not found — image/audio GPU work may fail." >&2
fi
mkdir -p "$NEXUS_LOG_DIR" "$NEXUS_IMAGE_OUTPUT_DIR" "$NEXUS_AUDIO_OUTPUT_DIR"

if [[ "$INSTALL_ONLY" -eq 1 ]]; then
    echo ""
    echo "[7/7] --install-only: venvs provisioned and imports verified. Not starting the server."
    echo "      fabric control: $FABRIC_PY"
    echo "      image-sdcli:    $SDCLI_PY"
    echo "      image worker:   $IMAGE_PY"
    exit 0
fi

# ── [7/7] Start the fabric ─────────────────────────────────────────────────────
echo "[7/7] Starting Fabric server on $HOST:$PORT..."
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if command -v ss >/dev/null 2>&1 && ss -tlnH "sport = :$PORT" 2>/dev/null | grep -q .; then
        sleep 1
    else
        break
    fi
done
echo "  control:   $FABRIC_PY"
echo "  workers:   $SDCLI_PY (image-sdcli), $IMAGE_PY (image-cuda), toolchains/<name>/.venv (audio)"
echo "  toolchains: $NEXUS_TOOLCHAIN_VENVS"
echo "  outputs:   $NEXUS_IMAGE_OUTPUT_DIR"
echo "  logs:      $NEXUS_LOG_DIR (workers), uvicorn on stdout"
echo "  platform backend remains on port 8000 (./clean_start.sh)"
echo ""

cd "$BACKEND_DIR"
exec "$FABRIC_PY" -m fabric.server
