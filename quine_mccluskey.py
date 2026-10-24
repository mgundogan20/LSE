class QMC:
	def __init__(self):
		self.qmc_table = {}
		self.PIs = []
		self.EPIs = []
		self.MinExp = []
	
	def table_from_SOP(self, SOP, inputs):
		if not SOP:
			raise ValueError("SOP cannot be empty. Please provide a valid SOP.")
		for minterm in SOP:
			num_ones = bin(minterm).count('1')
			if num_ones not in self.qmc_table:
				self.qmc_table[num_ones] = []
			self.qmc_table[num_ones].append(format(minterm, f'0{len(inputs)}b'))

		print(f"\nGenerated QMC table from SOP list:")
		self.print_qmc_table()
		return self.qmc_table

	def print_qmc_table(self):
		if not self.qmc_table:
			self.table_from_SOP()
		print("qmc Table:")
		for num_ones in sorted(self.qmc_table.keys()):
			print(f"{num_ones} ones: {self.qmc_table[num_ones]}")
		print()

	def check_neighbours(self, term1, num_ones, qmc_table):
		"""
		Check if a minterm has any adjacent minterms in the next group (with one more 1).
		"""
		print(f"\nChecking {term1}")
		updated = False
		if num_ones + 1 not in qmc_table:
			return False
		for term2 in qmc_table[num_ones + 1].copy():
			print(f"Checking terms {term1} and {term2}")
			if self.check_adjacency(term1, term2):
				print(f"Adjacent terms found: {term1} and {term2}")
				print(f"Merging {term1} and {term2} into {self.merge_terms(term1, term2)}")
				try:
					self.qmc_table[num_ones + 1].remove(term2)
				except ValueError as e:
					print(e)

				self.qmc_table[num_ones].append(self.merge_terms(term1, term2))
				updated = True
		if updated:
			try:
				self.qmc_table[num_ones].remove(term1) 
			except ValueError as e:
				print(e)

			self.print_qmc_table()
		return updated

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
		