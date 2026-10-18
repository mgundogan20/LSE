
module example(
	input a, b, c, d,
	output e);

	wire t1;
	wire t2;

	and (t1, a, b);
	and (t2, c, d);

	or (e, t1, t2);
endmodule