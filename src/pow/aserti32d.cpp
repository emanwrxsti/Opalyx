// Copyright (c) 2020 The Bitcoin developers
// Copyright (c) 2024-2025 The Opalyx Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include "pow/aserti32d.h"

#include "chain.h"
#include "primitives/block.h"
#include "uint256.h"

#include <cassert>

arith_uint256 CalculateASERT(const arith_uint256 &refTarget,
                             const int64_t nSpacing,
                             const int64_t nTimeDiff,
                             const int64_t nHeightDiff,
                             const arith_uint256 &powLimit,
                             const int64_t nHalfLife) noexcept {
    // Input target must never be zero nor exceed powLimit.
    assert(refTarget > arith_uint256(0) && refTarget <= powLimit);
    // We need at least 32 leading zero bits in powLimit so that the
    // fixed-point multiply below cannot overflow a 256-bit integer.
    assert((powLimit >> 224) == arith_uint256(0));
    // Height diff must not be negative.
    assert(nHeightDiff >= 0);
    assert(nSpacing > 0);
    assert(nHalfLife > 0);

    // Fixed-point (16 fractional bits) exponent:
    //   ((t - s*(h+1)) / halflife)
    int64_t exponent =
        ((nTimeDiff - nSpacing * (nHeightDiff + 1)) * 65536) / nHalfLife;

    // Split into integer (shifts) and fractional (exponent) parts.
    // Arithmetic right shift rounds toward negative infinity, which is what
    // we want for the integer part.
    int64_t shifts = exponent >> 16;
    exponent -= shifts * 65536;
    assert(exponent >= 0 && exponent < 65536);

    // 2^fractional, approximated with a cubic polynomial (error < 0.013%):
    //   2^x ~= 1 + 0.695502049*x + 0.2262698*x^2 + 0.0782318*x^3
    // evaluated in fixed point. Result "factor" is 2^16 * 2^fractional.
    uint64_t factor =
        65536 +
        ((+195766423245049ull * uint64_t(exponent) +
          971821376ull * uint64_t(exponent) * uint64_t(exponent) +
          5127ull * uint64_t(exponent) * uint64_t(exponent) * uint64_t(exponent) +
          (1ull << 47)) >>
         48);

    arith_uint256 nextTarget = refTarget;
    nextTarget *= factor;

    // Undo the fixed-point scaling and apply the integer power-of-two part.
    if (shifts < 0) {
        nextTarget >>= -shifts;
        nextTarget >>= 16;
    } else {
        // Detect potential overflow of the left shift. If it would overflow,
        // the result is far easier than powLimit anyway, so clamp to powLimit.
        arith_uint256 check = nextTarget;
        nextTarget <<= shifts;
        if ((nextTarget >> shifts) != check) {
            // overflow
            return powLimit;
        }
        nextTarget >>= 16;
    }

    if (nextTarget == arith_uint256(0)) {
        return arith_uint256(1);
    }
    if (nextTarget > powLimit) {
        return powLimit;
    }
    return nextTarget;
}

unsigned int GetNextWorkRequiredASERT(const CBlockIndex *pindexPrev,
                                      const CBlockHeader *pblock,
                                      const Consensus::Params &params) {
    assert(pindexPrev != nullptr);

    const arith_uint256 powLimit = UintToArith256(params.powLimit);
    const int64_t nSpacing = params.nPowTargetSpacing;
    const int64_t nHalfLife = params.nASERTHalfLife;

    // Regtest / no-retarget: keep last bits.
    if (params.fPowNoRetargeting) {
        return pindexPrev->nBits;
    }

    // -----------------------------------------------------------------
    // Optional testnet rule: allow a min-difficulty block after a long gap.
    // -----------------------------------------------------------------
    if (params.fPowAllowMinDifficultyBlocks) {
        if (pblock->GetBlockTime() >
            pindexPrev->GetBlockTime() + nSpacing * 2) {
            return powLimit.GetCompact();
        }
    }

    // -----------------------------------------------------------------
    // ASERT anchored at GENESIS (height 0).
    // We synthesise the genesis "parent time" as (genesisTime - spacing) so
    // that the standard aserti3-2d formula keeps difficulty constant when
    // blocks arrive exactly on schedule. (Verified numerically.)
    // -----------------------------------------------------------------
    const CBlockIndex *pindexAnchor = pindexPrev->GetAncestor(0); // genesis
    assert(pindexAnchor != nullptr);

    const arith_uint256 refTarget = arith_uint256().SetCompact(pindexAnchor->nBits);
    const int64_t refParentTime = int64_t(pindexAnchor->GetBlockTime()) - nSpacing;
    const int64_t refHeight = pindexAnchor->nHeight; // 0

    const int64_t nTimeDiff = int64_t(pindexPrev->GetBlockTime()) - refParentTime;
    const int64_t nHeightDiff = int64_t(pindexPrev->nHeight) - refHeight;

    arith_uint256 nextTarget =
        CalculateASERT(refTarget, nSpacing, nTimeDiff, nHeightDiff, powLimit, nHalfLife);

    // -----------------------------------------------------------------
    // CLAMP: bound the move relative to the previous block's target so a
    // single bad/forged timestamp cannot cause a wild swing. Default factor
    // is params.nDiffClampFactor (e.g. 4 => at most 4x easier / 4x harder).
    // -----------------------------------------------------------------
    const arith_uint256 prevTarget = arith_uint256().SetCompact(pindexPrev->nBits);
    const int64_t clamp = params.nDiffClampFactor > 1 ? params.nDiffClampFactor : 4;

    arith_uint256 maxTarget = prevTarget * uint64_t(clamp);     // easiest allowed this step
    arith_uint256 minTarget = prevTarget / uint64_t(clamp);     // hardest allowed this step
    if (minTarget == arith_uint256(0)) minTarget = arith_uint256(1);

    // -----------------------------------------------------------------
    // EMERGENCY recovery: if the chain has fallen far behind schedule
    // (no block for > nEmergencyGapSeconds), lift the clamp's upper bound so
    // ASERT is free to make the next block as easy as it needs to be. This is
    // what lets the chain recover quickly after a 90-99% hashrate drop.
    // -----------------------------------------------------------------
    const int64_t gap = int64_t(pblock->GetBlockTime()) - int64_t(pindexPrev->GetBlockTime());
    const bool fEmergency = params.nEmergencyGapSeconds > 0 &&
                            gap > params.nEmergencyGapSeconds;

    if (!fEmergency && nextTarget > maxTarget) {
        nextTarget = maxTarget; // normal: cannot get easier than clamp allows
    }
    if (nextTarget < minTarget) {
        nextTarget = minTarget; // never let one step get more than clamp x harder
    }

    if (nextTarget > powLimit) {
        nextTarget = powLimit;
    }
    if (nextTarget == arith_uint256(0)) {
        nextTarget = arith_uint256(1);
    }
    return nextTarget.GetCompact();
}
