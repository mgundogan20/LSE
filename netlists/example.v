module example(
  input  wire [9:0] x,
  output wire       f
);
  wire x2n, x3n, x5n, x6n, x8n;
  not g0 (x2n, x[2]);
  not g1 (x3n, x[3]);
  not g2 (x5n, x[5]);
  not g3 (x6n, x[6]);
  not g4 (x8n, x[8]);

  wire n1, A;
  and g5 (n1, x[0], x3n);
  or  g6 (A,  n1,   x[7]);

  wire n2, n3, n4, B;
  and g7  (n2, x5n, x[8]);
  or  g8  (n3, x[1], n2);
  xor g9  (n4, x2n, x[9]);
  and g10 (B,  n3,  n4);

  wire n5, C;
  or  g11 (n5, x[3], x8n);
  and g12 (C,  x[4], x6n, n5);

  wire n6;
  or  g13 (n6, B, C);
  xor g14 (f,  A, n6);
endmodule