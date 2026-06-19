# MINING.md — Mining Opalyx (KawPow, GPU)

Opalyx uses **KawPow**, the same GPU proof-of-work as Ravencoin. KawPow is
ASIC-resistant by design and is mined on GPUs. The `opalyxd` node does **not**
GPU-mine internally — an external miner produces block solutions via
`getblocktemplate`, normally through a pool such as Miningcore.

> KawPow is GPU-only in practice. CPU mining exists only for regtest smoke tests
> (where difficulty is trivial); it is not viable on testnet or mainnet.

## Option A — Pool mining with Miningcore (recommended)

Miningcore supports the `kawpow` family, so it works with Opalyx once you add
the coin definition and a pool config.

### 1. Add the coin definition

Merge the `opalyx` object from `miningcore/opalyx-coin-template.json` into
Miningcore's `coins.json` (the top-level object keyed by symbol).

Key fields:
- `"family": "kawpow"`, `"headerHasher": "kawpow"`.
- `"coinbaseMaturity": 60` — matches the chain's maturity so the pool only pays
  out matured coinbases.
- `blockHasher` — Opalyx inherits Ravencoin's on-disk block-id scheme. Start
  with Miningcore's Ravencoin value and confirm against `getblock` output before
  going live (noted inline in the template).

### 2. Configure the pool

Use `miningcore/opalyx-pool-template.json` as a starting point. It is wired for
**testnet** (daemon RPC port 29776). To go to mainnet, change the daemon `port`
to `19776`. Edit before running:

- `pools[0].address` — a pool-controlled Opalyx address (block rewards land
  here). Testnet: `opalyx-cli -testnet getnewaddress`. Mainnet addresses start
  with `o`.
- `pools[0].rewardRecipients` — your fee address and percentage.
- `daemons[0].user` / `password` — must match `rpcuser` / `rpcpassword` in
  `opalyx.conf`.
- `persistence.postgres` — your Postgres credentials (Miningcore requires it).
- Stratum is exposed on port `3333` in the template; change as you like.

### 3. Ensure the node is ready

In `opalyx.conf`:

```
server=1
txindex=1
rpcuser=opalyxrpc
rpcpassword=<match the pool config>
```

Restart the node, start Miningcore, then point miners at your stratum port.

### 4. Point a GPU miner at the pool

Any KawPow-capable miner works (e.g. `kawpowminer`, or multi-algo miners with a
kawpow/kawpow-OPX mode). Generic stratum form:

```
<miner> -P stratum+tcp://<wallet-or-worker>@<pool-host>:3333
```

`kawpowminer` example:

```bash
kawpowminer -P stratum://<OPX_ADDRESS>.<worker>@<pool-host>:3333
```

## Option B — Solo mining

Run your own single-pool Miningcore against your node (same steps as Option A,
just one pool and your own addresses). This is the practical way to "solo mine"
KawPow because the node speaks `getblocktemplate`, not stratum, and GPU miners
speak stratum — Miningcore bridges the two.

A direct `getblocktemplate` loop without a stratum bridge is possible but you'd
have to implement KawPow block assembly yourself; using Miningcore as a local
bridge is far simpler and is what the templates support.

## Option C — Regtest CPU smoke test (not real mining)

For development only. Regtest difficulty is trivial, so the daemon's
`generatetoaddress` works without a GPU:

```bash
opalyx-cli -regtest -rpcport=39776 -rpcuser=u -rpcpassword=p \
  generatetoaddress 101 <regtest-address>
```

This confirms emission, coinbase maturity (60), and wallet spendability end to
end. It is **not** representative of KawPow mining performance or difficulty.

## Difficulty behavior miners should expect

Opalyx retargets **every block** using ASERT (not Bitcoin's 2016-block step).
Consequences for miners:

- Difficulty tracks hashrate quickly. If a large miner leaves, difficulty falls
  within a few blocks rather than stalling for days.
- There is a clamp limiting how far difficulty can move per block under normal
  conditions, and an emergency-recovery path that lets difficulty ease faster
  when blocks fall far behind schedule (e.g. after a 90–99% hashrate drop). See
  `CHAINPARAMS.md` for the exact half-life, clamp factor, and emergency gap.

## Pool concentration / safety

If you operate or watch a pool, run the concentration monitor to catch dangerous
hashrate centralization (the spec's 40% warning):

```bash
scripts/pool-hashrate-monitor.py \
  --rpcuser opalyxrpc --rpcpassword <pass> --rpcport 19776 \
  --window 720 --threshold 0.40 --watch 60
```

It attributes recent blocks to coinbase payout addresses and warns if any single
address exceeds the threshold. It is a heuristic (pools can split addresses), not
a consensus rule. See `SECURITY.md`.
