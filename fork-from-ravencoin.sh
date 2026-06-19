#!/usr/bin/env bash
# Copyright (c) 2024-2025 The Opalyx Core developers
# Distributed under the MIT software license.
#
# fork-from-ravencoin.sh — produce an Opalyx (OPX) source tree from Ravencoin.
#
# Pipeline:
#   1. Clone Ravencoin at the pinned commit.
#   2. Copy in the Opalyx-only source files (ASERT engine, signed checkpoints).
#   3. Run configure-opalyx.py (chain params, ports, magic, genesis scaffolding).
#   4. Run rebrand.sh (Ravencoin -> Opalyx, binary names).
#
# It does NOT compile and does NOT mine the genesis block. After this finishes:
#       ./scripts/build-ubuntu.sh        # build opalyxd (+ deps) on Ubuntu 22.04
#       ./scripts/generate-genesis.sh    # mine genesis, patch __OPX_*__ tokens
#       ./scripts/build-ubuntu.sh        # rebuild with real genesis values
#
# Usage:
#   ./scripts/fork-from-ravencoin.sh [target_dir]
# Env overrides:
#   RVN_REPO   (default https://github.com/RavenProject/Ravencoin.git)
#   RVN_COMMIT (default 6d48ae0175b10283248146ae3080e2ba70966739)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OVERLAY_ROOT="$(cd "$HERE/.." && pwd)"   # the opalyx/ deliverable dir

TARGET="${1:-opalyx-src}"
RVN_REPO="${RVN_REPO:-https://github.com/RavenProject/Ravencoin.git}"
RVN_COMMIT="${RVN_COMMIT:-6d48ae0175b10283248146ae3080e2ba70966739}"

echo "==> Opalyx fork builder"
echo "    overlay : $OVERLAY_ROOT"
echo "    target  : $TARGET"
echo "    base    : $RVN_REPO @ $RVN_COMMIT"

if [ -e "$TARGET" ]; then
  echo "ERROR: target '$TARGET' already exists; remove it or choose another." >&2
  exit 2
fi

# --- 1. clone at the pinned commit --------------------------------------------
echo "==> [1/4] cloning Ravencoin"
git clone "$RVN_REPO" "$TARGET"
( cd "$TARGET" && git checkout --quiet "$RVN_COMMIT" )

# --- 2. copy Opalyx-only source files -----------------------------------------
echo "==> [2/4] copying Opalyx source overlay"
mkdir -p "$TARGET/src/pow"
cp "$OVERLAY_ROOT/src/pow/aserti32d.h"   "$TARGET/src/pow/"
cp "$OVERLAY_ROOT/src/pow/aserti32d.cpp" "$TARGET/src/pow/"
cp "$OVERLAY_ROOT/src/checkpointsync.h"   "$TARGET/src/"
cp "$OVERLAY_ROOT/src/checkpointsync.cpp" "$TARGET/src/"

# --- 3. apply chain-parameter configurator ------------------------------------
echo "==> [3/4] applying configure-opalyx.py"
python3 "$HERE/configure-opalyx.py" --src "$TARGET/src"

# --- 4. rebrand ----------------------------------------------------------------
echo "==> [4/4] rebranding Ravencoin -> Opalyx"
"$HERE/rebrand.sh" "$TARGET"

cat <<EOF

==> Done. Opalyx source tree is at: $TARGET

    Nothing has been compiled and the genesis block has NOT been mined yet.
    Next steps (on Ubuntu 22.04):

      cd $TARGET
      ../$(basename "$OVERLAY_ROOT")/scripts/build-ubuntu.sh    # first build
      ../$(basename "$OVERLAY_ROOT")/scripts/generate-genesis.sh # mine genesis
      ../$(basename "$OVERLAY_ROOT")/scripts/build-ubuntu.sh    # rebuild

    See INSTALL.md and TODO.md for details and manual fallbacks.
EOF
