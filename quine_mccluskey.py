import numpy as np
import copy

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
		print("Merging minterms to find prime implicants:")
		updated = True
		while updated:
			updated = False
			last_qmc = copy.deepcopy(self.qmc_table)
			for num_ones in sorted(last_qmc.keys()):
				for term in last_qmc[num_ones][:]:
					updated |= self.check_neighbours(term, num_ones, last_qmc)
			if updated:
				print("Updated qmc table")

		for term in self.qmc_table.values():
			self.PIs.extend(set(term))

	def check_term_coverage(self, term):
		covered_terms = []
		if '-' not in term:
			covered_terms.append(term)
		else:
			pos = term.find('-')

			term0 = term[:pos] + '0' + term[pos+1:]
			term1 = term[:pos] + '1' + term[pos+1:]

			covered_terms.extend(self.check_term_coverage(term0))
			covered_terms.extend(self.check_term_coverage(term1))
			
		return covered_terms
						
	def build_PI_chart(self, inputs, implicants):
		binaries = {}
		for impl in implicants:
			binaries[impl] = self.check_term_coverage(impl)
		
		PI_chart = np.zeros(shape=(len(implicants), 2**len(inputs)))
		PIC_dict = {}

		row = 0
		for key, value in binaries.items():
			minterms = [int("0b"+bin, base=2) for bin in value]
			PI_chart[row][minterms] = 1
			PIC_dict[key] = row
			row += 1

		print(f"\nPrime implicants are:")
		for key in PIC_dict.keys():
			print(key)
		return PIC_dict, PI_chart

	def find_EPIs(self, PIC_dict, PI_chart):
		essentials = []
		remaining_minterms = [int(i) for i in np.argwhere(PI_chart.sum(axis=0)==1)]
		
		while len(remaining_minterms) > 0:
			mt = remaining_minterms.pop()
			row_of_mt = np.argwhere(PI_chart[:,int(mt)] == 1)
			for impl, row in PIC_dict.items():
				if row == row_of_mt:
					essentials.append(impl)
					covered_by_EPI = np.argwhere(PI_chart[row]==1)

					for ter in covered_by_EPI:
						try:
							remaining_minterms.remove(int(ter))
						except ValueError as e:
							continue

		print(f"Remaining must-have implicants: {essentials}")
		return essentials

	def reduce_chart(self, PIC_dict, PI_chart, EPIs):
		rows_to_rem = set()
		cols_to_rem = set()
		for impl in EPIs:
			print("\nPIC:")
			print(PI_chart)
			print(PIC_dict)
			print()

			row = PIC_dict[impl]
			cols = [int(i) for i in (np.argwhere(PI_chart[row]==1))]

			rows_to_rem.add(row)
			cols_to_rem.update(cols)

			print(f"Considering {impl}:")
			print(f"Remove rows: {rows_to_rem}")
			print(f"Remove cols: {cols_to_rem}")

			self.MinExp.append(impl)

			PI_chart[row,:] = 0
			PI_chart[:, cols] = 0

			PIC_dict.pop(impl)
		
		print("\nPIC:")
		print(PI_chart)
		print(PIC_dict)

	def petricks(self, PIC, PIC_dict):
		"""
		Cover the minterms left after removing the EPIs using Petrick's method.
		"""
		remaining_minterms = [int(minterm) for minterm in np.flatnonzero(PIC.sum(axis=0) > 0)]
		if not remaining_minterms:
			print("\nNo minterms left to cover, Petrick's method is not needed")
			return []

		row_to_implicant = {row: impl for impl, row in PIC_dict.items()}

		print("\n There are missing minterms, using Pertick's to cover them.")
		# Multiply out the product of sums, one minterm (sum) at a time
		products = {frozenset()}
		for minterm in remaining_minterms:
			covering_implicants = [row_to_implicant[int(row)] for row in np.flatnonzero(PIC[:, minterm] == 1)]
			expanded = set()
			for product in products:
				for impl in covering_implicants:
					expanded.add(product | {impl})
			# Absorption: X + XY = X
			products = {product for product in expanded if not any(other < product for other in expanded)}
			print(f"After minterm {minterm}: {[sorted(product) for product in products]}")

		def cost(product):
			literal_count = sum(len(impl) - impl.count('-') for impl in product)
			return (len(product), literal_count, sorted(product))

		cheapest_cover = sorted(min(products, key=cost))
		print(f"\nPetrick's method selected: {cheapest_cover}")

		self.MinExp.extend(cheapest_cover)
		return cheapest_cover


	def find_minimal_expression(self, SOP, inputs):
		self.table_from_SOP(SOP, inputs)
		
		self.find_prime_implicants(SOP, inputs)

		PIC_dict, PI_chart = self.build_PI_chart(inputs, self.PIs)

		print("\nOptimizing Prime Implicant Chart")
		self.EPIs = self.find_EPIs(PIC_dict, PI_chart)
		self.reduce_chart(PIC_dict, PI_chart, self.EPIs)
		self.petricks(PI_chart, PIC_dict)

		return(self.MinExp)
		

