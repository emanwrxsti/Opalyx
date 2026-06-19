# TODO.md — what is NOT done

This is the brutally honest list. It exists so no one mistakes this overlay for a
finished, running coin. "Done" below means the source/automation exists; it does
**not** mean it was compiled or executed by the authors (see item 0).

## 0. Nothing here was compiled or run

The environment that produced this repo cannot build Ravencoin (1 core / ~4 GB).
Therefore:

- No binary was produced or tested here.
- The overlay C++ (`src/pow/aserti32d.*`, `src/checkpointsync.*`) is standard and
  self-contained but **unverified by compilation**.
- `scripts/rebrand.sh` and `scripts/configure-opalyx.py` were exercised against
  reference source for anchor matching, but the **resulting tree was never
  compiled**. The configurator's brace-balance and anchor checks are not a
  substitute for a real build.

**Action:** build on Ubuntu 22.04 (`INSTALL.md`) and treat the first successful
`make` as the real verification. Expect to fix small things the first compile
surfaces.

## 1. Genesis must be mined (placeholders present)

`src/chainparams.cpp` ships with `__OPX_NONCE_MAIN__`, `__OPX_NONCE_TEST__`,
`__OPX_NONCE_REGTEST__`, `__OPX_GENHASH_MAIN/TEST/REGTEST__`, `__OPX_MERKLE__`.

**Action:** after the first build, run `scripts/generate-genesis.sh` to mine all
three genesis blocks and patch the tokens, then **rebuild**. Verify with
`grep -n "__OPX_" src/chainparams.cpp` (must be empty). The node asserts on
startup until this is done.

## 2. Checkpoint master public key is a placeholder

`g_strCheckpointMasterPubKey` in `src/checkpointsync.cpp` is all zeros (an
intentionally **invalid** key, so checkpoints can't be forged against a default
build).

**Action:** `scripts/sign-checkpoint.py genkey`, paste the pubkey into
`checkpointsync.cpp`, store the private key offline, rebuild. Required before
mainnet if you intend to use signed checkpoints.

## 3. DNS seeds are placeholders

The seed hostnames in `src/chainparams.cpp` (main and test) are examples and will
not resolve.

**Action:** register real domains, run seeder infrastructure, add hard-coded
fallback peers. Until then bootstrap with `-addnode`. (`SECURITY.md`,
`ROADMAP.md` §5.)

## 4. Configurator manual-anchor fallback

If you pin a different Ravencoin commit than the one in
`scripts/fork-from-ravencoin.sh`, an anchor may not match. The configurator then
prints `MISS`/`AMBIG` and **makes no change for that edit** (exits non-zero).

**Action:** apply that single edit by hand using the table in `INSTALL.md` §5,
or fork from the pinned commit.

## 5. Signed-checkpoint P2P relay + RPC (roadmap, not MVP)

MVP accepts checkpoints only via `-synccheckpoint=HEIGHT:HASH:SIG` config/CLI and
has no automatic relay and no dedicated RPC. (`ROADMAP.md` §3.) Not required for
a working chain; required if you want runtime checkpoint propagation.

## 6. In-daemon pool/hashrate detection (roadmap)

The 40% warning is the external `scripts/pool-hashrate-monitor.py` heuristic, not
an in-daemon, peer-aware detector. (`ROADMAP.md` §4.)

## 7. Address groups (roadmap)

10 Alephium-style address groups are **not** implemented; Opalyx is plain
single-group UTXO. (`ROADMAP.md` §1.) Do not advertise groups as present.

## 8. SLIP-44 registration (roadmap)

Mainnet `nExtCoinType = 2025` is unregistered and may collide with other wallets.
(`ROADMAP.md` §2.) Decide before broad wallet integration.

## 9. Hard-coded block checkpoints

`src/checkpoints.cpp` has no Opalyx checkpoints yet (only genesis once mined).

**Action:** add periodic hard-coded checkpoints as the chain matures (standard
practice to harden initial block download).

## 10. `blockHasher` confirmation for Miningcore

`miningcore/opalyx-coin-template.json` notes that the `blockHasher` value should
be confirmed against real `getblock` output before going live, since Opalyx
inherits Ravencoin's block-id scheme.

**Action:** verify against a running node before opening a public pool.

## 11. Windows build not validated

`INSTALL.md` §4 documents the standard cross-compile and MSVC routes but they
were not run here.

**Action:** validate on Windows if you ship Windows binaries.

## 12. Tunables to finalize before genesis

`GENESIS_REWARD` (2500 OPX) and the halving interval are tunable **only before**
genesis is mined. Decide deliberately, then mine genesis. Changing emission after
launch means a new chain.

---

### Definition of "MVP working testnet" (the near-term goal)

- [ ] Builds on Ubuntu 22.04 (`opalyxd`, `opalyx-cli`).
- [ ] Genesis mined for all three networks; no placeholders remain.
- [ ] Two testnet nodes peer and converge on the same tip.
- [ ] A GPU miner (via Miningcore) finds testnet blocks; difficulty retargets via
      ASERT through a real hashrate change.
- [ ] A testnet transaction confirms and is spendable after maturity.

Only after that is mainnet on the table — and only after the `SECURITY.md`
launch checklist is fully satisfied.
