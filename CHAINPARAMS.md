# CHAINPARAMS.md — Opalyx parameters and rationale

Every consensus / network value Opalyx sets, what it is, and why. Values are the
ones applied by `scripts/configure-opalyx.py`; that script is the source of
truth if anything here ever drifts.

## Identity

| Param | Value | Notes |
|-------|-------|-------|
| Name | Opalyx | |
| Ticker | OPX | `RVN` → `OPX` during rebrand |
| Algorithm | KawPow | Inherited from Ravencoin; GPU PoW |
| KawPow activation | block 1 (`nKAWPOWActivationTime = 1`) | No legacy X16R phase — KawPow from genesis. |

## Emission

| Param | Value | Rationale |
|-------|-------|-----------|
| Block target | 120 s (`nPowTargetSpacing = 2 * 60`) | Spec requirement. Balances confirmation latency against orphan rate. |
| Initial reward | 2500 OPX | Tunable before launch (`GENESIS_REWARD` in the configurator). Change it **before** mining genesis. |
| Halving interval | 1,051,200 blocks | ≈ 4 years at 120 s/block (`365.25 * 24 * 3600 / 120 * 4 ≈ 1,051,920`; rounded to a clean 1,051,200). |
| Premine | none | The genesis coinbase is unspendable by Bitcoin/Ravencoin convention; no extra premine outputs are added. |
| Coinbase maturity | 60 blocks | `COINBASE_MATURITY 100 → 60`. 60 × 120 s = 7200 s = **exactly 2 hours** spend delay, per spec. |

## Difficulty (ASERT)

Opalyx replaces Bitcoin's 2016-block retarget with **per-block ASERT**
(absolute-scheduled exponentially rising targets, the aserti3-2d integer
algorithm). The anchor is the genesis block (height 0) with a synthetic parent
timestamp of `genesisTime − spacing`, which keeps difficulty constant when blocks
arrive exactly on schedule (verified numerically).

| Param | Main | Test | Regtest | Rationale |
|-------|------|------|---------|-----------|
| `fUseASERT` | true | true | false | Regtest keeps Bitcoin's `fPowNoRetargeting` path so `generatetoaddress` stays trivial. |
| `nASERTHalfLife` | 7200 s | 3600 s | 3600 s | Mainnet half-life = 2 h: difficulty halves/doubles per 2 h of schedule error. Testnet reacts twice as fast for quicker iteration. |
| `nDiffClampFactor` | 4 | 4 | 4 | Limits a single block's target move to 4× easier / 0.25× harder under normal conditions, damping oscillation. |
| `nEmergencyGapSeconds` | 1200 s | 1200 s | 0 | If the gap since the last block exceeds this (blocks far behind schedule), the clamp's *upper* (easier) bound is lifted so difficulty can fall fast and the chain recovers after a 90–99% hashrate drop. |

Why ASERT over LWMA: ASERT is memoryless and absolute-scheduled, so it cannot be
gamed by timestamp manipulation across a window the way windowed averages can,
and it recovers smoothly from large hashrate swings. The clamp prevents wild
single-block swings; the emergency path prevents the clamp from trapping the
chain at high difficulty after a hashrate collapse.

### PoW limits

| Param | Value | Notes |
|-------|-------|-------|
| `powLimit` (main/test) | `00000000ffff0000…0000` | Exactly 32 leading zero bits. Required: ASERT asserts `(powLimit >> 224) == 0`. Compact form `0x1d00ffff`. |
| `kawpowLimit` (main/test) | same as `powLimit` | |
| Genesis `nBits` (main/test) | `0x1d00ffff` | Matches `powLimit`. |
| `powLimit` (regtest) | `7fffff…` | Trivial difficulty for local testing. |
| Genesis `nBits` (regtest) | `0x207fffff` | |

## Network magic (`pchMessageStart`)

| Network | Bytes | ASCII |
|---------|-------|-------|
| Mainnet | `4F 50 58 4D` | OPXM |
| Testnet | `4F 50 58 54` | OPXT |
| Regtest | `4F 50 58 52` | OPXR |

Unique magic bytes prevent Opalyx nodes from accidentally peering with Ravencoin
or any other fork.

## Ports

| Network | P2P | RPC |
|---------|-----|-----|
| Mainnet | 19777 | 19776 |
| Testnet | 29777 | 29776 |
| Regtest | 39777 | 39776 |

## Addresses (Base58 / BIP32)

Set on **mainnet** (testnet keeps conventional prefixes 111/196/239 on purpose,
so standard testnet tooling and the `nExtCoinType=1` testnet convention work):

| Param | Value | Notes |
|-------|-------|-------|
| `PUBKEY_ADDRESS` | 115 | Renders a leading **`o`** in Base58Check — Opalyx branding. |
| `SCRIPT_ADDRESS` | 58 | |
| `SECRET_KEY` | 178 | WIF prefix. |
| `EXT_PUBLIC_KEY` | `04 4F 58 4D` | "xpub"-equivalent, OPX-flavored. |
| `EXT_SECRET_KEY` | `04 4F 58 53` | |
| `nExtCoinType` (main) | 2025 | **Not yet SLIP-44 registered.** Registration is a roadmap item (`ROADMAP.md`); until then this value could in principle collide with another project's wallet derivation. |
| `nExtCoinType` (test) | 1 | Standard testnet convention. |

## Genesis

| Param | Value | Notes |
|-------|-------|-------|
| `GENESIS_TIME` | 1735689600 | 2025-01-01 00:00:00 UTC. Shared across all three networks. |
| Coinbase message | `Opalyx 01/Jan/2025 A fair-launch KawPow chain forged in the open` | |
| Genesis nonce / hash / merkle | **placeholders** until mined | `__OPX_NONCE_*__`, `__OPX_GENHASH_*__`, `__OPX_MERKLE__`; filled by `generate-genesis.sh`. |

The merkle root is identical across networks (the coinbase — timestamp string +
output script + reward — is shared, and the merkle root doesn't depend on the
header's time/version/bits/nonce). The genesis **block hashes** still differ per
network because magic/params and the mined nonce differ.

## Security parameters

| Param | Value | Notes |
|-------|-------|-------|
| `nMaxReorganizationDepth` | 720 (all networks) | Reorgs deeper than 720 blocks (~24 h) are rejected. Override: `-allowdeepreorg=1` (emergency only). |
| Signed checkpoints | opt-in via `-synccheckpoint=HEIGHT:HASH:SIG` | Verified against a compiled-in master pubkey (`g_strCheckpointMasterPubKey`, currently a placeholder that must be replaced before mainnet). See `SECURITY.md`. |

## Things you MUST change before mainnet

1. Mine genesis and remove all `__OPX_*__` placeholders.
2. Replace `g_strCheckpointMasterPubKey` with a real key (`sign-checkpoint.py genkey`).
3. Register and run real DNS seeds (placeholders won't resolve).
4. Decide on the initial reward (`GENESIS_REWARD`) before mining genesis.
5. Register `nExtCoinType` with SLIP-44 (or accept the collision risk knowingly).

See `TODO.md` and `SECURITY.md` for the full launch gate.
