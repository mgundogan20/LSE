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

and(sel0, s0bar, s1bar);
and(sel1, s0bar, sel[1]);
and(sel2, sel[0], s1bar);
and(sel3, sel[0], sel[1]);

and(out, a, sel0);
and(out, b, sel1);
and(out, c, sel2);
and(out, d, sel3);
endmodule