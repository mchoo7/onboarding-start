/*
 * Copyright (c) 2025 Minsoo Choo
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module spi_peripheral (
    input  wire [2:0] ui_in,
    output  reg [7:0] en_reg_out_7_0,
    output  reg [7:0] en_reg_out_15_8,
    output  reg [7:0] en_reg_pwm_7_0,
    output  reg [7:0] en_reg_pwm_15_8,
    output  reg [7:0] pwm_duty_cycle
);

    wire copi, ncs, sclk;

    assign copi = ui_in[1];
    assign ncs = ui_in[2];
    assign sclk = ui_in[0];

    reg [15:0] shift_reg;  // Shift register for incoming data
    reg [4:0] bit_count;  // Counter for received bits

    // Initialize registers to 0x00 per spec
    initial begin
        en_reg_out_7_0 = 8'h00;
        en_reg_out_15_8 = 8'h00;
        en_reg_pwm_7_0 = 8'h00;
        en_reg_pwm_15_8 = 8'h00;
        pwm_duty_cycle = 8'h00;
        bit_count = 5'b0;
        shift_reg = 16'b0;
    end

    always @(posedge sclk or negedge ncs) begin
        if (!ncs) begin
        // Transaction starts on falling edge of nCS
        bit_count <= 5'b0;
        shift_reg <= 16'b0;
        end else begin
        // Shift in data on rising edge of sclk (Mode 0)
        shift_reg <= {shift_reg[14:0], copi};
        bit_count <= bit_count + 1;
        end
    end

    // Process complete transaction when nCS goes high
    always @(posedge ncs) begin
        if (bit_count == 5'd16) begin
        // Check if Write operation (bit 15 = 1)
        if (shift_reg[15]) begin
            case (shift_reg[14:8])  // 7-bit address
            7'h00: en_reg_out_7_0 <= shift_reg[7:0];
            7'h01: en_reg_out_15_8 <= shift_reg[7:0];
            7'h02: en_reg_pwm_7_0 <= shift_reg[7:0];
            7'h03: en_reg_pwm_15_8 <= shift_reg[7:0];
            7'h04: pwm_duty_cycle <= shift_reg[7:0];
            default: begin end  // Ignore invalid addresses
            endcase
        end
        end
    end

endmodule
