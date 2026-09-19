#!/bin/bash
# Build the accessibility bridge. Prints the binary path; skips the compile when
# the source has not changed. No dependencies beyond the Swift toolchain.
#
# Paths differ from upstream because the bridge is vendored rather than being
# the project's own package.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="$root/axbridge.swift"
out="$root/build/axbridge"
mkdir -p "$(dirname "$out")"
if [[ ! -x "$out" || "$src" -nt "$out" ]]; then
  swiftc -O -o "$out" "$src" >&2
fi
echo "$out"
