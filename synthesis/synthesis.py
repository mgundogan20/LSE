## Usage python synthesis.py ../example_blifs/mll.blif


import sys
from itertools import product, combinations


def replace_char_with_binary(string_list, target_char,output_list):
  result_list = []
  outlist = []
  for enum,s in enumerate(string_list):
    count = s.count(target_char)

    if count == 0:
      result_list.append(s)
      if(output_list != None):
            outlist.append(output_list[enum])
      continue

    binary_combinations = product(['0', '1'], repeat=count)

    string_variants = []
    for combo in binary_combinations:
      temp = s
      for bit in combo:
        temp = temp.replace(target_char, bit, 1)
      string_variants.append(temp)
    for i in string_variants:
        result_list.append(i)
        if(output_list != None):
            outlist.append(output_list[enum])
  
  if(output_list != None):
        return result_list,outlist
  else:
        return result_list
if len(sys.argv) < 2:                                   # FIX: was < 1
    sys.exit("Usage: python synthesis.py <input_file_path>")

file_path = sys.argv[1]
def file_search(file_path):
    line_table, buf = [], ""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.split("#", 1)[0].rstrip()
                if line.endswith("\\"):
                    buf += line[:-1] + " "
                    continue
                line = (buf + line).strip()
                buf = ""
                if line:
                    line_table.append(line)
    except FileNotFoundError:
        sys.exit(f"Error: The file at '{file_path}' was not found.")
    if buf.strip():
        line_table.append(buf.strip())
    return line_table


module_name, inputs, outputs, blocks = "top", [], [], []
for line in file_search(file_path):
    tok = line.split()
    if tok[0] == ".model":
        module_name = tok[1] if len(tok) > 1 else module_name
    elif tok[0] == ".inputs":
        inputs += tok[1:]
    elif tok[0] == ".outputs":
        outputs += tok[1:]
    elif tok[0] == ".names":
        blocks.append((tok[1:], []))
    elif tok[0].startswith("."):
        continue
    elif blocks:
        blocks[-1][1].append(tok)

defs = {}
for signals, table in blocks:
    k = 1
    if table:
        k = len(table[0][1]) if len(table[0]) > 1 else len(table[0][0])
    block_ins, block_outs = signals[:-k], signals[-k:]
    for j, o in enumerate(block_outs):
        defs[o] = (block_ins, block_outs, table, j)


def get_onset(block_ins, block_outs, table, j):
    out = block_outs[j]
    missing = [s for s in block_ins if s not in inputs]
    if missing:
        sys.exit(f"Output '{out}' depends on internal signal(s) {missing}; "
                 "only .names blocks over primary inputs are supported.")
    cols = [inputs.index(s) for s in block_ins]
    i_table, all_rows, out_vals = [], [], set()
    for row in table:
        pattern, val = ("", row[0]) if not block_ins else (row[0], row[1])
        if len(val) != len(block_outs):
            sys.exit(f"Row '{' '.join(row)}' has {len(val)} output bits, expected {len(block_outs)}.")
        out_vals.add(val[j])
        full = ["-"] * len(inputs)
        for c, ch in zip(cols, pattern):
            full[c] = ch
        all_rows.append("".join(full))
        if val[j] == "1":
            i_table.append("".join(full))
    if len(block_outs) == 1 and out_vals == {"0"}:
        return all_minterms - set(replace_char_with_binary(all_rows, "-", None))
    return set(replace_char_with_binary(i_table, "-", None))


def sort_binary_strings(strings):
    return sorted(
        strings, 
        key=lambda s: (
            int(s.replace('-', '0'), 2), 
            s.replace('-', 'a').replace('0', 'b'),
        ),
        reverse = False
    )

def term_str(pi):
    s = ""
    for var in range(len(pi)):
        if(pi[var]=="1"):
            s += inputs[var]
        elif(pi[var]!="-"):
            s += inputs[var]+"'"
    return s or "1"

def clause_str(pi):
    lits = []
    for var in range(len(pi)):
        if(pi[var]=="0"):
            lits.append(inputs[var])
        elif(pi[var]!="-"):
            lits.append(inputs[var]+"'")
    return "(" + " + ".join(lits) + ")" if lits else "0"


def covers(pi, minterm):
    return all(c == "-" or c == m for c, m in zip(pi, minterm))
def prime_implicants(minterms):
    simplification_table = set(minterms)
    pi_list = set()
    while simplification_table:
        grouped_i_table = {}
        for t in simplification_table:
            grouped_i_table.setdefault(t.count("1"), []).append(t)
        used, new_simplification_table = set(), set()
        for key, group in grouped_i_table.items():
            for term in group:
                for j in grouped_i_table.get(key + 1, []):
                    diff = 0
                    bit_index = 0
                    for bit in range(len(j)):
                        if(term[bit] != j[bit]):
                            if(term[bit] == "-" or j[bit] == "-"):
                                diff = 99
                            diff = diff+1
                            bit_index = bit
                    if(diff == 1):
                        new_simplification_table.add(term[:bit_index] + "-" + term[bit_index+1:])
                        used.update((term, j))
        pi_list |= simplification_table - used
        simplification_table = new_simplification_table
    return sort_binary_strings(pi_list)
def choose_cover(pi_list, minterms):
    total_minterm_list = sort_binary_strings(minterms)
    final_table = [[1 if covers(pi, m) else 0 for m in total_minterm_list] for pi in pi_list]
    epi_list = []
    for col, minterm in enumerate(total_minterm_list):
        rows = [row for row in range(len(pi_list)) if final_table[row][col] == 1]
        if(len(rows) == 1 and pi_list[rows[0]] not in epi_list):
            epi_list.append(pi_list[rows[0]])

    remaining = {m for m in minterms if not any(covers(p, m) for p in epi_list)}
    candidates = [p for p in pi_list
                  if p not in epi_list and any(covers(p, m) for m in remaining)]
    lit = lambda p: sum(c != "-" for c in p)
    added_list = []
    if remaining:
        if len(candidates) <= 16:
            best = None
            for k in range(1, len(candidates) + 1):
                for combo in combinations(candidates, k):
                    if all(any(covers(p, m) for p in combo) for m in remaining):
                        cost = sum(lit(p) for p in combo)
                        if best is None or cost < best[0]:
                            best = (cost, list(combo))
                if best:
                    break
            added_list = best[1]
        else:
            left = set(remaining)
            while left:
                p = max(candidates, key=lambda p: (sum(covers(p, m) for m in left), -lit(p)))
                added_list.append(p)
                left = {m for m in left if not covers(p, m)}
    return epi_list + added_list, epi_list


all_minterms = {"".join(b) for b in product("01", repeat=len(inputs))}
minimized = {}
onsets = {}
for out in outputs:
    if out not in defs:
        sys.exit(f"No .names block found for output '{out}'.")
    onset = get_onset(*defs[out])
    global_onset = onset
    offset = all_minterms - onset

    print(f" Output: {out}")
    print("# of Onset Minterms:", len(onset))
    print("Minterms:  m(" + ", ".join(str(int(t, 2)) for t in sort_binary_strings(onset)) + ")")
    print("# of Maxterms (off-set):", len(offset))
    print("Maxterms:  M(" + ", ".join(str(int(t, 2)) for t in sort_binary_strings(offset)) + ")")

    print("Canonical SOP:")
    print(" + ".join(term_str(t) for t in sort_binary_strings(onset)) if sort_binary_strings(onset)  else "0")
    print("Canonical POS:")
    print("".join(clause_str(t) for t in sort_binary_strings(offset)) if sort_binary_strings(offset) else "1")
    print("Inverse Canonical SOP:")
    print("".join(clause_str(t) for t in sort_binary_strings(offset)) if sort_binary_strings(offset) else "1")
    print("Inverse Canonical POS:")
    print(" + ".join(term_str(t) for t in sort_binary_strings(onset)) if sort_binary_strings(onset)  else "0")

    pi_list = prime_implicants(onset)
    added_list, epi_list = choose_cover(pi_list, onset)
    print("Prime implicants:")
    print(", ".join(term_str(p) for p in pi_list))
    print("EPI LIST:")
    print(", ".join(term_str(p) for p in epi_list))
    print("Minimized SOP:")
    print(" + ".join(term_str(t) for t in sort_binary_strings(added_list)) if sort_binary_strings(added_list)  else "0")

    inv_pi_list = prime_implicants(offset)
    pos_cover, inv_epi_list = choose_cover(inv_pi_list, offset)
    print("Prime implicates (as clauses):")
    print(", ".join(clause_str(p) for p in inv_pi_list))
    print("Essential prime implicates:")
    print(", ".join(clause_str(p) for p in inv_epi_list))
    print("Minimized POS:")
    print("".join(clause_str(t) for t in pos_cover) if pos_cover else "1")
    print()

    minimized[out] = added_list
    onsets[out] = onset


wires, gates, inverted, term_wire = [], [], {}, {}

def literal(name, bit):
    if bit == "1":
        return name
    if name not in inverted:
        inverted[name] = f"{name}_n"
        wires.append(inverted[name])
        gates.append(f"    not g_not_{name} ({inverted[name]}, {name});")
    return inverted[name]

def product_wire(pi):
    if pi in term_wire:
        return term_wire[pi]
    lits = [literal(inputs[var], pi[var]) for var in range(min(len(pi), len(inputs))) if pi[var] != "-"]
    if not lits:
        w = "1'b1"
    elif len(lits) == 1:
        w = lits[0]
    else:
        k = sum(1 for g in gates if g.lstrip().startswith("and "))
        w = f"pt_{k}"
        wires.append(w)
        gates.append(f"    and g_and_{k} ({w}, {', '.join(lits)});")
    term_wire[pi] = w
    return w

for o in outputs:
    ins = [product_wire(pi) for pi in minimized[o]] or ["1'b0"]
    if len(ins) == 1:
        gates.append(f"    buf g_buf_{o} ({o}, {ins[0]});")
    else:
        gates.append(f"    or g_or_{o} ({o}, {', '.join(ins)});")

with open(module_name+".v", "w") as f:
        ports = [f"    input {i}" for i in inputs] + [f"    output {o}" for o in outputs]
        module_init_txt = "`timescale 1ns / 1ps\n"
        module_init_txt += f"module {module_name} (\n" + ",\n".join(ports) + "\n);\n\n"
        if wires:
            module_init_txt += "    wire " + ", ".join(wires) + ";\n\n"
        module_init_txt += "\n".join(gates) + "\n\nendmodule\n"
        f.write(module_init_txt)
print(f"Wrote structural netlist to {module_name}.v")


# Here we read the constraints file template
with open("nexys.xdc") as f:
    lines = f.readlines()
# We edit the IOs we need
for k in range(0,len(inputs)):
    lines[k] = lines[k][1:]
    lines[k] = lines[k].replace(f"SW[{k}]", f"{inputs[k]}")
    
for k in range(16,16+len(outputs)):
    lines[k] = lines[k][1:]
    lines[k] = lines[k].replace(f"LED[{k-16}]", f"{outputs[k-16]}")
# We write back
with open("constraints.xdc", "w") as f:
    f.writelines(lines)
print("Successfuly generated constraints file at constraints.xdc")

with open(module_name+"_truth_table.txt", "w") as f:
    f.write(" ".join(inputs) + " | " + " ".join(outputs) + "\n")
    for bits in sort_binary_strings(all_minterms):
        f.write(" ".join(bits) + " | " + " ".join("1" if bits in onsets[o] else "0" for o in outputs) + "\n")
print(f"Wrote truth table to {module_name}_truth_table.txt")
