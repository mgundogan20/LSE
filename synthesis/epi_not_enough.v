`timescale 1ns / 1ps
module epi_not_enough (
    input a,
    input b,
    input c,
    input d,
    output e
);

    wire pt_0, a_n, b_n, d_n, pt_1, c_n, pt_2, pt_3;

    and g_and_0 (pt_0, a, b);
    not g_not_a (a_n, a);
    not g_not_b (b_n, b);
    not g_not_d (d_n, d);
    and g_and_1 (pt_1, a_n, b_n, d_n);
    not g_not_c (c_n, c);
    and g_and_2 (pt_2, a_n, c_n, d);
    and g_and_3 (pt_3, b, c);
    or g_or_e (e, pt_0, pt_1, pt_2, pt_3);

endmodule
