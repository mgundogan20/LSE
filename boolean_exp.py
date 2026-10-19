import re

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
		print(f"Expanded expression for {self.output}: {self.expression}\n")
		
		return self.expression

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
		
if __name__ == "__main__":
	boolean_expression = boolean_exp()
	boolean_expression.parse_eqn('./example_eqns/sop_continuous_single.eqn')
	boolean_expression.onset_minterms_brute_force()
