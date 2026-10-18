module example(
	input a, b, c, d,
	output e);

	assign e = (a&b) | (c&d);
endmodule