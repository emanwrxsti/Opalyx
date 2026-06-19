# SECURITY.md — Opalyx security model and mainnet launch checklist

## The honest baseline: no PoW chain fully prevents 51% attacks

Opalyx is proof-of-work. **Any** PoW chain can be reorganized by an entity that
controls a majority of hashrate; this is inherent to Nakamoto consensus, not a
bug specific to Opalyx. A new or small-cap KawPow chain is especially exposed
because rentable KawPow hashrate exists and may dwarf the honest network. The
mechanisms below **raise the cost and limit the blast radius** of attacks. They
do **not** make a 51% attack impossible. Plan accordingly — particularly
exchanges and custodians.

## Deep-reorg protection

Opalyx rejects any reorganization deeper than **720 blocks** (~24 hours at 120
s/block) via `nMaxReorganizationDepth = 720`, enforced in
`ContextualCheckBlockHeader`. This caps how far history an attacker can rewrite
even with overwhelming hashrate: a multi-day-deep rewrite is refused outright by
honest nodes.

- Default: on, all networks.
- Emergency override: `-allowdeepreorg=1`. Use **only** when you are knowingly
  recovering from a legitimate deep split and understand that you are lowering
  the guard. Leave it off in normal operation.
- Ravencoin's existing related knobs (`-maxreorg`, `-minreorgpeers`,
  `-minreorgage`) remain available.

Caveat: deep-reorg limits can themselves cause a network to **split** if a
genuine long reorg occurs (some nodes accept, some reject). That is a deliberate
trade-off — preventing silent deep history rewrites is judged more important than
seamlessly healing a 720+ block split. Coordinate via signed checkpoints if such
an event ever happens.

## Signed checkpoints

Opalyx supports operator-signed checkpoints to pin canonical history during the
fragile early life of the chain.

- A checkpoint is `HEIGHT:BLOCKHASH:SIGNATURE`, signed by a project master key
  and supplied to nodes via `-synccheckpoint=...` (config or CLI).
- The daemon verifies the signature against a **compiled-in** master public key
  (`g_strCheckpointMasterPubKey` in `src/checkpointsync.cpp`) using real
  secp256k1 verification, then rejects any block that conflicts with the
  checkpoint at that height.
- Generate the key and sign checkpoints with `scripts/sign-checkpoint.py`
  (`genkey`, then `sign`).

**Current status / limitations (do not skip):**
- The shipped master pubkey is an all-zero **placeholder and is intentionally
  invalid**, so no one can forge checkpoints against a default build. You must
  replace it with a real key before mainnet, then rebuild.
- Distribution is **manual** in the MVP: operators paste the `-synccheckpoint`
  string into their config. Automatic **P2P relay** of checkpoints and a
  dedicated RPC to broadcast them are roadmap items (`ROADMAP.md`).
- Signed checkpoints are a centralization trade-off: the key holder can pin
  history. Treat the key like a release-signing key (air-gapped, offline) and
  publish your checkpoint policy so it is auditable.

## Hashrate concentration monitoring (the 40% warning)

The spec calls for a warning when one entity exceeds 40% of network hashrate. A
UTXO PoW daemon cannot *know* who mined a block, so this is implemented as an
**external heuristic monitor**, `scripts/pool-hashrate-monitor.py`, not a
consensus rule:

```bash
scripts/pool-hashrate-monitor.py --rpcuser U --rpcpassword P \
  --rpcport 19776 --window 720 --threshold 0.40 --watch 60
```

It attributes recent blocks to coinbase payout addresses and warns when any
single address exceeds the threshold. Limitations: a pool can split rewards over
many addresses (false negative); solo miners rotating addresses look like many
miners. Treat a sustained warning as "investigate and consider raising
confirmation requirements," not proof.

In-daemon, peer-aware concentration detection is a roadmap item.

## Confirmation guidance

Because of 51%/deep-reorg risk, especially early on:

- **Coinbase maturity** is 60 blocks (~2 h) — miners can't spend rewards before
  that regardless.
- **Exchanges / custodians: require 120–360 confirmations** (~4–12 h) before
  crediting deposits, and more for large amounts. Start at the high end while the
  chain is young and hashrate is thin, and lower only as sustained hashrate and
  decentralization justify it.
- Combine with the concentration monitor: if one entity is near or above 40%,
  raise confirmations further or pause deposits.

## DNS seeds and checkpoints (operational)

- DNS seeds in chainparams are **placeholders**. Register real seed domains,
  run seeder infrastructure, and add hard-coded fallback peers before relying on
  automatic peer discovery. Until then, bootstrap with `-addnode`.
- Add hard-coded block checkpoints in `src/checkpoints.cpp` as the chain matures
  (standard Bitcoin/Ravencoin practice) to harden initial-block-download against
  low-difficulty header spam.

## Mainnet launch checklist

Do **not** launch mainnet until all of these are true:

1. **Built and run** on a real machine; `opalyxd`/`opalyx-cli` work; basic RPCs
   succeed. (Nothing in this repo was compiled by its authors — see `TODO.md`.)
2. **Testnet exercised**: multiple nodes peer and converge, blocks mine via a
   GPU miner/Miningcore, transactions confirm, difficulty retargets sanely
   through a real hashrate swing. (`TESTNET.md`)
3. **Genesis mined and compiled in**; no `__OPX_*__` placeholders remain
   (`grep -n "__OPX_" src/chainparams.cpp` is empty).
4. **Reward and emission finalized** (`GENESIS_REWARD`, halving) before genesis
   was mined — these cannot change afterward without a new chain.
5. **Checkpoint master key generated offline**, pubkey compiled in
   (placeholder replaced), key stored air-gapped, policy published.
6. **DNS seeds registered and serving**, plus hard-coded fallback peers.
7. **`nExtCoinType` decided**: SLIP-44 registered, or the collision risk
   knowingly accepted and documented for wallet integrators.
8. **Deep-reorg policy documented** for operators (when, if ever,
   `-allowdeepreorg` would be coordinated).
9. **Exchange/confirmation guidance published** (120–360 confs; concentration
   monitor in use).
10. **Source published** with build instructions so others can independently
    build and verify — a fair launch requires reproducibility.
11. **Magic bytes, ports, address prefixes verified distinct** from Ravencoin
    and any chain you might share peers/tooling with (they are by default; verify
    after any edits).

## Reporting

Establish a security contact and disclosure process before mainnet. A coin with
real value but no way to report vulnerabilities is a liability to its users.
