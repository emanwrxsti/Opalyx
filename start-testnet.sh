#!/usr/bin/env bash
#
# start-testnet.sh — bring up an Opalyx testnet node.
#
# This starts opalyxd on the Opalyx test network (P2P 29777 / RPC 29776).
# It does NOT mine — point a KawPow miner (or miningcore) at the RPC port,
# see MINING.md. By default the node runs in the foreground so you can watch
# the logs; pass -daemon-style backgrounding via DAEMON=1.
#
# Prerequisites:
#   * opalyxd has been built (scripts/build-ubuntu.sh) and is on PATH or in
#     the path given by OPALYXD below.
#   * Genesis has already been generated and compiled in (scripts/generate-genesis.sh),
#     otherwise the node will assert on startup with a genesis/merkle mismatch.
#
set -euo pipefail

# --- locate the daemon --------------------------------------------------------
OPALYXD="${OPALYXD:-opalyxd}"
if ! command -v "$OPALYXD" >/dev/null 2>&1 && [ ! -x "$OPALYXD" ]; then
  # try the usual in-tree build location relative to this script
  HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  for cand in \
      "$HERE/../src/opalyxd" \
      "$HERE/../opalyx/src/opalyxd" \
      "./src/opalyxd"; do
    if [ -x "$cand" ]; then OPALYXD="$cand"; break; fi
  done
fi
if ! command -v "$OPALYXD" >/dev/null 2>&1 && [ ! -x "$OPALYXD" ]; then
  echo "ERROR: opalyxd not found. Build it first (scripts/build-ubuntu.sh)" >&2
  echo "       or set OPALYXD=/path/to/opalyxd" >&2
  exit 1
fi

# --- data directory -----------------------------------------------------------
DATADIR="${DATADIR:-$HOME/.opalyx-testnet}"
mkdir -p "$DATADIR"

# --- RPC credentials ----------------------------------------------------------
# For a throwaway test node we generate a random rpc password once and stash it.
RPCUSER="${RPCUSER:-opalyxrpc}"
RPCPASS="${RPCPASS:-}"
CREDFILE="$DATADIR/.rpccreds"
if [ -z "$RPCPASS" ]; then
  if [ -f "$CREDFILE" ]; then
    # shellcheck disable=SC1090
    source "$CREDFILE"
  else
    RPCPASS="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    printf 'RPCUSER=%q\nRPCPASS=%q\n' "$RPCUSER" "$RPCPASS" > "$CREDFILE"
    chmod 600 "$CREDFILE"
  fi
fi

echo "=== Opalyx testnet node ==="
echo "  daemon : $OPALYXD"
echo "  datadir: $DATADIR"
echo "  P2P    : 29777"
echo "  RPC    : 29776 (user=$RPCUSER)"
echo "  control: $OPALYXD -testnet -datadir=$DATADIR -rpcuser=$RPCUSER -rpcpassword=*** getblockchaininfo"
echo "==========================="

ARGS=(
  -testnet
  -datadir="$DATADIR"
  -rpcuser="$RPCUSER"
  -rpcpassword="$RPCPASS"
  -rpcbind=127.0.0.1
  -rpcallowip=127.0.0.1
  -rpcport=29776
  -port=29777
  -server=1
  -listen=1
  -txindex=1
  -printtoconsole=1
)

# Allow callers to append extra flags, e.g.:
#   ./start-testnet.sh -addnode=1.2.3.4 -mine-genesis
if [ "$#" -gt 0 ]; then
  ARGS+=("$@")
fi

if [ "${DAEMON:-0}" = "1" ]; then
  ARGS+=(-daemon)
  exec "$OPALYXD" "${ARGS[@]}"
else
  exec "$OPALYXD" "${ARGS[@]}"
fi
