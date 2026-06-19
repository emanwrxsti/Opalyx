# INSTALL.md — Building Opalyx

This covers building `opalyxd` and friends from a fresh machine, plus a
manual fallback for every edit the configurator makes (in case an anchor
ever fails to match because you pinned a different Ravencoin commit).

> Nothing here was compiled in the environment that produced this repo. These
> are the standard Ravencoin/Bitcoin build steps adapted for Opalyx. Treat your
> first successful `make` as the real verification.

## 0. Prerequisites

- A 64-bit Linux box (Ubuntu 22.04 LTS assumed). 4+ GB RAM and several GB of
  free disk for the build. A 1-core/4 GB VM **can** build it but slowly; use
  `JOBS=1` and expect a long compile.
- `git`, `curl`, and `python3` on PATH.
- Network access to GitHub (to clone Ravencoin) and Ubuntu package mirrors.

## 1. Run the fork pipeline

From the `opalyx/` directory:

```bash
chmod +x scripts/*.sh scripts/*.py
./scripts/fork-from-ravencoin.sh
```

This clones Ravencoin at the pinned commit, copies the Opalyx overlay source
files into `src/`, runs the Python configurator (anchored edits), and finally
runs `rebrand.sh`. The result is a complete Opalyx source tree at
`./opalyx-src/` (the driver prints the exact path).

Environment overrides:

```bash
RVN_REPO=https://github.com/RavenProject/Ravencoin.git \
RVN_COMMIT=6d48ae0175b10283248146ae3080e2ba70966739 \
  ./scripts/fork-from-ravencoin.sh
```

If the configurator reports any `MISS` or `AMBIG`, it exits non-zero and changes
nothing for that edit. Apply that one edit by hand using the table in §5, or
re-run against the pinned commit (anchors target that exact source).

## 2. Build on Ubuntu 22.04

```bash
cd opalyx-src
../scripts/build-ubuntu.sh
```

`build-ubuntu.sh` installs build dependencies, builds Berkeley DB 4.8 via
Ravencoin's `contrib/install_db4.sh` (needed for wallet compatibility), then
runs `./autogen.sh`, `./configure`, and `make`. Useful knobs:

```bash
JOBS=4 ../scripts/build-ubuntu.sh          # parallelism (default: nproc)
WITH_GUI=1 ../scripts/build-ubuntu.sh      # also build opalyx-qt (needs Qt5)
```

The build dependencies it installs are:

```
build-essential libtool autotools-dev automake pkg-config bsdmainutils \
python3 libssl-dev libevent-dev libboost-system-dev libboost-filesystem-dev \
libboost-chrono-dev libboost-program-options-dev libboost-test-dev \
libboost-thread-dev libminiupnpc-dev libzmq3-dev
```

GUI builds additionally need `libqt5gui5 libqt5core5a libqt5dbus5 qttools5-dev
qttools5-dev-tools libqrencode-dev`.

On success you'll have, under `opalyx-src/src/`:

```
opalyxd        # the node daemon
opalyx-cli     # RPC client
opalyx-tx      # transaction tool
qt/opalyx-qt   # GUI wallet (only if WITH_GUI=1)
```

## 3. Mine the genesis blocks (one time)

The shipped chain params contain placeholder genesis values. Mine the real ones
and patch them in:

```bash
cd opalyx-src
../scripts/generate-genesis.sh
```

This runs the freshly built `opalyxd` three times with `-mine-genesis` (mainnet,
testnet, regtest), captures each `OPX-GENESIS ...` line, and `sed`s the real
nonce / genesis hash / merkle root into `src/chainparams.cpp` (backing up to
`.bak`). It errors out if any `__OPX_*__` placeholder remains.

Then **rebuild** so the real genesis is compiled in:

```bash
../scripts/build-ubuntu.sh
```

Verify there are no leftover placeholders:

```bash
grep -n "__OPX_" src/chainparams.cpp   # should print nothing
```

## 4. Windows build notes

Two supported routes; both mirror Ravencoin/Bitcoin Core practice:

**A. Cross-compile from Ubuntu (recommended).** Use the depends system:

```bash
cd opalyx-src/depends
make HOST=x86_64-w64-mingw32 -j4
cd ..
./autogen.sh
CONFIG_SITE=$PWD/depends/x86_64-w64-mingw32/share/config.site ./configure --prefix=/
make -j4
```

You need the MinGW-w64 toolchain (`g++-mingw-w64-x86-64`) and must select the
POSIX threading variant:

```bash
sudo update-alternatives --config x86_64-w64-mingw32-g++   # choose posix
```

**B. Native MSVC.** Ravencoin ships a `build_msvc/` solution. Open it in Visual
Studio 2019+, retarget to your installed toolset, and build the `opalyxd` /
`opalyx-cli` projects. After rebranding, the project files are renamed; if you
hit a stale path, search the solution for any remaining `raven` references.

Genesis mining (§3) must still be run once on whichever platform you build, or
you can mine on Linux and copy the patched `chainparams.cpp` before the Windows
build.

## 5. Manual fallback for each configurator edit

If an anchor fails (e.g. you pinned a newer Ravencoin), apply the edit by hand.
Files are relative to `opalyx-src/`.

| File | Change |
|------|--------|
| `src/Makefile.am` | Add `pow/aserti32d.h`, `pow/aserti32d.cpp`, `checkpointsync.h`, `checkpointsync.cpp` to the lib sources (next to the existing `pow.*` / `checkpoints.*` entries). |
| `src/consensus/consensus.h` | `COINBASE_MATURITY` `100` → `60`. |
| `src/consensus/params.h` | After `int64_t nPowTargetTimespan;` add fields: `bool fUseASERT;`, `int64_t nASERTHalfLife;`, `int64_t nDiffClampFactor;`, `int64_t nEmergencyGapSeconds;`. |
| `src/chainparamsbase.cpp` | RPC ports: main `8766`→`19776`, test `18766`→`29776`, regtest `18443`→`39776`. Testnet datadir `testnet7`→`testnet1`. |
| `src/pow.cpp` | Add `#include "pow/aserti32d.h"`; at the top of `GetNextWorkRequired`, `if (params.fUseASERT) return GetNextWorkRequiredASERT(pindexLast, pblock, params);`. |
| `src/validation.cpp` | Add `#include "checkpointsync.h"`; after `const int nHeight = pindexPrev->nHeight + 1;` in `ContextualCheckBlockHeader`, enforce `CheckBlockAgainstSyncCheckpoint(nHeight, block.GetHash())`. Add `-allowdeepreorg` bypass to the deep-reorg condition. |
| `src/chainparams.cpp` | Per network: subsidy halving `1051200`; `powLimit`/`kawpowLimit` = `00000000ffff…`; `nPowTargetSpacing = 2 * 60`; new genesis `CreateGenesisBlock(...)` line with placeholder nonce and `0x1d00ffff` (regtest `0x207fffff`); guarded genesis/merkle asserts; magic bytes; `nDefaultPort`; mainnet base58 prefixes (PUBKEY 115, SCRIPT 58, SECRET 178, EXT keys `04 4F 58 4D` / `04 4F 58 53`); `nExtCoinType = 2025` (main); DNS seeds; `nMaxReorganizationDepth = 720`; `nKAWPOWActivationTime = 1`; ASERT fields (main `fUseASERT=true, halflife=7200, clamp=4, emergency=1200`; test `true/3600/4/1200`; regtest `false/3600/4/0`). Also insert the inline `OpalyxMaybeMineGenesis` helper used by `-mine-genesis`. |

The configurator is the source of truth for exact strings; open
`scripts/configure-opalyx.py` and search for the file name if you need the
precise before/after text.

## 6. First run

```bash
cp opalyx.conf.sample ~/.opalyx/opalyx.conf   # then edit rpcpassword
./src/opalyxd -printtoconsole
./src/opalyx-cli getblockchaininfo
```

For testnet, see `TESTNET.md`.
