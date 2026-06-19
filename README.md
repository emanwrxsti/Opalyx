# Opalyx (OPX)

Opalyx is a real, mineable **KawPow** proof-of-work cryptocurrency built as a
fork **overlay** for the Ravencoin (UTXO / Bitcoin-derived C++) codebase. It is
**not** an ERC-20 token and **not** a simulator. When you run the fork pipeline
on a real Ravencoin checkout and build it on Ubuntu, you get working `opalyxd`,
`opalyx-cli`, `opalyx-tx`, and (optionally) `opalyx-qt` binaries that speak a
distinct network with its own genesis block, magic bytes, address prefixes, and
ports.

## Honest build status (read this first)

This repository is a **fork overlay plus automation**, not a pre-compiled
coin. Specifically:

- **Nothing in this repository has been compiled.** It was assembled in a
  constrained environment that cannot build Ravencoin. The C++ you add is
  standard and self-contained, but you must build it yourself on a real box
  (see `INSTALL.md`) and treat the first successful compile as the real test.
- **The genesis blocks are not mined yet.** The chain params ship with
  placeholder tokens (`__OPX_NONCE_*__`, `__OPX_GENHASH_*__`, `__OPX_MERKLE__`).
  You mine real values once with `scripts/generate-genesis.sh`, which patches
  them in, then you rebuild.
- **DNS seeds and checkpoint keys are placeholders.** You must register/run
  your own DNS seeds and generate your own checkpoint master key before a
  public launch.

Everything that is incomplete, and exactly which file/function it lives in, is
enumerated in `TODO.md`. The project deliberately does not pretend any binary
"works" until you have built and run it.

## What you actually get

| Property            | Value                                              |
|---------------------|----------------------------------------------------|
| Name / ticker       | Opalyx / OPX                                       |
| Algorithm           | KawPow (GPU), active from block 1                  |
| Block target        | 120 seconds                                        |
| Difficulty          | per-block **ASERT** with clamp + emergency recovery |
| Coinbase maturity   | 60 blocks (~2 hours spend delay)                   |
| Initial reward      | 2500 OPX (tunable before launch)                   |
| Halving interval    | 1,051,200 blocks (~4 years)                        |
| Premine             | none by default                                    |
| Mainnet P2P / RPC   | 19777 / 19776                                      |
| Testnet P2P / RPC   | 29777 / 29776                                      |
| Regtest P2P / RPC   | 39777 / 39776                                      |
| Mainnet magic       | `4F 50 58 4D` ("OPXM")                             |
| Mainnet address     | starts with `o` (PUBKEY prefix 115)                |
| Mining pools        | Miningcore-compatible (kawpow family)              |

Full parameter table with rationale is in `CHAINPARAMS.md`.

## How the fork is applied

The repo never ships a full copy of Ravencoin. Instead it carries new source
files (`src/pow/aserti32d.*`, `src/checkpointsync.*`) plus a Python
**configurator** that applies precise, anchored edits to a pristine Ravencoin
checkout, and a `rebrand.sh` that renames Raven→Opalyx. The driver runs them in
the correct order:

```
scripts/fork-from-ravencoin.sh
  1. git clone Ravencoin @ pinned commit
  2. copy the Opalyx overlay source files into src/
  3. scripts/configure-opalyx.py   (anchored edits to chainparams, pow, etc.)
  4. scripts/rebrand.sh            (Raven -> Opalyx renaming, runs LAST)
```

Then you build and mine genesis:

```
scripts/build-ubuntu.sh           # compile opalyxd & friends
scripts/generate-genesis.sh       # mine the 3 genesis blocks, patch params
scripts/build-ubuntu.sh           # rebuild with real genesis
```

See `INSTALL.md` for the full, copy-pasteable sequence and Windows notes, and
`TESTNET.md` to bring up a testnet (do this before mainnet).

## Documentation map

- `INSTALL.md` — build on Ubuntu 22.04, Windows notes, per-edit manual fallback
- `TESTNET.md` — stand up a testnet, mine, send a transaction
- `MINING.md` — GPU mining (solo and via Miningcore)
- `CHAINPARAMS.md` — every parameter and why it has that value
- `SECURITY.md` — deep-reorg protection, signed checkpoints, 51% reality, mainnet launch checklist
- `ROADMAP.md` — what is intentionally deferred (10 address groups, SLIP-44, P2P checkpoint relay)
- `TODO.md` — exact unfinished files/functions
- `NOTICE.md` — license / attribution (Ravencoin & Bitcoin are MIT)

## License

Opalyx inherits the MIT License from Ravencoin and Bitcoin Core. Existing
copyright notices are preserved; see `NOTICE.md`.
