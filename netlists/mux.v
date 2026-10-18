module example(a,b,c,d,sel,out);

input wire a;
input wire b;
input wire c;
input wire d;
input wire [1:0] sel;
output wire out;

wire s0bar, s1bar;
not(s0bar, sel[0]);
not(s1bar, sel[1]);

wire sel0, sel1, sel2, sel3;

and(sel0, s1bar, s0bar);
and(sel1, s1bar, sel[0]);
and(sel2, sel[1], s0bar);
and(sel3, sel[1], sel[0]);

wire out0, out1, out2, out3;

and(out0, a, sel0);
and(out1, b, sel1);
and(out2, c, sel2);
and(out3, d, sel3);

or(out, out0, out1, out2, out3);
endmodule