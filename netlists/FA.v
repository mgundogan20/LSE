module example(i1, i2, cin, sum);
input wire i1;
input wire i2;
input wire cin;
output wire sum;

wire w1, w2, w3;
xor(w1, i1, i2);
xor(sum, w1, cin);
and(w2, w1, cin);
and(w3, i1, i2);
endmodule