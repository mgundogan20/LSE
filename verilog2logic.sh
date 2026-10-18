#!/usr/bin/env bash
# verilog2logic.sh - convert Verilog files into flat EQN, BLIF, PLA and AIGER files
# using Yosys and the ABC embedded in it.
#
# Flow per file:
#   yosys: read_verilog -> hierarchy -> proc -> flatten -> opt -> techmap -> write_blif
#   abc:   read_blif -> collapse|strash -> write_eqn, write_blif
#          -> collapse -> write_pla -> strash -> write_aiger
#
# Output (under OUT_ROOT):
#   example_eqns/NAME.eqn   example_blifs/NAME.blif
#   example_plas/NAME.pla   example_aigs/NAME.aig   (binary AIGER with symbol table)
#
# Usage:
#   ./verilog2logic.sh [-m] [-o OUT_ROOT] [INPUT ...]
#     INPUT     .v files or directories containing .v files (default: example_verilogs)
#     -o DIR    root directory for the output folders (default: this script's directory)
#     -m        keep multi-level logic (AIG via strash) in the EQN/BLIF outputs instead of
#               collapsing each output into a function of the primary inputs.
#               PLA is always two-level and AIG is always an AIG.
#
# Needs `yosys` or `yowasp-yosys` (pip install --user yowasp-yosys) on PATH.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_ROOT="$SCRIPT_DIR"
ABC_OPT="collapse"

while getopts "o:mh" opt; do
    case "$opt" in
        o) OUT_ROOT="$OPTARG" ;;
        m) ABC_OPT="strash" ;;
        h) sed -n '2,22p' "$0"; exit 0 ;;
        *) exit 2 ;;
    esac
done
shift $((OPTIND - 1))
[ $# -eq 0 ] && set -- "$SCRIPT_DIR/example_verilogs"

if command -v yosys >/dev/null; then
    YOSYS=yosys
elif command -v yowasp-yosys >/dev/null; then
    YOSYS=yowasp-yosys
else
    echo "error: yosys not found (try: pip install --user yowasp-yosys)" >&2
    exit 1
fi

# Collect .v files from arguments
files=()
for arg in "$@"; do
    if [ -d "$arg" ]; then
        for f in "$arg"/*.v; do [ -e "$f" ] && files+=("$f"); done
    elif [ -f "$arg" ]; then
        files+=("$arg")
    else
        echo "warning: skipping '$arg' (not found)" >&2
    fi
done
[ ${#files[@]} -eq 0 ] && { echo "error: no .v files found" >&2; exit 1; }

mkdir -p "$OUT_ROOT"
OUT_ROOT="$(cd "$OUT_ROOT" && pwd)"
mkdir -p "$OUT_ROOT"/{example_eqns,example_blifs,example_plas,example_aigs}

fail=0
for f in "${files[@]}"; do
    src="$(cd "$(dirname "$f")" && pwd)/$(basename "$f")"
    name="$(basename "$f" .v)"
    tmp=".$name.yosys.blif"
    outs=("example_eqns/$name.eqn" "example_blifs/$name.blif"
          "example_plas/$name.pla" "example_aigs/$name.aig")
    # ABC script args are comma-separated, so run from OUT_ROOT and use relative paths.
    # backup/restore hands yosys back its own netlist so the abc pass exits cleanly.
    abc_script="+backup;read_blif,$tmp;$ABC_OPT;write_eqn,${outs[0]};write_blif,${outs[1]}"
    abc_script+=";collapse;write_pla,${outs[2]};strash;write_aiger,-s,${outs[3]};restore"
    (cd "$OUT_ROOT" && rm -f "${outs[@]}")  # so stale files cannot mask a failure
    ok=1
    (cd "$OUT_ROOT" && "$YOSYS" -q -p "
            read_verilog \"$src\";
            hierarchy -auto-top; proc; flatten; opt; techmap; opt -purge;
            write_blif $tmp;
            abc -script $abc_script") || ok=0
    for o in "${outs[@]}"; do [ -s "$OUT_ROOT/$o" ] || ok=0; done
    if [ $ok -eq 1 ]; then
        echo "ok    $f -> {eqn,blif,pla,aig}"
    else
        echo "FAIL  $f" >&2
        fail=1
    fi
    rm -f "$OUT_ROOT/$tmp"
done
exit $fail
