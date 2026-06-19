// Copyright (c) 2020 The Bitcoin developers
// Copyright (c) 2024-2025 The Opalyx Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.
//
// aserti3-2d (ASERT) difficulty adjustment for Opalyx (OPX).
// This is the well-tested integer reference implementation of ASERT
// (Absolutely Scheduled Exponentially Rising Targets), adapted for a
// fresh chain whose difficulty anchor is the genesis block.
//
// On top of pure ASERT, Opalyx layers two operator-requested safeguards:
//   * a per-step CLAMP that bounds how far a single retarget may move
//     relative to the previous block's target (anti "wild swing"); and
//   * an EMERGENCY recovery rule that lifts the clamp's "make easier"
//     bound once the chain has fallen far behind schedule, so the chain
//     can recover quickly after a 90-99% hashrate drop.
//
// See src/pow.cpp for how this is wired into GetNextWorkRequired().

#ifndef OPALYX_POW_ASERTI32D_H
#define OPALYX_POW_ASERTI32D_H

#include "arith_uint256.h"
#include "consensus/params.h"

#include <cstdint>

class CBlockIndex;
class CBlockHeader;

/**
 * Pure ASERT target calculation (aserti3-2d), integer math, no clamp.
 *
 * next_target = ref_target * 2^((time_diff - spacing*(height_diff+1)) / halflife)
 *
 * @param refTarget   Target of the anchor block (decoded from its nBits).
 * @param nSpacing    Ideal block spacing in seconds (params.nPowTargetSpacing).
 * @param nTimeDiff   (block-1).time - anchor.parent.time  (see GetNextWorkRequiredASERT).
 * @param nHeightDiff (block-1).height - anchor.height.
 * @param powLimit    Maximum (easiest) target; MUST have >=32 leading zero bits.
 * @param nHalfLife   ASERT half-life in seconds (params.nASERTHalfLife).
 */
arith_uint256 CalculateASERT(const arith_uint256 &refTarget,
                             const int64_t nSpacing,
                             const int64_t nTimeDiff,
                             const int64_t nHeightDiff,
                             const arith_uint256 &powLimit,
                             const int64_t nHalfLife) noexcept;

/**
 * Compute nBits for the block that will follow pindexPrev, using ASERT
 * anchored at the genesis block, with Opalyx clamp + emergency recovery.
 */
unsigned int GetNextWorkRequiredASERT(const CBlockIndex *pindexPrev,
                                      const CBlockHeader *pblock,
                                      const Consensus::Params &params);

#endif // OPALYX_POW_ASERTI32D_H
