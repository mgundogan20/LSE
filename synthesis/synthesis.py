## Usage python synthesis.py ../example_blifs/mll.blif


import sys
from itertools import product


def replace_char_with_binary(string_list, target_char,output_list):
  result_list = []
  outlist = []
  for enum,s in enumerate(string_list):
    count = s.count(target_char)

    if count == 0:
      result_list.append(s)
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
        outlist.append(output_list[enum])

  return result_list,outlist
if len(sys.argv) < 1:
    print("Usage: python synthesis.py <input_file_path>")
    sys.exit(1)

file_path = sys.argv[1]

def file_search(file_path, target_word):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            line_table = []
            for line_num, line in enumerate(file, start=1):
                if line.startswith(tuple(target_word)):
                    line_table.append(line.strip())
            return line_table
    except FileNotFoundError:
        print(f"Error: The file at '{file_path}' was not found.")


inputs = file_search(file_path, [".i"])[0].split()[1:]
outputs = file_search(file_path, [".o"])[0].split()[1:]
table = file_search(file_path, ["1","0","-"])

i_table, o_table = [i.split()[0] for i in table],[i.split()[1] for i in table]

i_table, o_table = replace_char_with_binary(i_table, "-",o_table)

onset_minterms = sum(s.count("1") for s in o_table)
print("# of Onset Minterms: ")
print(sum(s.count("1") for s in o_table))
print("# of Onset Maxterms: ")
total_possible_outputs = len(o_table[0])*(2**len(i_table[0]))
print(total_possible_outputs-onset_minterms)



print("Canonical SOP: ")
for i in range(len(o_table[0])):
    for line in range(len(i_table)):
        for var in range(len(i_table[0])):
            if(i_table[line][var]=="1"):
                print(inputs[var],end="")
            else:
                print(inputs[var]+"'",end="")
        if(line !=len(i_table)-1): 
            print("+",end="")
    print()
print()




print("Canonical POS: ")
printed = False
for bits in product('01', repeat=len(inputs)):
    test_string = "".join(bits)
    if(test_string not in i_table):
        print("(",end="")
        for var,char in enumerate(test_string):
            printed = True
            if(test_string[var]=="0"):
                print(inputs[var],end="")
            else:
                print(inputs[var]+"'",end="")
            if(var != len(test_string)-1):
                print("+",end="")
            else:
                print(")",end="")
print()


print()
print("Inverse Canonical SOP: ")


for i in range(len(o_table[0])):
    for line in range(len(i_table)):
        for var in range(len(i_table[0])):
            if(i_table[line][var]=="0"):
                print(inputs[var],end="")
            else:
                print(inputs[var]+"'",end="")
        if(line !=len(i_table)-1): 
            print("+",end="")
    print()
print()
print("Inverse Canonical POS: ")
printed = False
for bits in product('01', repeat=len(inputs)):
    test_string = "".join(bits)
    if(test_string not in i_table):
        print("(",end="")
        for var,char in enumerate(test_string):
            printed = True
            if(test_string[var]=="1"):
                print(inputs[var],end="")
            else:
                print(inputs[var]+"'",end="")
            if(var != len(test_string)-1):
                print("+",end="")
            else:
                print(")",end="")
print()

