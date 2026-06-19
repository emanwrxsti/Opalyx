#!/usr/bin/env bash
# Copyright (c) 2024-2025 The Opalyx Core developers
# Distributed under the MIT software license.
#
# rebrand.sh — rename Ravencoin branding to Opalyx / OPX across a cloned tree.
#
# Strategy:
#   * Token replacement is applied CONSISTENTLY to every text file (identifiers,
#     include guards, lib names, log strings, binary names) so the result still
#     compiles — the key is that e.g. RAVEN_POW_H -> OPALYX_POW_H happens
#     everywhere it appears, not just in some places.
#   * Existing "Copyright (c) ... developers" lines are PRESERVED VERBATIM
#     (MIT license requires retaining the original copyright notices). We do
#     not rewrite Bitcoin/Raven attribution; we only add Opalyx where new.
#   * Source FILES whose path contains raven/Raven are renamed (ravend.cpp ->
#     opalyxd.cpp, raven-cli.cpp -> opalyx-cli.cpp, ...).
#
# IMPORTANT: This rebrand has NOT been compile-verified in the build container
# (see TODO.md). After running it, ALWAYS run ./scripts/build-ubuntu.sh and fix
# any residual references it reports. Run this AFTER configure-opalyx.py.
#
# Usage: ./scripts/rebrand.sh /path/to/clone

set -euo pipefail

ROOT="${1:-.}"
cd "$ROOT"

if [ ! -f "src/chainparams.cpp" ]; then
  echo "ERROR: run from / pass the repo root (no src/chainparams.cpp found)." >&2
  exit 2
fi

echo ">> Opalyx rebrand starting in $(pwd)"

# Text file extensions we touch. We deliberately skip binaries, images, and
# the .git directory.
mapfile -t FILES < <(find . \
  -path ./.git -prune -o \
  -type f \( \
     -name '*.cpp' -o -name '*.h' -o -name '*.hpp' -o -name '*.c' -o \
     -name '*.cc' -o -name '*.am' -o -name '*.ac' -o -name '*.m4' -o \
     -name '*.include' -o -name '*.py' -o -name '*.sh' -o -name '*.md' -o \
     -name '*.conf' -o -name '*.json' -o -name '*.in' -o -name '*.ts' -o \
     -name '*.qrc' -o -name '*.plist' -o -name '*.txt' -o -name '*.yml' -o \
     -name '*.yaml' -o -name '*.cfg' -o -name '*.pro' \
  \) -print)

echo ">> Rewriting tokens in ${#FILES[@]} text files (preserving copyright lines)"

# Ordered, case-sensitive token map. Longer/more-specific first.
# The `unless /Copyright \(c\)/i` guard keeps existing attribution lines intact.
perl -i -pe '
  unless (/Copyright \(c\)/i) {
    s/Ravencoin/Opalyx/g;
    s/RavenCoin/Opalyx/g;
    s/ravencoin/opalyx/g;
    s/RAVENCOIN/OPALYX/g;
    s/Raven/Opalyx/g;
    s/RAVEN/OPALYX/g;
    s/raven/opalyx/g;
    s/\bRVN\b/OPX/g;
  }
' "${FILES[@]}"

echo ">> Renaming files whose path contains raven/Raven"
# Rename deepest paths first so parent renames do not invalidate child paths.
while IFS= read -r path; do
  newpath="$(echo "$path" | sed -e 's/Ravencoin/Opalyx/g' -e 's/ravencoin/opalyx/g' \
                                  -e 's/Raven/Opalyx/g' -e 's/raven/opalyx/g')"
  if [ "$path" != "$newpath" ]; then
    mkdir -p "$(dirname "$newpath")"
    if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      git mv -f "$path" "$newpath" 2>/dev/null || mv -f "$path" "$newpath"
    else
      mv -f "$path" "$newpath"
    fi
    echo "   $path -> $newpath"
  fi
done < <(find . -path ./.git -prune -o -depth -name '*raven*' -print; \
         find . -path ./.git -prune -o -depth -name '*Raven*' -print)

echo ">> Sanity scan for residual 'raven' references (excluding copyright lines):"
if grep -rIn --exclude-dir=.git -e 'raven' -e 'Raven' -e 'RVN' . \
     | grep -vi 'copyright (c)' | head -40; then
  echo "   ^ review the above; some may be legitimate (URLs in comments, etc.)."
else
  echo "   none found."
fi

echo ">> Rebrand done. Binaries will build as: opalyxd, opalyx-cli, opalyx-tx, opalyx-qt"
echo ">> NEXT: ./scripts/build-ubuntu.sh   (rebrand is NOT compile-verified; see TODO.md)"
