#!/usr/bin/env python3
# Copyright (c) 2024-2025 The Opalyx Core developers
# Distributed under the MIT software license.
#
# configure-opalyx.py
# ===================
# Applies the Opalyx (OPX) chain-parameter edits to a freshly cloned
# Ravencoin source tree (pinned commit 6d48ae0175b10283248146ae3080e2ba70966739).
#
# Design goals:
#   * ANCHORED string replacement, not line numbers (robust to drift).
#   * NEVER silently corrupt: if an anchor is missing or ambiguous, the edit
#     is reported LOUDLY and the script exits non-zero. Every automated edit
#     has a documented manual fallback in INSTALL.md / TODO.md.
#   * chainparams.cpp is split into its three network sections so values that
#     repeat across networks (powLimit, spacing, reorg depth, ...) are edited
#     in exactly the right place.
#
# Usage:
#     python3 configure-opalyx.py --src /path/to/clone/src
#     python3 configure-opalyx.py --src ./src --check   # dry run, report only
#
# After this runs successfully you must still MINE THE GENESIS BLOCKS:
#     ./scripts/generate-genesis.sh
# which fills the __OPX_*__ placeholders this script leaves behind.

import argparse
import os
import sys

# ----------------------------------------------------------------------------
# Opalyx constants (single source of truth; keep in sync with CHAINPARAMS.md)
# ----------------------------------------------------------------------------
GENESIS_TIME = 1735689600  # 2025-01-01 00:00:00 UTC (shared; hashes still differ)
GENESIS_REWARD = 2500      # OPX, tunable (see CHAINPARAMS.md)
HALVING_INTERVAL = 1051200 # ~4 years at 120 s
TARGET_SPACING_EXPR = "2 * 60"  # 120 s
REORG_DEPTH = 720
# powLimit / kawpowLimit: exactly 32 leading zero bits (REQUIRED by ASERT).
POW_LIMIT = "00000000ffff0000000000000000000000000000000000000000000000000000"

MASTER_PUBKEY_PLACEHOLDER = (
    "000000000000000000000000000000000000000000000000000000000000000000")

RESET = "\033[0m"; RED = "\033[31m"; GRN = "\033[32m"; YEL = "\033[33m"


class Configurator:
    def __init__(self, srcdir, check_only):
        self.src = srcdir
        self.check = check_only
        self.misses = []   # (file, description)
        self.applied = []  # (file, description)
        self._cache = {}   # path -> content

    # --- file helpers -------------------------------------------------------
    def _path(self, rel):
        return os.path.join(self.src, rel)

    def load(self, rel):
        if rel not in self._cache:
            p = self._path(rel)
            if not os.path.isfile(p):
                print(f"{RED}FATAL: missing file {p}{RESET}")
                sys.exit(2)
            with open(p, "r", encoding="utf-8", errors="surrogateescape") as f:
                self._cache[rel] = f.read()
        return self._cache[rel]

    def store(self, rel, content):
        self._cache[rel] = content

    def flush(self):
        if self.check:
            return
        for rel, content in self._cache.items():
            with open(self._path(rel), "w", encoding="utf-8",
                      errors="surrogateescape") as f:
                f.write(content)

    # --- core edit primitive ------------------------------------------------
    def edit(self, rel, desc, old, new, *, region=None, allow_missing=False):
        """Replace exactly one occurrence of `old` with `new`.

        If region is given, the search/replace happens only inside that
        substring and the *modified* region must be spliced back by the
        caller (used by the chainparams section editor). For whole-file edits
        region is None.

        Records a miss (loud, non-fatal-until-end) if `old` is absent or
        appears more than once.
        """
        haystack = region if region is not None else self.load(rel)
        count = haystack.count(old)
        if count == 0:
            if not allow_missing:
                self.misses.append((rel, desc))
                print(f"{RED}  MISS {RESET}{rel}: {desc}")
            return haystack if region is not None else None
        if count > 1:
            self.misses.append((rel, desc + f" [AMBIGUOUS: {count} matches]"))
            print(f"{RED}  AMBIG{RESET}{rel}: {desc} ({count} matches)")
            return haystack if region is not None else None
        result = haystack.replace(old, new, 1)
        self.applied.append((rel, desc))
        print(f"{GRN}  ok   {RESET}{rel}: {desc}")
        if region is not None:
            return result
        self.store(rel, result)
        return result

    # --- chainparams section splitter --------------------------------------
    def split_chainparams(self, content):
        """Return (preamble, main, test, regtest) by class boundaries."""
        m1 = content.find("class CMainParams")
        m2 = content.find("class CTestNetParams")
        m3 = content.find("class CRegTestParams")
        if -1 in (m1, m2, m3) or not (m1 < m2 < m3):
            print(f"{RED}FATAL: cannot locate the three CChainParams classes "
                  f"in chainparams.cpp (offsets {m1},{m2},{m3}).{RESET}")
            sys.exit(2)
        return content[:m1], content[m1:m2], content[m2:m3], content[m3:]

    # ========================================================================
    # Per-file edit programs
    # ========================================================================
    def do_makefile(self):
        rel = "Makefile.am"
        # Headers: add after pow.h and checkpoints.h.
        self.edit(rel, "add pow/aserti32d.h to BITCOIN_CORE_H",
                  "  pow.h \\\n", "  pow.h \\\n  pow/aserti32d.h \\\n")
        self.edit(rel, "add checkpointsync.h to BITCOIN_CORE_H",
                  "  checkpoints.h \\\n", "  checkpoints.h \\\n  checkpointsync.h \\\n")
        # Sources: add to libraven_server_a_SOURCES after pow.cpp / checkpoints.cpp.
        self.edit(rel, "add pow/aserti32d.cpp to server sources",
                  "  pow.cpp \\\n", "  pow.cpp \\\n  pow/aserti32d.cpp \\\n")
        self.edit(rel, "add checkpointsync.cpp to server sources",
                  "  checkpoints.cpp \\\n", "  checkpoints.cpp \\\n  checkpointsync.cpp \\\n")

    def do_consensus_h(self):
        rel = "consensus/consensus.h"
        self.edit(rel, "COINBASE_MATURITY 100 -> 60",
                  "static const int COINBASE_MATURITY = 100;",
                  "static const int COINBASE_MATURITY = 60;")

    def do_params_h(self):
        rel = "consensus/params.h"
        self.edit(rel, "add ASERT fields to Consensus::Params",
                  "    int64_t nPowTargetTimespan;\n",
                  "    int64_t nPowTargetTimespan;\n"
                  "    // --- Opalyx ASERT (aserti3-2d) difficulty parameters ---\n"
                  "    bool fUseASERT;             //!< use per-block ASERT instead of legacy retarget\n"
                  "    int64_t nASERTHalfLife;     //!< ASERT half-life in seconds\n"
                  "    int64_t nDiffClampFactor;   //!< max per-step target move factor (e.g. 4 => 4x/0.25x)\n"
                  "    int64_t nEmergencyGapSeconds; //!< if a gap exceeds this, lift clamp upper bound for fast recovery\n")

    def do_chainparamsbase(self):
        rel = "chainparamsbase.cpp"
        self.edit(rel, "main RPC port 8766 -> 19776",
                  "nRPCPort = 8766;", "nRPCPort = 19776;")
        self.edit(rel, "testnet RPC port 18766 -> 29776",
                  "nRPCPort = 18766;", "nRPCPort = 29776;")
        self.edit(rel, "testnet datadir testnet7 -> testnet1",
                  'strDataDir = "testnet7";', 'strDataDir = "testnet1";')
        self.edit(rel, "regtest RPC port 18443 -> 39776",
                  "nRPCPort = 18443;", "nRPCPort = 39776;")

    def do_pow_cpp(self):
        rel = "pow.cpp"
        self.edit(rel, "include pow/aserti32d.h",
                  '#include "pow.h"\n',
                  '#include "pow.h"\n#include "pow/aserti32d.h"\n')
        self.edit(rel, "dispatch to ASERT first in GetNextWorkRequired",
                  "unsigned int GetNextWorkRequired(const CBlockIndex* pindexLast, "
                  "const CBlockHeader *pblock, const Consensus::Params& params)\n{\n",
                  "unsigned int GetNextWorkRequired(const CBlockIndex* pindexLast, "
                  "const CBlockHeader *pblock, const Consensus::Params& params)\n{\n"
                  "    // Opalyx: per-block ASERT difficulty (preferred path). "
                  "See pow/aserti32d.cpp.\n"
                  "    if (params.fUseASERT) {\n"
                  "        return GetNextWorkRequiredASERT(pindexLast, pblock, params);\n"
                  "    }\n")

    def do_validation_cpp(self):
        rel = "validation.cpp"
        self.edit(rel, "include checkpointsync.h",
                  '#include "checkpoints.h"\n',
                  '#include "checkpoints.h"\n#include "checkpointsync.h"\n')
        self.edit(rel, "enforce signed checkpoint in ContextualCheckBlockHeader",
                  "    assert(pindexPrev != nullptr);\n"
                  "    const int nHeight = pindexPrev->nHeight + 1;\n",
                  "    assert(pindexPrev != nullptr);\n"
                  "    const int nHeight = pindexPrev->nHeight + 1;\n\n"
                  "    // Opalyx: enforce the active signed checkpoint (if any) at its height.\n"
                  "    if (!CheckBlockAgainstSyncCheckpoint(nHeight, block.GetHash())) {\n"
                  "        return state.DoS(100, error(\"%s: block at height %d "
                  "rejected by signed checkpoint\", __func__, nHeight),\n"
                  "                         REJECT_INVALID, \"bad-fork-signed-checkpoint\");\n"
                  "    }\n")
        self.edit(rel, "-allowdeepreorg emergency override",
                  "    bool fGreaterThanMaxReorg = (chainActive.Height() - "
                  "(nHeight - 1)) >= nMaxReorgDepth;\n"
                  "    if (fGreaterThanMaxReorg && g_connman) {\n",
                  "    bool fAllowDeepReorg = gArgs.GetBoolArg(\"-allowdeepreorg\", false);\n"
                  "    bool fGreaterThanMaxReorg = (chainActive.Height() - "
                  "(nHeight - 1)) >= nMaxReorgDepth;\n"
                  "    if (fGreaterThanMaxReorg && !fAllowDeepReorg && g_connman) {\n")

    # --- chainparams.cpp: preamble (timestamp + inline genesis miner) -------
    def do_chainparams(self):
        rel = "chainparams.cpp"
        content = self.load(rel)
        pre, main, test, reg = self.split_chainparams(content)

        # ---- preamble edits ----
        pre = self.edit(rel, "extra includes for inline genesis miner",
                        '#include "arith_uint256.h"\n',
                        '#include "arith_uint256.h"\n#include <cstdio>\n'
                        '#include <cstdlib>\n',
                        region=pre)
        pre = self.edit(rel, "Opalyx genesis timestamp string",
                        '"The Times 03/Jan/2018 Bitcoin is name of the game for '
                        'new generation of firms"',
                        '"Opalyx 01/Jan/2025 A fair-launch KawPow chain forged '
                        'in the open"',
                        region=pre)
        # Insert the inline genesis miner helper after the CreateGenesisBlock wrapper.
        anchor = ("    return CreateGenesisBlock(pszTimestamp, genesisOutputScript, "
                  "nTime, nNonce, nBits, nVersion, genesisReward);\n}\n")
        miner = anchor + (
            "\n"
            "// Opalyx inline genesis miner. Enabled only with -mine-genesis.\n"
            "// Mines the active network's genesis nonce, prints the result on a\n"
            "// single OPX-GENESIS line, then exits. scripts/generate-genesis.sh\n"
            "// runs the daemon once per network and seds the values back in.\n"
            "static void OpalyxMaybeMineGenesis(const char* net, CBlock& genesis)\n"
            "{\n"
            "    if (!gArgs.GetBoolArg(\"-mine-genesis\", false)) return;\n"
            "    arith_uint256 bnTarget;\n"
            "    bool fNeg = false, fOver = false;\n"
            "    bnTarget.SetCompact(genesis.nBits, &fNeg, &fOver);\n"
            "    std::fprintf(stderr, \"Opalyx: mining genesis for %s (this can take a while)...\\n\", net);\n"
            "    for (uint64_t n = 0; n <= 0xffffffffULL; ++n) {\n"
            "        genesis.nNonce = (uint32_t)n;\n"
            "        uint256 h = genesis.GetX16RHash();\n"
            "        if (UintToArith256(h) <= bnTarget) {\n"
            "            std::printf(\"OPX-GENESIS net=%s time=%u nonce=%u bits=%08x merkle=%s hash=%s\\n\",\n"
            "                        net, genesis.nTime, genesis.nNonce, genesis.nBits,\n"
            "                        genesis.hashMerkleRoot.ToString().c_str(), h.ToString().c_str());\n"
            "            std::fflush(stdout);\n"
            "            std::exit(0);\n"
            "        }\n"
            "    }\n"
            "    std::fprintf(stderr, \"OPX-GENESIS net=%s NO SOLUTION in nonce range; bump GENESIS_TIME.\\n\", net);\n"
            "    std::exit(1);\n"
            "}\n")
        pre = self.edit(rel, "insert inline genesis miner helper",
                        anchor, miner, region=pre)

        # ---- main network ----
        main = self.section_common(rel, "main", main, halving=True)
        main = self.genesis_main(rel, main)
        main = self.edit(rel, "[main] magic bytes -> OPXM",
                         "        pchMessageStart[0] = 0x52; // R\n"
                         "        pchMessageStart[1] = 0x41; // A\n"
                         "        pchMessageStart[2] = 0x56; // V\n"
                         "        pchMessageStart[3] = 0x4e; // N\n",
                         "        pchMessageStart[0] = 0x4F; // O\n"
                         "        pchMessageStart[1] = 0x50; // P\n"
                         "        pchMessageStart[2] = 0x58; // X\n"
                         "        pchMessageStart[3] = 0x4D; // M\n",
                         region=main)
        main = self.edit(rel, "[main] P2P port 8767 -> 19777",
                         "nDefaultPort = 8767;", "nDefaultPort = 19777;", region=main)
        main = self.edit(rel, "[main] base58 prefixes -> 115/58/178",
                         "        base58Prefixes[PUBKEY_ADDRESS] = std::vector<unsigned char>(1,60);\n"
                         "        base58Prefixes[SCRIPT_ADDRESS] = std::vector<unsigned char>(1,122);\n"
                         "        base58Prefixes[SECRET_KEY] =     std::vector<unsigned char>(1,128);\n"
                         "        base58Prefixes[EXT_PUBLIC_KEY] = {0x04, 0x88, 0xB2, 0x1E};\n"
                         "        base58Prefixes[EXT_SECRET_KEY] = {0x04, 0x88, 0xAD, 0xE4};\n",
                         "        base58Prefixes[PUBKEY_ADDRESS] = std::vector<unsigned char>(1,115); // 'o'\n"
                         "        base58Prefixes[SCRIPT_ADDRESS] = std::vector<unsigned char>(1,58);\n"
                         "        base58Prefixes[SECRET_KEY] =     std::vector<unsigned char>(1,178);\n"
                         "        base58Prefixes[EXT_PUBLIC_KEY] = {0x04, 0x4F, 0x58, 0x4D};\n"
                         "        base58Prefixes[EXT_SECRET_KEY] = {0x04, 0x4F, 0x58, 0x53};\n",
                         region=main)
        main = self.edit(rel, "[main] nExtCoinType 175 -> 2025 (not yet SLIP-44 registered)",
                         "nExtCoinType = 175;", "nExtCoinType = 2025;", region=main)
        main = self.edit(rel, "[main] DNS seeds -> Opalyx",
                         '        vSeeds.emplace_back("seed-raven.bitactivate.com", false);\n'
                         '        vSeeds.emplace_back("seed-raven.ravencoin.com", false);\n'
                         '        vSeeds.emplace_back("seed-raven.ravencoin.org", false);\n',
                         '        // TODO(operator): register and run these before mainnet (see SECURITY.md).\n'
                         '        vSeeds.emplace_back("seed.opalyx.org", false);\n'
                         '        vSeeds.emplace_back("seed2.opalyx.org", false);\n'
                         '        vSeeds.emplace_back("dnsseed.opalyx.network", false);\n',
                         region=main)

        # ---- testnet ----
        test = self.section_common(rel, "test", test, halving=True)
        test = self.genesis_test(rel, test)
        test = self.edit(rel, "[test] magic bytes -> OPXT",
                         "        pchMessageStart[0] = 0x52; // R\n"
                         "        pchMessageStart[1] = 0x56; // V\n"
                         "        pchMessageStart[2] = 0x4E; // N\n"
                         "        pchMessageStart[3] = 0x54; // T\n",
                         "        pchMessageStart[0] = 0x4F; // O\n"
                         "        pchMessageStart[1] = 0x50; // P\n"
                         "        pchMessageStart[2] = 0x58; // X\n"
                         "        pchMessageStart[3] = 0x54; // T\n",
                         region=test)
        test = self.edit(rel, "[test] P2P port 18770 -> 29777",
                         "nDefaultPort = 18770;", "nDefaultPort = 29777;", region=test)
        test = self.edit(rel, "[test] enable ASERT min-difficulty testnet rule note",
                         '        vSeeds.emplace_back("seed-testnet-raven.bitactivate.com", false);\n'
                         '        vSeeds.emplace_back("seed-testnet-raven.ravencoin.com", false);\n'
                         '        vSeeds.emplace_back("seed-testnet-raven.ravencoin.org", false);\n',
                         '        vSeeds.emplace_back("testnet-seed.opalyx.org", false);\n'
                         '        vSeeds.emplace_back("testnet-seed2.opalyx.org", false);\n',
                         region=test)
        # testnet keeps conventional 111/196/239 prefixes + cointype 1 (intentional).

        # ---- regtest ----
        reg = self.genesis_regtest(rel, reg)
        reg = self.edit(rel, "[regtest] magic bytes -> OPXR",
                        "        pchMessageStart[0] = 0x43; // C\n"
                        "        pchMessageStart[1] = 0x52; // R\n"
                        "        pchMessageStart[2] = 0x4F; // O\n"
                        "        pchMessageStart[3] = 0x57; // W\n",
                        "        pchMessageStart[0] = 0x4F; // O\n"
                        "        pchMessageStart[1] = 0x50; // P\n"
                        "        pchMessageStart[2] = 0x58; // X\n"
                        "        pchMessageStart[3] = 0x52; // R\n",
                        region=reg)
        reg = self.edit(rel, "[regtest] P2P port 18444 -> 39777",
                        "nDefaultPort = 18444;", "nDefaultPort = 39777;", region=reg)
        # regtest difficulty: leave fPowNoRetargeting true => ASERT skipped. Still set
        # fUseASERT=false explicitly below in the ASERT-fields injector.

        # Re-assemble and store, then run the cross-section ASERT-field + reorg
        # + kawpow injections that apply identically to every section.
        content = pre + main + test + reg
        self.store(rel, content)
        self.inject_all_sections(rel)

    # Shared NON-genesis edits for a network section: halving (main/test only),
    # powLimit, kawpowLimit, spacing.
    def section_common(self, rel, name, sec, *, halving):
        if halving:
            sec = self.edit(rel, f"[{name}] halving interval -> {HALVING_INTERVAL}",
                            "consensus.nSubsidyHalvingInterval = 2100000;",
                            f"consensus.nSubsidyHalvingInterval = {HALVING_INTERVAL};",
                            region=sec)
        sec = self.edit(rel, f"[{name}] powLimit -> 32 leading zero bits",
                        'consensus.powLimit = uint256S("00000fffffffffffffffffffffffff'
                        'ffffffffffffffffffffffffffffffffff");',
                        f'consensus.powLimit = uint256S("{POW_LIMIT}");',
                        region=sec)
        # kawpowLimit differs by network in RVN; match powLimit for both.
        # Build anchors programmatically (avoids miscounting the f-run).
        kaw_main = 'consensus.kawpowLimit = uint256S("' + ("0" * 10 + "f" * 54) + \
                   '"); // Estimated starting diff for first 180 kawpow blocks'
        kaw_test = 'consensus.kawpowLimit = uint256S("' + ("0" * 6 + "f" * 58) + '");'
        for kp in (kaw_main, kaw_test):
            if kp in sec:
                sec = self.edit(rel, f"[{name}] kawpowLimit -> powLimit",
                                kp, f'consensus.kawpowLimit = uint256S("{POW_LIMIT}");',
                                region=sec)
                break
        else:
            self.misses.append((rel, f"[{name}] kawpowLimit anchor not found"))
            print(f"{RED}  MISS {RESET}{rel}: [{name}] kawpowLimit anchor not found")
        sec = self.edit(rel, f"[{name}] target spacing 1*60 -> {TARGET_SPACING_EXPR}",
                        "consensus.nPowTargetSpacing = 1 * 60;",
                        f"consensus.nPowTargetSpacing = {TARGET_SPACING_EXPR};",
                        region=sec)
        return sec

    # Explicit genesis handling per network (create line + guarded asserts).
    def genesis_main(self, rel, sec):
        sec = self.edit(rel, "[main] genesis CreateGenesisBlock",
                        "genesis = CreateGenesisBlock(1514999494, 25023712, 0x1e00ffff, 4, 5000 * COIN);",
                        f"genesis = CreateGenesisBlock({GENESIS_TIME}, __OPX_NONCE_MAIN__, "
                        f"0x1d00ffff, 4, {GENESIS_REWARD} * COIN);", region=sec)
        sec = self.edit(rel, "[main] guard genesis hash assert + miner call",
                        '        consensus.hashGenesisBlock = genesis.GetX16RHash();\n\n'
                        '        assert(consensus.hashGenesisBlock == uint256S("0000006b444bc2f2'
                        'ffe627be9d9e7e7a0730000870ef6eb6da46c8eae389df90"));\n',
                        '        consensus.hashGenesisBlock = genesis.GetX16RHash();\n'
                        '        OpalyxMaybeMineGenesis("main", genesis);\n\n'
                        '        if (!gArgs.GetBoolArg("-mine-genesis", false))\n'
                        '            assert(consensus.hashGenesisBlock == uint256S("__OPX_GENHASH_MAIN__"));\n',
                        region=sec)
        sec = self.edit(rel, "[main] guard merkle assert",
                        '        assert(genesis.hashMerkleRoot == uint256S("28ff00a867739a3'
                        '52523808d301f504bc4547699398d70faf2266a8bae5f3516"));\n',
                        '        if (!gArgs.GetBoolArg("-mine-genesis", false))\n'
                        '            assert(genesis.hashMerkleRoot == uint256S("__OPX_MERKLE__"));\n',
                        region=sec)
        return sec

    def genesis_test(self, rel, sec):
        # Testnet uses nGenesisTime variable, version 2, nonce 15615880.
        sec = self.edit(rel, "[test] pin nGenesisTime to GENESIS_TIME",
                        "uint32_t nGenesisTime = 1537466400;",
                        f"uint32_t nGenesisTime = {GENESIS_TIME};", region=sec)
        sec = self.edit(rel, "[test] genesis CreateGenesisBlock",
                        "genesis = CreateGenesisBlock(nGenesisTime, 15615880, 0x1e00ffff, 2, 5000 * COIN);",
                        f"genesis = CreateGenesisBlock(nGenesisTime, __OPX_NONCE_TEST__, "
                        f"0x1d00ffff, 4, {GENESIS_REWARD} * COIN);", region=sec)
        sec = self.edit(rel, "[test] guard genesis hash assert + miner call",
                        '        consensus.hashGenesisBlock = genesis.GetX16RHash();\n\n'
                        '        //Test MerkleRoot and GenesisBlock\n'
                        '        assert(consensus.hashGenesisBlock == uint256S("0x000000ecfc5e6324'
                        'a079542221d00e10362bdc894d56500c414060eea8a3ad5a"));\n',
                        '        consensus.hashGenesisBlock = genesis.GetX16RHash();\n'
                        '        OpalyxMaybeMineGenesis("test", genesis);\n\n'
                        '        //Test MerkleRoot and GenesisBlock\n'
                        '        if (!gArgs.GetBoolArg("-mine-genesis", false))\n'
                        '            assert(consensus.hashGenesisBlock == uint256S("__OPX_GENHASH_TEST__"));\n',
                        region=sec)
        sec = self.edit(rel, "[test] guard merkle assert",
                        '        assert(genesis.hashMerkleRoot == uint256S("28ff00a867739a3'
                        '52523808d301f504bc4547699398d70faf2266a8bae5f3516"));\n',
                        '        if (!gArgs.GetBoolArg("-mine-genesis", false))\n'
                        '            assert(genesis.hashMerkleRoot == uint256S("__OPX_MERKLE__"));\n',
                        region=sec)
        return sec

    def genesis_regtest(self, rel, reg):
        reg = self.edit(rel, "[regtest] genesis reward + nonce token (keep 0x207fffff)",
                        "genesis = CreateGenesisBlock(1524179366, 1, 0x207fffff, 4, 5000 * COIN);",
                        f"genesis = CreateGenesisBlock({GENESIS_TIME}, __OPX_NONCE_REGTEST__, "
                        f"0x207fffff, 4, {GENESIS_REWARD} * COIN);", region=reg)
        reg = self.edit(rel, "[regtest] guard genesis hash assert + miner call",
                        '        consensus.hashGenesisBlock = genesis.GetX16RHash();\n\n'
                        '        assert(consensus.hashGenesisBlock == uint256S("0x0b2c703dc9'
                        '3bb63a36c4e33b85be4855ddbca2ac951a7a0a29b8de0408200a3c "));\n',
                        '        consensus.hashGenesisBlock = genesis.GetX16RHash();\n'
                        '        OpalyxMaybeMineGenesis("regtest", genesis);\n\n'
                        '        if (!gArgs.GetBoolArg("-mine-genesis", false))\n'
                        '            assert(consensus.hashGenesisBlock == uint256S("__OPX_GENHASH_REGTEST__"));\n',
                        region=reg)
        reg = self.edit(rel, "[regtest] guard merkle assert",
                        '        assert(genesis.hashMerkleRoot == uint256S("0x28ff00a867739a3'
                        '52523808d301f504bc4547699398d70faf2266a8bae5f3516"));\n',
                        '        if (!gArgs.GetBoolArg("-mine-genesis", false))\n'
                        '            assert(genesis.hashMerkleRoot == uint256S("__OPX_MERKLE__"));\n',
                        region=reg)
        return reg

    def inject_all_sections(self, rel):
        """Edits that appear once per network section, applied across the file:
        reorg depth (3x), kawpow activation (3x), and ASERT field assignment."""
        content = self.load(rel)
        # reorg depth: same string 3 times -> replace all.
        old_reorg = ("        nMaxReorganizationDepth = 60; // 60 at 1 minute block "
                     "timespan is +/- 60 minutes.\n")
        n = content.count(old_reorg)
        if n == 0:
            self.misses.append((rel, "nMaxReorganizationDepth anchor (x3)"))
            print(f"{RED}  MISS {RESET}{rel}: nMaxReorganizationDepth anchor")
        else:
            content = content.replace(
                old_reorg,
                f"        nMaxReorganizationDepth = {REORG_DEPTH}; // Opalyx: reject "
                f"reorgs deeper than {REORG_DEPTH} blocks (override: -allowdeepreorg).\n")
            print(f"{GRN}  ok   {RESET}{rel}: nMaxReorganizationDepth -> {REORG_DEPTH} ({n}x)")
            self.applied.append((rel, f"nMaxReorganizationDepth -> {REORG_DEPTH} ({n}x)"))
        # kawpow activation from block 1: same string 3 times.
        old_kaw = "        nKAWPOWActivationTime = nKAAAWWWPOWActivationTime;\n"
        n = content.count(old_kaw)
        if n == 0:
            self.misses.append((rel, "nKAWPOWActivationTime anchor (x3)"))
            print(f"{RED}  MISS {RESET}{rel}: nKAWPOWActivationTime anchor")
        else:
            content = content.replace(
                old_kaw,
                "        nKAWPOWActivationTime = 1; // Opalyx: KawPow active from genesis.\n")
            print(f"{GRN}  ok   {RESET}{rel}: nKAWPOWActivationTime -> 1 ({n}x)")
            self.applied.append((rel, f"nKAWPOWActivationTime -> 1 ({n}x)"))
        self.store(rel, content)

        # ASERT consensus fields: insert per network just after the spacing line.
        # main + test => ASERT on; regtest => off (keeps fPowNoRetargeting path).
        self.inject_asert_fields(rel)

    def inject_asert_fields(self, rel):
        content = self.load(rel)
        pre, main, test, reg = self.split_chainparams(content)

        def block(use, halflife, clamp, emerg):
            return (f"        consensus.fUseASERT = {use};\n"
                    f"        consensus.nASERTHalfLife = {halflife};\n"
                    f"        consensus.nDiffClampFactor = {clamp};\n"
                    f"        consensus.nEmergencyGapSeconds = {emerg};\n")

        anchor = f"        consensus.nPowTargetSpacing = {TARGET_SPACING_EXPR};\n"
        main = self.edit(rel, "[main] set ASERT fields", anchor,
                         anchor + block("true", 7200, 4, 1200), region=main)
        test = self.edit(rel, "[test] set ASERT fields", anchor,
                         anchor + block("true", 3600, 4, 1200), region=test)
        # regtest spacing was 1*60 too; we changed it via section? No—regtest spacing
        # not edited by section_common, so anchor is the original 1*60.
        reg_anchor = "        consensus.nPowTargetSpacing = 1 * 60;\n"
        reg = self.edit(rel, "[regtest] set ASERT fields (disabled)", reg_anchor,
                        reg_anchor + block("false", 3600, 4, 0), region=reg,
                        allow_missing=True)
        self.store(rel, pre + main + test + reg)

    # ========================================================================
    def run(self):
        print(f"{YEL}Opalyx configurator: editing tree at {self.src}{RESET}")
        self.do_makefile()
        self.do_consensus_h()
        self.do_params_h()
        self.do_chainparamsbase()
        self.do_pow_cpp()
        self.do_validation_cpp()
        self.do_chainparams()

        print()
        print(f"{GRN}Applied {len(self.applied)} edits.{RESET}")
        if self.misses:
            print(f"{RED}{'='*70}{RESET}")
            print(f"{RED}{len(self.misses)} ANCHOR(S) NOT APPLIED — APPLY THESE MANUALLY{RESET}")
            print(f"{RED}(see INSTALL.md > 'Manual fallback edits' and TODO.md){RESET}")
            for f, d in self.misses:
                print(f"{RED}  - {f}: {d}{RESET}")
            print(f"{RED}{'='*70}{RESET}")
            return 1
        self.flush()
        if self.check:
            print(f"{YEL}--check: no files written.{RESET}")
        else:
            print(f"{GRN}All edits written. Next: ./scripts/generate-genesis.sh{RESET}")
        return 0


def main():
    ap = argparse.ArgumentParser(description="Apply Opalyx fork edits to a Ravencoin src tree.")
    ap.add_argument("--src", default="./src", help="path to the cloned src/ directory")
    ap.add_argument("--check", action="store_true", help="dry run; report only, write nothing")
    args = ap.parse_args()
    if not os.path.isdir(args.src):
        print(f"{RED}FATAL: --src '{args.src}' is not a directory{RESET}")
        sys.exit(2)
    sys.exit(Configurator(args.src, args.check).run())


if __name__ == "__main__":
    main()
