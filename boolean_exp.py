import re
from datetime import datetime
from pathlib import Path
import quine_mccluskey

class boolean_exp:
	# Expressions are nested tuples:
	#   ('VARIABLE', name) | ('CONSTANT', 0 or 1) | ('NOT', expression)
	#   ('AND', [expression, ...]) | ('OR', [expression, ...])

	TOKEN_PATTERN = re.compile(r"[()!*+]|[^\s()!*+;=]+")

	def __init__(self):
		self.inputs = []
		self.output = None
		self.expression = None
		self.minterms = []

	def parse_eqn(self, eqn_file):
		"""Load an ABC .eqn file into inputs/output/expression.

		Intermediate equations (e.g. `n6 = a * b;`) are substituted, so the stored
		expression only refers to primary inputs. For multi-output files, the first
		output in OUTORDER is used.
		"""
		with open(eqn_file) as file:
			text = re.sub(r"#[^\n]*", "", file.read())
			print(f"Parsing {eqn_file}:\n{text} \n---------------")

		# Step 1: split the file into statements of the form `name = right side;`
		equation_tokens = {}
		for statement in text.split(";"):
			if "=" not in statement:
				continue
			left_side, right_side = statement.split("=", 1)
			left_side = left_side.strip()
			if left_side == "INORDER":
				self.inputs = right_side.split()
			elif left_side == "OUTORDER":
				output_order = right_side.split()
				self.output = output_order[0]
			else:
				equation_tokens[left_side] = self.TOKEN_PATTERN.findall(right_side)

		# Step 2: substitute intermediate equations so only primary inputs remain
		expanded_tokens = self.substitute_equations(equation_tokens)

		self.expression = self.build_tree(expanded_tokens[self.output])
		print(f"Expanded expression for {self.output}:")
		print(self.expression_tree())


		
		return self.expression
	
	def expression_tree(self, node=None, prefix="", is_last=True, is_root=True):
			"""Written by Claude"""
			"""Return the expression tree with box-drawing lines connecting parent to child."""
			if node is None:
				node = self.expression

			kind = node[0]
			if kind in ("VARIABLE", "CONSTANT"):
				label = f"{kind}: {node[1]}"
			else:
				label = kind

			if is_root:
				line = label
				child_prefix = ""
			else:
				connector = "└── " if is_last else "├── "
				line = prefix + connector + label
				child_prefix = prefix + ("    " if is_last else "│   ")

			lines = [line]
			if kind not in ("VARIABLE", "CONSTANT"):
				children = [node[1]] if kind == "NOT" else node[1]
				for i, child in enumerate(children):
					lines.append(self.expression_tree(
						child, child_prefix, i == len(children) - 1, False
					))
			return "\n".join(lines)

	def substitute_equations(self, equation_tokens):
		"""
		Suggested by Claude to remove internal nodes.
		"""
		dependencies = {}
		for name, tokens in equation_tokens.items():
			dependencies[name] = {token for token in tokens if token in equation_tokens}

		# Order the equations so that each one comes after everything it uses
		order = []
		while len(order) < len(equation_tokens):
			for name in equation_tokens:
				if name not in order and dependencies[name].issubset(order):
					order.append(name)

		expanded_tokens = {}
		for name in order:
			result = []
			for token in equation_tokens[name]:
				if token in expanded_tokens:
					result.append("(")
					result.extend(expanded_tokens[token])
					result.append(")")
				else:
					result.append(token)
			expanded_tokens[name] = result
		return expanded_tokens

	def build_tree(self, tokens):
		"""Turn a token list into an expression tree with the shunting-yard algorithm.

		Operands wait on one stack and operators on another. An operator is applied
		once no operator that binds tighter (or a closing parenthesis) can still
		claim its operands.

		tokens: list of strings, e.g. ["(", "a", "*", "b", ")", "+", "c"]
		operators: 
			(, !, *, +, )
		operands:
			('VARIABLE', name)
			('CONSTANT', 0 or 1)
			('NOT', expression)
			('AND', [expression, ...])
			('OR', [expression, ...])
		"""
		operands = []
		operators = []

		for token in tokens:
			if token in ("(", "!"):
				operators.append(token)
			elif token == ")":
				# End of subexpression; pop operators until the matching "("
				while operators[-1] != "(":
					self.add_parsed_branch(operators.pop(), operands)
				operators.pop()  # discard the "("

			elif token in ("*", "+"):
				while (operators 
				       and operators[-1] != "("
					   and self.precedence(operators[-1]) >= self.precedence(token)):
					
					self.add_parsed_branch(operators.pop(), operands)
				operators.append(token)

			# Leaf nodes: variables and constants
			elif token in ("0", "1"):
				operands.append(('CONSTANT', int(token)))
			else:
				operands.append(('VARIABLE', token))

		while operators:
			self.add_parsed_branch(operators.pop(), operands)
		return operands[0]

	def precedence(self, operator):
		"""How tightly an operator binds: NOT before AND before OR."""
		if operator == "!":
			return 3
		elif operator == "*":
			return 2
		else:  # "+"
			return 1

	def add_parsed_branch(self, operator, operands):
		"""
		Generate the corresponding branch for the last operator and its operands.		
		"""
		if operator == "!":
			operands.append(('NOT', operands.pop()))
			return
		elif operator == "*":
			kind = 'AND'
		else:  # "+"
			kind = 'OR'

		right = operands.pop()
		left = operands.pop()
		children = []
		for child in (left, right):
			if child[0] == kind:
				children.extend(child[1])
			else:
				children.append(child)
		operands.append((kind, children))

	def evaluate(self, variable_values):
		"""Evaluate the expression tree with the given variable values.

		variable_values: dict mapping variable names to 0 or 1
		"""
		def eval_node(node):
			if node[0] == 'VARIABLE':
				return variable_values[node[1]]
			elif node[0] == 'CONSTANT':
				return node[1]
			elif node[0] == 'NOT':
				return 1 - eval_node(node[1])
			elif node[0] == 'AND':
				return int(all(eval_node(child) for child in node[1]))
			elif node[0] == 'OR':
				return int(any(eval_node(child) for child in node[1]))
			else:
				raise ValueError(f"Unknown node type: {node[0]}")

		return eval_node(self.expression)

	def get_onset_minterms(self, method='brute_force'):
		if method == 'brute_force':
			return self.onset_minterms_brute_force()
		else:
			raise ValueError(f"Unknown method: {method}")

	def onset_minterms_brute_force(self):
		self.minterms = []

		num_all_minterms = 2 ** len(self.inputs)

		
		for index, row in enumerate(range(num_all_minterms)):
			# Convert index to binary representation for variable values
			index_binary = format(index, f'0{len(self.inputs)}b')
			variable_value_dict = {}

			for position, name in enumerate(self.inputs):
				variable_value_dict[name] = int(index_binary[position])

			if self.evaluate(variable_value_dict) == 1:
				self.minterms.append(index)

		print(f"Onset minterms: {self.minterms}")
		return self.minterms

	def get_canonical_SOP(self):
		if not self.minterms:
			self.get_onset_minterms()
		return self.minterms

	def get_canonical_POS(self):
		max_minterm = 2 ** len(self.inputs) - 1
		if not self.minterms:
			self.get_onset_minterms()
		return [i for i in range(max_minterm + 1) if i not in self.minterms]

	def get_inverse_SOP(self):
		if not self.minterms:
			self.get_onset_minterms()
		return self.get_canonical_POS()

	def get_inverse_POS(self):
		if not self.minterms:
			self.get_onset_minterms()
		return self.get_canonical_SOP()

	def write_eqn_from_SOP_cubes(self, cubes, path):
		out_exp = []
		for cube in cubes:
			cube_exp = []
			for bit, variable in zip(cube, self.inputs):
				if bit == '1':
					cube_exp.append(variable)
				elif bit == "0":
					cube_exp.append("!" + variable)
			cube_exp = "(" + " * ".join(cube_exp) + ")"
			out_exp.append(cube_exp)
		
		out_exp = self.output + " = " + " + ".join(out_exp)
		filename = Path(path).stem
		header = (
			f'# Equation for "{filename}" written by us\n'
		)
		content = (
			header
			+ "INORDER = " + " ".join(self.inputs) + ";\n"
			+ "OUTORDER = " + self.output + ";\n"
			+ out_exp + ";\n"
		)
		with open(path, "w") as file:
			file.write(content)
		return content



if __name__ == "__main__":
	boolean_expression = boolean_exp()
	boolean_expression.parse_eqn('./example_eqns/no_epis.eqn')

	print(f"Inputs: {boolean_expression.inputs}")
	print(f"Output: {boolean_expression.output}")

	print(f"Expression: {boolean_expression.expression}")
	print(f"Onset minterms: {boolean_expression.get_onset_minterms()}")

	print(f"Canonical SOP: {boolean_expression.get_canonical_SOP()}")
	print(f"Canonical POS: {boolean_expression.get_canonical_POS()}")

	print(f"SOP of inverse: {boolean_expression.get_inverse_SOP()}")
	print(f"POS of inverse: {boolean_expression.get_inverse_POS()}")

	QMC = quine_mccluskey.QMC()
	minimized_SOP = QMC.find_minimal_expression(boolean_expression.get_canonical_SOP(), boolean_expression.inputs)

	boolean_expression.write_eqn_from_SOP_cubes(minimized_SOP, './result.eqn')

	minimized = boolean_exp()
	minimized.parse_eqn('./result.eqn')

	print(f"Inputs: {minimized.inputs}")
	print(f"Output: {minimized.output}")

	print(f"Expression: {minimized.expression}")
	print(f"Onset minterms: {minimized.get_onset_minterms()}")

	print(f"Canonical SOP: {minimized.get_canonical_SOP()}")
	print(f"Canonical POS: {minimized.get_canonical_POS()}")

	print(f"SOP of inverse: {minimized.get_inverse_SOP()}")
	print(f"POS of inverse: {minimized.get_inverse_POS()}")

	sop_cubes = []

	for term in boolean_expression.get_canonical_SOP():
		cube = f"{term:0{len(boolean_expression.inputs)}b}"
		sop_cubes.append(cube)

	boolean_expression.write_eqn_from_SOP_cubes(sop_cubes, './canonical.eqn')

	canonical_SOP = boolean_exp()
	canonical_SOP.parse_eqn('./canonical.eqn')

	print(f"Inputs: {canonical_SOP.inputs}")
	print(f"Output: {canonical_SOP.output}")

	print(f"Expression: {canonical_SOP.expression}")
	print(f"Onset minterms: {canonical_SOP.get_onset_minterms()}")

	print(f"Canonical SOP: {canonical_SOP.get_canonical_SOP()}")
	print(f"Canonical POS: {canonical_SOP.get_canonical_POS()}")

	print(f"SOP of inverse: {canonical_SOP.get_inverse_SOP()}")
	print(f"POS of inverse: {canonical_SOP.get_inverse_POS()}")