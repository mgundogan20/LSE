
module example(
	input a, b, c, d,
	output e);

	always begin
		e <= (a&b) | (c&d);
	end
endmodule