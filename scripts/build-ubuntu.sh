#!/usr/bin/env bash
# Copyright (c) 2024-2025 The Opalyx Core developers
# Distributed under the MIT software license.
#
# build-ubuntu.sh — build Opalyx (opalyxd, opalyx-cli, opalyx-tx) on Ubuntu 22.04.
#
# This mirrors the upstream Ravencoin build (Opalyx is a source fork) and has
# the same dependency set. It has NOT been run end-to-end in the packaging
# container (no compiler/deps there); the commands below are the standard,
# documented build for this codebase on Ubuntu 22.04 LTS.
#
# Usage (from the forked source root):
#   ./scripts/build-ubuntu.sh             # build daemon + cli + tx (no GUI)
#   WITH_GUI=1 ./scripts/build-ubuntu.sh  # also build opalyx-qt
#   JOBS=4 ./scripts/build-ubuntu.sh      # limit parallelism (low-RAM boxes)

set -euo pipefail

[ -f "src/chainparams.cpp" ] || { echo "ERROR: run from the forked source root." >&2; exit 2; }

JOBS="${JOBS:-$(nproc)}"
WITH_GUI="${WITH_GUI:-0}"

echo "==> Installing build dependencies (sudo apt-get)"
if command -v sudo >/dev/null 2>&1; then SUDO=sudo; else SUDO=; fi
$SUDO apt-get update
$SUDO apt-get install -y \
  build-essential libtool autotools-dev automake pkg-config bsdmainutils python3 \
  libssl-dev libevent-dev libboost-system-dev libboost-filesystem-dev \
  libboost-chrono-dev libboost-program-options-dev libboost-test-dev \
  libboost-thread-dev libminiupnpc-dev libzmq3-dev git curl

# Berkeley DB 4.8 for wallet compatibility. Easiest path: the bundled script.
if [ -x ./contrib/install_db4.sh ]; then
  echo "==> Building Berkeley DB 4.8 (wallet support)"
  ./contrib/install_db4.sh "$(pwd)"
  export BDB_PREFIX="$(pwd)/db4"
  BDB_FLAGS="BDB_LIBS=\"-L${BDB_PREFIX}/lib -ldb_cxx-4.8\" BDB_CFLAGS=\"-I${BDB_PREFIX}/include\""
else
  echo "WARN: contrib/install_db4.sh not found; will try --with-incompatible-bdb"
  BDB_FLAGS=""
fi

if [ "$WITH_GUI" = "1" ]; then
  echo "==> Installing Qt5 (GUI build)"
  $SUDO apt-get install -y qttools5-dev qttools5-dev-tools libqt5gui5 libqt5core5a \
    libqt5dbus5 libprotobuf-dev protobuf-compiler libqrencode-dev
  GUI_FLAG="--with-gui=qt5"
else
  GUI_FLAG="--without-gui"
fi

echo "==> autogen + configure"
./autogen.sh
if [ -n "$BDB_FLAGS" ]; then
  eval ./configure "$GUI_FLAG" "$BDB_FLAGS"
else
  ./configure "$GUI_FLAG" --with-incompatible-bdb
fi

echo "==> make -j$JOBS"
make -j"$JOBS"

echo
echo "==> Build complete. Binaries:"
ls -1 src/opalyxd src/opalyx-cli src/opalyx-tx 2>/dev/null || true
[ "$WITH_GUI" = "1" ] && ls -1 src/qt/opalyx-qt 2>/dev/null || true
echo
echo "    Run a node:        ./src/opalyxd -testnet -daemon"
echo "    Query it:          ./src/opalyx-cli -testnet getblockchaininfo"
