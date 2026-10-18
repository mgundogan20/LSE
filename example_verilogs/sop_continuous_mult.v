
module example(
	input a, b, c, d,
	output e);

	wire t1;
	wire t2;

	assign t1 = a&b;
	assign t2 = c&d;

	assign e = t1 | t2;
endmodule