#!/usr/bin/env python3
"""
pool-hashrate-monitor.py — Opalyx network concentration monitor.

PURPOSE
    The Opalyx spec requires a warning when one entity appears to control more
    than 40% of network hashrate. A UTXO PoW daemon does not (and cannot)
    *know* who mined a block — it only sees coinbase outputs. This script
    therefore APPROXIMATES pool/miner concentration by attributing each block
    in a recent window to the coinbase payout address(es) it pays, then flags
    any address whose share of the window exceeds the threshold.

    This is a heuristic monitoring tool that runs OUTSIDE the daemon. It is NOT
    a consensus rule and cannot stop a 51% attack — see SECURITY.md. It exists
    so pool operators and exchanges can notice dangerous concentration early.

LIMITATIONS
    * A single pool can split rewards across many addresses, which makes its
      share look smaller than it is (false negative).
    * Solo miners rotating addresses look like many small miners.
    * Treat a sustained warning as "investigate", not "proof".

USAGE
    ./pool-hashrate-monitor.py \
        --rpcuser USER --rpcpassword PASS \
        [--rpcport 19776] [--rpchost 127.0.0.1] \
        [--window 720] [--threshold 0.40] [--watch 60]

    --window     number of most-recent blocks to analyse (default 720 = ~1 day)
    --threshold  fraction that triggers a warning (default 0.40)
    --watch N    loop forever, re-checking every N seconds (default: run once)

EXIT CODES
    0  ran successfully, no entity over threshold
    2  ran successfully, at least one entity over threshold
    1  error talking to the daemon
"""
import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict


class RpcError(Exception):
    pass


def rpc(host, port, user, password, method, params=None):
    payload = json.dumps({
        "jsonrpc": "1.0",
        "id": "opx-monitor",
        "method": method,
        "params": params or [],
    }).encode()
    url = f"http://{host}:{port}/"
    req = urllib.request.Request(url, data=payload)
    req.add_header("Content-Type", "text/plain")
    import base64
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        # bitcoin-style daemons return JSON errors with non-200 codes
        try:
            body = json.loads(e.read().decode())
        except Exception:
            raise RpcError(f"HTTP {e.code} calling {method}")
    except urllib.error.URLError as e:
        raise RpcError(f"cannot reach daemon at {url}: {e.reason}")
    if body.get("error"):
        raise RpcError(f"{method}: {body['error']}")
    return body["result"]


def coinbase_addresses(block):
    """Return the set of payout addresses in a block's coinbase tx."""
    if not block.get("tx"):
        return set()
    cb = block["tx"][0]
    addrs = set()
    for vout in cb.get("vout", []):
        spk = vout.get("scriptPubKey", {})
        for a in spk.get("addresses", []) or ([spk["address"]] if "address" in spk else []):
            addrs.add(a)
    return addrs


def analyse(host, port, user, password, window, threshold):
    info = rpc(host, port, user, password, "getblockchaininfo")
    tip = info["blocks"]
    start = max(0, tip - window + 1)

    counts = defaultdict(float)
    analysed = 0
    for height in range(start, tip + 1):
        bhash = rpc(host, port, user, password, "getblockhash", [height])
        block = rpc(host, port, user, password, "getblock", [bhash, 2])
        addrs = coinbase_addresses(block)
        if not addrs:
            counts["<unparseable-coinbase>"] += 1.0
            analysed += 1
            continue
        # split credit evenly if a coinbase pays multiple addresses
        share = 1.0 / len(addrs)
        for a in addrs:
            counts[a] += share
        analysed += 1

    if analysed == 0:
        return tip, []

    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    rows = [(addr, n, n / analysed) for addr, n in ranked]
    return tip, rows


def main():
    ap = argparse.ArgumentParser(description="Opalyx hashrate concentration monitor")
    ap.add_argument("--rpchost", default="127.0.0.1")
    ap.add_argument("--rpcport", type=int, default=19776,
                    help="default 19776 (mainnet). Testnet=29776, regtest=39776")
    ap.add_argument("--rpcuser", required=True)
    ap.add_argument("--rpcpassword", required=True)
    ap.add_argument("--window", type=int, default=720)
    ap.add_argument("--threshold", type=float, default=0.40)
    ap.add_argument("--watch", type=int, default=0,
                    help="loop forever, re-checking every N seconds")
    ap.add_argument("--top", type=int, default=5, help="how many addresses to print")
    args = ap.parse_args()

    def run_once():
        try:
            tip, rows = analyse(args.rpchost, args.rpcport, args.rpcuser,
                                args.rpcpassword, args.window, args.threshold)
        except RpcError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        if not rows:
            print("No blocks analysed yet.")
            return 0
        flagged = [r for r in rows if r[2] > args.threshold]
        print(f"[tip {tip}] analysed {min(args.window, tip+1)} blocks; "
              f"top {args.top} payout addresses:")
        for addr, n, frac in rows[:args.top]:
            mark = "  <-- OVER THRESHOLD" if frac > args.threshold else ""
            print(f"    {frac*100:6.2f}%  ({n:.1f} blk)  {addr}{mark}")
        if flagged:
            print()
            print("=" * 70)
            print(f"WARNING: {len(flagged)} address(es) exceed "
                  f"{args.threshold*100:.0f}% of recent blocks.")
            print("One entity may control a dangerous share of hashrate.")
            print("This is a HEURISTIC (pools split addresses). Investigate;")
            print("consider raising exchange confirmation requirements. See SECURITY.md.")
            print("=" * 70)
            return 2
        return 0

    if args.watch > 0:
        rc = 0
        try:
            while True:
                rc = run_once()
                time.sleep(args.watch)
        except KeyboardInterrupt:
            return rc
    else:
        return run_once()


if __name__ == "__main__":
    sys.exit(main())
