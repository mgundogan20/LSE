module example4(
	input a, b, c, d,
	output e
);
	assign e = a&((b^d) ^ (c|d));
endmodule