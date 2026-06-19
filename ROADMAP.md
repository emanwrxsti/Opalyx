# ROADMAP.md — Opalyx deferred features

These are intentionally **out of scope for the MVP** and are documented here so
nobody mistakes them for finished work. The MVP goal is a working testnet, then
a defensible mainnet, on plain UTXO mechanics.

## 1. Ten Alephium-style address groups

The original spec mentioned 10 address groups (sharded address space à la
Alephium). The MVP uses **plain Ravencoin-style UTXO addresses** with no groups.

Adding groups is a significant consensus and wallet change: it touches address
encoding, transaction validation (group-aware UTXO selection), mempool/relay,
and every wallet/explorer. It is deferred until after mainnet stability and would
ship as a versioned, well-tested upgrade — not bolted on pre-launch. Until then,
treat Opalyx as a single-group UTXO chain.

## 2. SLIP-44 coin-type registration

Mainnet `nExtCoinType` is currently **2025**, which is **not registered** with
SLIP-44. Risk: BIP44 wallet derivation paths could collide with another project
using the same index, causing cross-wallet confusion.

Plan: register an official coin type with SLIP-44 and, if the assigned value
differs from 2025, decide deliberately whether to migrate (a derivation-path
change affects existing wallets) or keep 2025. Document the final decision for
wallet integrators. Until registered, integrators should be warned.

## 3. P2P checkpoint relay + dedicated RPC

The MVP signed-checkpoint system verifies a compiled-in master pubkey and accepts
checkpoints via the `-synccheckpoint` config/CLI option only. Deferred:

- **Automatic P2P relay** of signed checkpoints between nodes (so a freshly
  published checkpoint propagates without every operator editing configs).
- A **dedicated RPC** (e.g. `sendcheckpoint` / `getcheckpoint`) to broadcast and
  inspect checkpoints at runtime.
- Optional **key rotation without a binary release** (today the pubkey is
  compiled in, so rotating it ships a new build — intentional for MVP simplicity
  and auditability).

The verification logic (`src/checkpointsync.*`) is built to extend into this; the
network/RPC plumbing is the deferred part.

## 4. In-daemon hashrate-concentration detection

The 40% concentration warning is an **external heuristic script**
(`pool-hashrate-monitor.py`). A peer-aware, in-daemon detector (using connection
and block-relay data the node already has) could produce better signal and warn
operators automatically. Deferred; the external monitor covers the MVP
requirement.

## 5. DNS seed infrastructure

Chainparams ship **placeholder** DNS seeds. Standing up real seeder
infrastructure (seeder daemons, monitored seed domains, geographic diversity) is
operational work to be done before/around mainnet, with hard-coded fallback peers
as backup.

## 6. GUI wallet polish

`opalyx-qt` builds (with `WITH_GUI=1`) but ships with Ravencoin's UI rebranded.
Real iconography, branding, and UX review are deferred.

## 7. Independent reproducible builds & release signing

Beyond the build scripts here: deterministic/reproducible builds (Guix/depends),
signed release binaries, and a published verification process. Important for a
fair-launch coin; deferred past first mainnet bring-up.

---

Anything **blocking a correct MVP** lives in `TODO.md`, not here. This file is
strictly for features deliberately postponed.
