#!/usr/bin/env bash
# Set up a Fedora machine to build the Vita client (VitaSDK) and the desktop dev build.
# Idempotent: safe to re-run. Only the dnf step needs sudo.
#
# Usage: tools/setup-fedora.sh [--all-ports] [--skip-dnf]
#   --all-ports  run vdpm's install-all.sh instead of only the ports we need
#   --skip-dnf   do not install Fedora packages
set -euo pipefail

VITASDK_DIR="${VITASDK:-$HOME/vitasdk}"
VDPM_DIR="${VDPM_DIR:-$HOME/src/vdpm}"
ALL_PORTS=0
SKIP_DNF=0
for a in "$@"; do
  case "$a" in
    --all-ports) ALL_PORTS=1 ;;
    --skip-dnf)  SKIP_DNF=1 ;;
    -h|--help)   sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

# Ports needed by the client. Names follow vdpm package names; adjust if vdpm renames one.
PORTS=(zlib libpng libjpeg-turbo freetype mbedtls curl vita2d yyjson)

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarn:\033[0m %s\n' "$*" >&2; }

if [ "$SKIP_DNF" -eq 0 ]; then
  log "Installing Fedora packages (sudo)"
  sudo dnf install -y \
    git cmake make ninja-build gcc gcc-c++ python3 python3-pip \
    curl wget tar xz bzip2 unzip zip patch pkgconf-pkg-config \
    SDL2-devel SDL2_ttf-devel libcurl-devel lftp netcat
fi

mkdir -p "$(dirname "$VDPM_DIR")"
if [ -d "$VDPM_DIR/.git" ]; then
  log "Updating vdpm in $VDPM_DIR"
  git -C "$VDPM_DIR" pull --ff-only
else
  log "Cloning vdpm into $VDPM_DIR"
  git clone https://github.com/vitasdk/vdpm "$VDPM_DIR"
fi

export VITASDK="$VITASDK_DIR"
export PATH="$VITASDK/bin:$PATH"

if [ -x "$VITASDK/bin/arm-vita-eabi-gcc" ]; then
  log "VitaSDK toolchain already present in $VITASDK (delete it to force a reinstall)"
else
  log "Bootstrapping VitaSDK into $VITASDK"
  (cd "$VDPM_DIR" && ./bootstrap-vitasdk.sh)
fi

if [ "$ALL_PORTS" -eq 1 ]; then
  log "Installing all vdpm ports"
  (cd "$VDPM_DIR" && ./install-all.sh)
else
  log "Installing required ports: ${PORTS[*]}"
  for p in "${PORTS[@]}"; do
    (cd "$VDPM_DIR" && ./vdpm "$p") || warn "port '$p' failed; check its name in $VDPM_DIR (or rerun with --all-ports)"
  done
fi

# Persist environment (once)
MARK="# >>> vitasdk >>>"
for rc in "$HOME/.bashrc"; do
  if ! grep -qF "$MARK" "$rc" 2>/dev/null; then
    log "Adding VITASDK to $rc"
    cat >> "$rc" <<RC

$MARK
export VITASDK="$VITASDK_DIR"
export PATH="\$VITASDK/bin:\$PATH"
# <<< vitasdk <<<
RC
  fi
done

log "Checks"
"$VITASDK/bin/arm-vita-eabi-gcc" --version | head -1
command -v vita-mksfoex >/dev/null && echo "vita-mksfoex: ok" || warn "vita-mksfoex not found on PATH"
[ -f "$VITASDK/share/vita.toolchain.cmake" ] && echo "toolchain file: ok" || warn "vita.toolchain.cmake missing"
for lib in libvita2d.a libcurl.a libmbedtls.a; do
  [ -f "$VITASDK/arm-vita-eabi/lib/$lib" ] && echo "$lib: ok" || warn "$lib not found (port missing?)"
done

log "Done. Open a new shell (or: source ~/.bashrc) so VITASDK is set."
