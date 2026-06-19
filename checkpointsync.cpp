// Copyright (c) 2024-2025 The Opalyx Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include "checkpointsync.h"

#include "hash.h"
#include "pubkey.h"
#include "sync.h"
#include "util.h"
#include "utilstrencodings.h"

#include <mutex>

// Hard-coded checkpoint master public key (compressed, hex).
// REPLACE before mainnet launch:  ./scripts/sign-checkpoint.py genkey
// Paste the public key here; keep the private key OFFLINE.
std::string g_strCheckpointMasterPubKey =
    "000000000000000000000000000000000000000000000000000000000000000000"; // placeholder (invalid)

static CCriticalSection cs_synccheckpoint;
static CSignedCheckpoint g_activeCheckpoint;
static std::once_flag g_loadOnce;

std::vector<unsigned char> CSignedCheckpoint::GetSignedPayload() const {
    std::vector<unsigned char> v;
    v.reserve(4 + 32);
    uint32_t h = uint32_t(nHeight);
    v.push_back(uint8_t(h & 0xff));
    v.push_back(uint8_t((h >> 8) & 0xff));
    v.push_back(uint8_t((h >> 16) & 0xff));
    v.push_back(uint8_t((h >> 24) & 0xff));
    const unsigned char *p = hashBlock.begin();
    v.insert(v.end(), p, p + 32);
    return v;
}

bool VerifySignedCheckpoint(const CSignedCheckpoint &cp) {
    if (cp.IsNull() || cp.vchSig.empty()) return false;
    if (!IsHex(g_strCheckpointMasterPubKey)) return false;
    std::vector<unsigned char> vchPub = ParseHex(g_strCheckpointMasterPubKey);
    CPubKey pubkey(vchPub);
    if (!pubkey.IsFullyValid()) {
        LogPrintf("%s: checkpoint master pubkey not configured/invalid\n", __func__);
        return false;
    }
    std::vector<unsigned char> payload = cp.GetSignedPayload();
    uint256 h = Hash(payload.begin(), payload.end());
    return pubkey.Verify(h, cp.vchSig);
}

bool AcceptSignedCheckpoint(const CSignedCheckpoint &cp, std::string &strError) {
    if (!VerifySignedCheckpoint(cp)) {
        strError = "signed checkpoint signature invalid";
        return false;
    }
    LOCK(cs_synccheckpoint);
    if (!g_activeCheckpoint.IsNull() && cp.nHeight <= g_activeCheckpoint.nHeight) {
        strError = "signed checkpoint is not newer than the active one";
        return false;
    }
    g_activeCheckpoint = cp;
    LogPrintf("Opalyx: accepted signed checkpoint height=%d hash=%s\n",
              cp.nHeight, cp.hashBlock.ToString());
    return true;
}

// MVP injection mechanism: read -synccheckpoint=<height>:<blockhashhex>:<sighex>
// from the config/args exactly once, the first time a checkpoint is consulted.
// (Network auto-relay is a roadmap item; see TODO.md.)
static void LoadConfiguredCheckpointOnce() {
    std::call_once(g_loadOnce, []() {
        std::string s = gArgs.GetArg("-synccheckpoint", "");
        if (s.empty()) return;
        size_t a = s.find(':');
        size_t b = (a == std::string::npos) ? std::string::npos : s.find(':', a + 1);
        if (a == std::string::npos || b == std::string::npos) {
            LogPrintf("Opalyx: malformed -synccheckpoint (want height:hash:sig)\n");
            return;
        }
        CSignedCheckpoint cp;
        cp.nHeight = atoi(s.substr(0, a).c_str());
        cp.hashBlock = uint256S(s.substr(a + 1, b - a - 1));
        cp.vchSig = ParseHex(s.substr(b + 1));
        std::string err;
        if (!AcceptSignedCheckpoint(cp, err))
            LogPrintf("Opalyx: -synccheckpoint rejected: %s\n", err.c_str());
    });
}

CSignedCheckpoint GetActiveSyncCheckpoint() {
    LoadConfiguredCheckpointOnce();
    LOCK(cs_synccheckpoint);
    return g_activeCheckpoint;
}

bool CheckBlockAgainstSyncCheckpoint(int nHeight, const uint256 &hashBlock) {
    LoadConfiguredCheckpointOnce();
    LOCK(cs_synccheckpoint);
    if (g_activeCheckpoint.IsNull()) return true;
    if (nHeight == g_activeCheckpoint.nHeight)
        return hashBlock == g_activeCheckpoint.hashBlock;
    return true;
}
