#!/usr/bin/env python3
"""netlist2json.py - convert structural (gate-level) Verilog into a JSON gate graph.

Nodes are logic gates plus one node per primary input/output bit and per constant;
edges are interconnects (one edge per driver -> sink pin, labelled with the net).

Supported Verilog subset (one module per file):
  * ANSI or non-ANSI port lists, `wire` declarations, vectors and bit-selects (x[3])
  * gate primitives: and, or, nand, nor, xor, xnor (n inputs), not, buf
    (instance names optional; unnamed gates get ids like `xor_1`)
  * `assign a = b;` where b is a single net/bit or a constant (becomes a BUF node)
  * constants 1'b0 / 1'b1 / 0 / 1

Output JSON:
  {
    "module": str, "source": str,
    "inputs": [bit, ...], "outputs": [bit, ...],
    "nodes": [{"id", "type", "inputs": [net, ...], "outputs": [net, ...]}, ...],
    "edges": [{"from": node_id, "to": node_id, "net": net, "pin": int}, ...],
    "warnings": [str, ...]
  }
INPUT nodes have only "outputs", OUTPUT nodes only "inputs". "pin" is the index of
the net in the sink node's "inputs" list.

Usage:
  ./netlist2json.py [-o OUT_DIR] [INPUT ...]
    INPUT    .v files or directories of .v files (default: netlists/)
    -o DIR   output directory (default: netlist_jsons/)
"""

import argparse
import json
import re
import sys
from pathlib import Path

GATES = {"and", "or", "nand", "nor", "xor", "xnor", "not", "buf"}
DIRECTIONS = {"input", "output", "inout"}
NET_TYPES = {"wire", "tri", "wand", "wor", "supply0", "supply1"}
CONSTS = {"1'b0": "CONST0", "1'b1": "CONST1", "0": "CONST0", "1": "CONST1"}

IDENT = r"[A-Za-z_\\][\w$]*"
RANGE_RE = re.compile(r"\[\s*(\d+)\s*:\s*(\d+)\s*\]")
TERM_RE = re.compile(rf"^({IDENT})\s*(?:\[\s*(\d+)\s*\])?$")


class NetlistError(Exception):
    pass


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", " ", text)


def bit_names(name, rng):
    """Expand a declaration into bit names: x[9:0] -> x[9] .. x[0]; scalar -> x."""
    if rng is None:
        return [name]
    msb, lsb = rng
    step = -1 if msb >= lsb else 1
    return [f"{name}[{i}]" for i in range(msb, lsb + step, step)]


class Module:
    def __init__(self, name):
        self.name = name
        self.ports = []        # port names in header order
        self.direction = {}    # name -> input/output
        self.width = {}        # name -> (msb, lsb) or None
        self.gates = []        # (id, type, [output nets], [input nets])

    def declare(self, kind, rest):
        """Handle `input wire [3:0] a, b` / `wire w1, w2` (rest = text after keyword)."""
        rng = None
        tokens = rest.strip()
        while True:
            m = re.match(r"(wire|reg|logic|signed)\b\s*", tokens)
            if not m:
                break
            if m.group(1) in ("reg", "logic"):
                raise NetlistError(f"'{m.group(1)}' is not structural; use wire")
            tokens = tokens[m.end():]
        m = RANGE_RE.match(tokens)
        if m:
            rng = (int(m.group(1)), int(m.group(2)))
            tokens = tokens[m.end():]
        for name in (n.strip() for n in tokens.split(",")):
            if not name:
                continue
            if not re.fullmatch(IDENT, name):
                raise NetlistError(f"cannot parse declaration '{kind} {rest.strip()}'")
            if kind in DIRECTIONS:
                if kind == "inout":
                    raise NetlistError(f"inout port '{name}' is not supported")
                self.direction[name] = kind
            if rng is not None or name not in self.width:
                self.width[name] = rng

    def resolve(self, term):
        """Turn a terminal expression into a single-bit net name (or a constant)."""
        term = term.strip()
        if term in CONSTS:
            return term
        m = TERM_RE.match(term)
        if not m:
            raise NetlistError(f"unsupported terminal '{term}' (only nets, bit-selects, constants)")
        name, idx = m.group(1), m.group(2)
        if name not in self.width:
            raise NetlistError(f"net '{name}' is not declared")
        rng = self.width[name]
        if idx is None:
            if rng is not None and rng[0] != rng[1]:
                raise NetlistError(f"vector '{name}' used as a gate terminal; select one bit")
            return name if rng is None else f"{name}[{rng[0]}]"
        if rng is None:
            raise NetlistError(f"bit-select on scalar net '{name}'")
        i = int(idx)
        if not min(rng) <= i <= max(rng):
            raise NetlistError(f"index {i} out of range for '{name}'")
        return f"{name}[{i}]"

    def bits(self, direction):
        return [b for p in self.ports if self.direction.get(p) == direction
                for b in bit_names(p, self.width.get(p))]


def parse(text):
    text = strip_comments(text)
    modules = re.findall(r"\bmodule\b(.*?)\bendmodule\b", text, flags=re.S)
    if len(modules) != 1:
        raise NetlistError(f"expected exactly one module, found {len(modules)}")
    body = modules[0]

    header = re.match(rf"\s*({IDENT})\s*(?:#\s*\(.*?\)\s*)?\((.*?)\)\s*;", body, flags=re.S)
    if not header:
        raise NetlistError("cannot parse module header")
    mod = Module(header.group(1))

    # Port list: either plain names (non-ANSI) or full ANSI declarations
    kind = None
    for item in (p.strip() for p in header.group(2).split(",")):
        if not item:
            continue
        first = item.split()[0]
        if first in DIRECTIONS:
            kind, item = first, item[len(first):]
        if kind is None:          # non-ANSI: just a name
            mod.ports.append(item)
            continue
        mod.declare(kind, item)   # ANSI: direction carries over to following names
        mod.ports.append(item.split()[-1].split("]")[-1].strip())

    counters = {}
    for stmt in (s.strip() for s in body[header.end():].split(";")):
        if not stmt:
            continue
        keyword = stmt.split()[0].split("(")[0]
        if keyword in DIRECTIONS or keyword in NET_TYPES:
            mod.declare(keyword, stmt[len(keyword):])
        elif keyword == "assign":
            lhs, _, rhs = stmt[len("assign"):].partition("=")
            out, src = mod.resolve(lhs), mod.resolve(rhs)
            if out in CONSTS:
                raise NetlistError(f"cannot assign to constant in '{stmt}'")
            counters["assign"] = counters.get("assign", 0) + 1
            mod.gates.append((f"assign_{counters['assign']}", "BUF", [out], [src]))
        elif keyword in GATES:
            m = re.fullmatch(rf"{keyword}\s*(?:#\s*\S+\s*)?({IDENT})?\s*(?:\[[^\]]*\]\s*)?\((.*)\)",
                             stmt, flags=re.S)
            if not m:
                raise NetlistError(f"cannot parse gate '{stmt}'")
            terms = [mod.resolve(t) for t in m.group(2).split(",")]
            if len(terms) < 2:
                raise NetlistError(f"gate needs at least 2 terminals: '{stmt}'")
            if keyword in ("not", "buf"):     # outputs..., input
                outs, ins = terms[:-1], terms[-1:]
            else:                             # output, inputs...
                outs, ins = terms[:1], terms[1:]
            if any(o in CONSTS for o in outs):
                raise NetlistError(f"gate drives a constant: '{stmt}'")
            gid = m.group(1)
            if gid is None:
                counters[keyword] = counters.get(keyword, 0) + 1
                gid = f"{keyword}_{counters[keyword]}"
            mod.gates.append((gid, keyword.upper(), outs, ins))
        else:
            raise NetlistError(f"unsupported statement '{stmt.splitlines()[0]}' "
                               "(only declarations, gate primitives and simple assigns)")

    missing = [p for p in mod.ports if p not in mod.direction]
    if missing:
        raise NetlistError(f"ports without direction: {', '.join(missing)}")
    ids = [g[0] for g in mod.gates]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise NetlistError(f"duplicate instance names: {', '.join(dupes)}")
    return mod


def build_graph(mod, source):
    inputs, outputs = mod.bits("input"), mod.bits("output")
    nodes, warnings = [], []
    drivers, sinks = {}, {}   # net -> [node ids], net -> [(node id, pin)]

    taken = {g[0] for g in mod.gates}
    def port_id(prefix, bit):
        nid = bit
        while nid in taken:
            nid = f"{prefix}:{nid}"
        taken.add(nid)
        return nid

    for b in inputs:
        nid = port_id("in", b)
        nodes.append({"id": nid, "type": "INPUT", "outputs": [b]})
        drivers.setdefault(b, []).append(nid)

    for gid, gtype, outs, ins in mod.gates:
        nodes.append({"id": gid, "type": gtype, "inputs": ins, "outputs": outs})
        for o in outs:
            drivers.setdefault(o, []).append(gid)
        for pin, i in enumerate(ins):
            sinks.setdefault(i, []).append((gid, pin))

    for b in outputs:
        nid = port_id("out", b)
        nodes.append({"id": nid, "type": "OUTPUT", "inputs": [b]})
        sinks.setdefault(b, []).append((nid, 0))

    for c in sorted(set(sinks) & set(CONSTS)):
        nid = port_id("const", CONSTS[c])
        nodes.append({"id": nid, "type": CONSTS[c], "outputs": [c]})
        drivers[c] = [nid]

    edges = [{"from": d, "to": s, "net": net, "pin": pin}
             for net, sink_list in sinks.items()
             for s, pin in sink_list
             for d in drivers.get(net, [])]

    for net, ds in drivers.items():
        if len(ds) > 1:
            warnings.append(f"net '{net}' has multiple drivers: {', '.join(ds)}")
        if net not in sinks:
            warnings.append(f"net '{net}' (driven by {', '.join(ds)}) drives nothing")
    for net, ss in sinks.items():
        if net not in drivers:
            warnings.append(f"net '{net}' is undriven but used by "
                            f"{', '.join(s for s, _ in ss)}")
    for name, rng in mod.width.items():
        if name not in mod.direction:
            for b in bit_names(name, rng):
                if b not in drivers and b not in sinks:
                    warnings.append(f"wire '{b}' is declared but unused")
    if has_cycle(mod.gates, drivers):
        warnings.append("combinational loop detected")

    return {"module": mod.name, "source": source, "inputs": inputs, "outputs": outputs,
            "nodes": nodes, "edges": edges, "warnings": warnings}


def has_cycle(gates, drivers):
    fanin = {gid: {d for i in ins for d in drivers.get(i, [])} for gid, _, _, ins in gates}
    state = {}
    def visit(n):
        state[n] = 1
        for p in fanin.get(n, ()):
            if state.get(p) == 1 or (p not in state and visit(p)):
                return True
        state[n] = 2
        return False
    return any(g not in state and visit(g) for g in fanin)


def main():
    root = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("inputs", nargs="*", default=[str(root / "netlists")])
    ap.add_argument("-o", "--out-dir", default=str(root / "netlist_jsons"))
    args = ap.parse_args()

    files = []
    for arg in map(Path, args.inputs):
        if arg.is_dir():
            files += sorted(arg.glob("*.v"))
        elif arg.is_file():
            files.append(arg)
        else:
            print(f"warning: skipping '{arg}' (not found)", file=sys.stderr)
    if not files:
        sys.exit("error: no .v files found")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fail = False
    for f in files:
        try:
            graph = build_graph(parse(f.read_text()), f.name)
        except NetlistError as e:
            print(f"FAIL  {f}: {e}", file=sys.stderr)
            fail = True
            continue
        out = out_dir / f"{f.stem}.json"
        out.write_text(json.dumps(graph, indent=2) + "\n")
        gates = sum(n["type"] not in ("INPUT", "OUTPUT", "CONST0", "CONST1") for n in graph["nodes"])
        print(f"ok    {f} -> {out}  ({gates} gates, {len(graph['edges'])} edges)")
        for w in graph["warnings"]:
            print(f"      warning: {w}")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
