#!/usr/bin/env bash
# Copyright (c) 2024-2025 The Opalyx Core developers
# Distributed under the MIT software license.
#
# generate-genesis.sh — mine the Opalyx genesis blocks and patch chainparams.cpp.
#
# How it works:
#   The configurator left placeholder tokens in src/chainparams.cpp:
#       __OPX_NONCE_MAIN__   __OPX_GENHASH_MAIN__
#       __OPX_NONCE_TEST__   __OPX_GENHASH_TEST__
#       __OPX_NONCE_REGTEST__ __OPX_GENHASH_REGTEST__
#       __OPX_MERKLE__       (shared across all three)
#   and wrapped the genesis asserts in `if (!-mine-genesis)` guards plus a call
#   to OpalyxMaybeMineGenesis(). With -mine-genesis the daemon mines the active
#   network's nonce, prints an `OPX-GENESIS ...` line on stdout, and exits.
#
#   This script builds the daemon once (placeholders still present, but the
#   guarded asserts are skipped under -mine-genesis), runs it three times
#   (-mine-genesis, -testnet -mine-genesis, -regtest -mine-genesis), parses the
#   OPX-GENESIS lines, and seds the real values back into chainparams.cpp.
#
# Run this from the forked source root, with opalyxd already built once.
# Usage:
#   ./scripts/generate-genesis.sh [path_to_opalyxd]
# If opalyxd is not given/with no build present, set BUILD=1 to build first.

set -euo pipefail

SRC_ROOT="$(pwd)"
CP="src/chainparams.cpp"
[ -f "$CP" ] || { echo "ERROR: run from forked source root (no $CP)." >&2; exit 2; }

DAEMON="${1:-./src/opalyxd}"
if [ "${BUILD:-0}" = "1" ] || [ ! -x "$DAEMON" ]; then
  echo "==> building opalyxd (genesis miner build)"
  if [ ! -x ./configure ]; then ./autogen.sh; fi
  # Disable wallet/gui/tests to make this bootstrap build as fast as possible.
  ./configure --disable-tests --disable-bench --without-gui --with-incompatible-bdb >/dev/null
  make -j"$(nproc)" src/opalyxd
  DAEMON="./src/opalyxd"
fi

[ -x "$DAEMON" ] || { echo "ERROR: daemon '$DAEMON' not executable." >&2; exit 2; }

TMPDIR_GEN="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_GEN"' EXIT

mine() {
  # $1 = extra flags ; prints the OPX-GENESIS line
  local flags="$1"
  # shellcheck disable=SC2086
  "$DAEMON" -datadir="$TMPDIR_GEN" -mine-genesis $flags 2>/dev/null | grep -m1 '^OPX-GENESIS'
}

echo "==> mining MAINNET genesis (this can take a while)"
LINE_MAIN="$(mine "")"
echo "    $LINE_MAIN"
echo "==> mining TESTNET genesis"
LINE_TEST="$(mine "-testnet")"
echo "    $LINE_TEST"
echo "==> mining REGTEST genesis"
LINE_REG="$(mine "-regtest")"
echo "    $LINE_REG"

# field extractor: field key=value pairs in the OPX-GENESIS line
field() { echo "$1" | sed -n "s/.* $2=\([^ ]*\).*/\1/p"; }

N_MAIN="$(field "$LINE_MAIN" nonce)";  H_MAIN="$(field "$LINE_MAIN" hash)"
N_TEST="$(field "$LINE_TEST" nonce)";  H_TEST="$(field "$LINE_TEST" hash)"
N_REG="$(field "$LINE_REG" nonce)";    H_REG="$(field "$LINE_REG" hash)"
MERKLE="$(field "$LINE_MAIN" merkle)"   # identical for all three networks

for v in N_MAIN H_MAIN N_TEST H_TEST N_REG H_REG MERKLE; do
  if [ -z "${!v}" ]; then echo "ERROR: failed to parse $v from miner output." >&2; exit 3; fi
done

echo "==> patching $CP"
cp "$CP" "$CP.bak"
sed -i \
  -e "s/__OPX_NONCE_MAIN__/$N_MAIN/g" \
  -e "s/__OPX_GENHASH_MAIN__/$H_MAIN/g" \
  -e "s/__OPX_NONCE_TEST__/$N_TEST/g" \
  -e "s/__OPX_GENHASH_TEST__/$H_TEST/g" \
  -e "s/__OPX_NONCE_REGTEST__/$N_REG/g" \
  -e "s/__OPX_GENHASH_REGTEST__/$H_REG/g" \
  -e "s/__OPX_MERKLE__/$MERKLE/g" \
  "$CP"

if grep -q '__OPX_' "$CP"; then
  echo "ERROR: some placeholders remain in $CP:" >&2
  grep -n '__OPX_' "$CP" >&2
  exit 4
fi

cat <<EOF
==> genesis values written:
    main    nonce=$N_MAIN hash=$H_MAIN
    test    nonce=$N_TEST hash=$H_TEST
    regtest nonce=$N_REG hash=$H_REG
    merkle  $MERKLE

    Backup saved to $CP.bak
    NEXT: rebuild with real genesis values:  make -j\$(nproc)
EOF
