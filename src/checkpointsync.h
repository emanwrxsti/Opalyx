// Copyright (c) 2024-2025 The Opalyx Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.
//
// Opalyx signed checkpoints (MVP).
//
// A signed checkpoint is a message {height, blockhash} signed by a
// hard-coded checkpoint master key. When a node holds a verified signed
// checkpoint, it will reject any block at that height whose hash differs
// from the signed hash. Combined with deep-reorg protection this lets the
// project pin the chain quickly during an incident without a software
// release.
//
// MVP scope (see TODO.md):
//   * Real secp256k1 signature verification against a hard-coded pubkey.
//   * Local in-memory enforcement via ContextualCheckBlockHeader.
//   * Injection via the -synccheckpoint=<height>:<hash>:<sig> config/arg,
//     loaded once on first consult (no init.cpp / RPC wiring required).
// NOT in MVP (roadmap, see TODO.md):
//   * Automatic P2P relay of the checkpoint message between peers.
//   * A dedicated setsynccheckpoint RPC.

#ifndef OPALYX_CHECKPOINTSYNC_H
#define OPALYX_CHECKPOINTSYNC_H

#include "uint256.h"

#include <string>
#include <vector>

struct CSignedCheckpoint {
    int32_t nHeight = -1;
    uint256 hashBlock;
    std::vector<unsigned char> vchSig;

    bool IsNull() const { return nHeight < 0; }

    // Bytes that get signed: 4-byte LE height followed by 32-byte block hash.
    std::vector<unsigned char> GetSignedPayload() const;
};

/** Hex-encoded compressed secp256k1 master public key (set per network). */
extern std::string g_strCheckpointMasterPubKey;

/** Verify the signature on cp against the configured master public key. */
bool VerifySignedCheckpoint(const CSignedCheckpoint &cp);

/** Verify and, if newer than what we hold, store as the active checkpoint. */
bool AcceptSignedCheckpoint(const CSignedCheckpoint &cp, std::string &strError);

/** Current active signed checkpoint (may be null). */
CSignedCheckpoint GetActiveSyncCheckpoint();

/**
 * Returns true if a block of the given hash is permitted at nHeight given the
 * active signed checkpoint. (Only constrains the exact checkpoint height.)
 */
bool CheckBlockAgainstSyncCheckpoint(int nHeight, const uint256 &hashBlock);

#endif // OPALYX_CHECKPOINTSYNC_H
