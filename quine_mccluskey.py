class QMC:
	def __init__(self):
		self.mcqueen_table = {}
	
	def table_from_SOP(self, SOP, inputs):
		if not SOP:
			raise ValueError("SOP cannot be empty. Please provide a valid SOP.")
		for minterm in SOP:
			num_ones = bin(minterm).count('1')
			if num_ones not in self.mcqueen_table:
				self.mcqueen_table[num_ones] = []
			self.mcqueen_table[num_ones].append(format(minterm, f'0{len(inputs)}b'))
		return self.mcqueen_table

	def print_mcqueen_table(self):
		if not self.mcqueen_table:
			self.table_from_SOP()
		print("\nMcQueen Table:")
		for num_ones in sorted(self.mcqueen_table.keys()):
			print(f"{num_ones} ones: {self.mcqueen_table[num_ones]}")

	def check_neighbours(self, term1, num_ones):
		"""
		Check if a minterm has any adjacent minterms in the next group (with one more 1).
		"""
		if num_ones + 1 not in self.mcqueen_table:
			return False
		for term2 in self.mcqueen_table[num_ones + 1]:
			if self.check_adjacency(term1, term2):
				print(f"Adjacent terms found: {term1} and {term2}")
				print(f"Merging {term1} and {term2} into {self.merge_terms(term1, term2)}")
				self.mcqueen_table[num_ones + 1].remove(term2)
				self.mcqueen_table[num_ones].remove(term1) 
				self.mcqueen_table[num_ones].append(self.merge_terms(term1, term2))
				return True
		return False

	def check_adjacency(self, term1, term2):
		"""
		Check if two terms are adjacent (differ by exactly one bit).
		"""
		diff_count = 0
		term1_free_dash = False
		term2_free_dash = False
		for bit1, bit2 in zip(term1, term2):
			if bit1 == bit2: # (0,0)(1,1)(-,-)
				continue
			elif (bit1 in ['0', '1'] and bit2 in ['0', '1']): # (0,1)(1,0)
				diff_count += 1
			else: # (-,x)
				if bit1 == '-':
					term1_free_dash = True
				if bit2 == '-':
					term2_free_dash = True

			if term1_free_dash and term2_free_dash:
				return False
			if diff_count > 1:
				return False

		return True
	
	def merge_terms(self, term1, term2):
		"""
		Merge two adjacent minterms into a new term with a '-' in the differing position.
		"""
		merged = []
		for bit1, bit2 in zip(term1, term2):
			if bit1 == bit2:
				merged.append(bit1)
			else:
				merged.append('-')
		return ''.join(merged)

	def find_prime_implicants(self, SOP, inputs):
		self.table_from_SOP(SOP, inputs)
		
		updated = True
		while updated:
			updated = False
			for num_ones in sorted(self.mcqueen_table.keys()):
				for term in self.mcqueen_table[num_ones][:]:  # Use a copy of the list to avoid modification issues
					updated |= self.check_neighbours(term, num_ones)

					self.print_mcqueen_table()  # Print the table after each merge to visualize the process
		