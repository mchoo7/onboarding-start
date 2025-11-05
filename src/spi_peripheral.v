/*
 * Copyright (c) 2025 Minsoo Choo
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module spi_peripheral (
    input  wire       clk,      // clock
    input  wire       rst_n,    // reset_n - low to reset
    input  wire [2:0] ui_in,
    output  reg [7:0] en_reg_out_7_0,
    output  reg [7:0] en_reg_out_15_8,
    output  reg [7:0] en_reg_pwm_7_0,
    output  reg [7:0] en_reg_pwm_15_8,
    output  reg [7:0] pwm_duty_cycle
);

    wire copi, nCS, sclk;

    assign copi = ui_in[1];
    assign nCS = ui_in[2];
    assign sclk = ui_in[0];

    reg [15:0] shift_reg;  // Shift register for incoming data
    reg [4:0] bit_count;   // Counter for received bits
    reg transaction_ready;
    reg transaction_processed;

    // 2-stage synchronizers for CDC
    reg sclk_sync1, sclk_sync2, sclk_prev;   // Edge-sensitive: N + 1 samples
    reg copi_sync1, copi_sync2;              // Value-sensitive: N samples
    reg nCS_sync1, nCS_sync2, nCS_prev;      // Edge-sensitive: N + 1 samples

    // Initialize registers to 0x00 per spec
    initial begin
        en_reg_out_7_0 = 8'h00;
        en_reg_out_15_8 = 8'h00;
        en_reg_pwm_7_0 = 8'h00;
        en_reg_pwm_15_8 = 8'h00;
        pwm_duty_cycle = 8'h00;
        bit_count = 5'b0;
        shift_reg = 16'b0;
        transaction_ready = 1'b0;
        transaction_processed = 1'b0;
        sclk_sync1 = 1'b0;
        sclk_sync2 = 1'b0;
        sclk_prev = 1'b0;
        copi_sync1 = 1'b0;
        copi_sync2 = 1'b0;
        nCS_sync1 = 1'b0;
        nCS_sync2 = 1'b0;
        nCS_prev = 1'b0;
    end

    // 2-stage synchronizers for all CDC signals
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sclk_sync1 <= 1'b0;
            sclk_sync2 <= 1'b0;
            sclk_prev <= 1'b0;
            copi_sync1 <= 1'b0;
            copi_sync2 <= 1'b0;
            nCS_sync1 <= 1'b0;
            nCS_sync2 <= 1'b0;
            nCS_prev <= 1'b0;
        end else begin
            // First stage - sample asynchronous inputs
            sclk_sync1 <= sclk;
            copi_sync1 <= copi;
            nCS_sync1 <= nCS;

            // Second stage - reduce metastability
            sclk_sync2 <= sclk_sync1;
            sclk_prev <= sclk_sync2;  // Extra sample for edge detection
            copi_sync2 <= copi_sync1;
            nCS_sync2 <= nCS_sync1;
            nCS_prev <= nCS_sync2;  // Extra sample for edge detection
        end
    end

    // Detect SCLK rising edge (edge-sensitive signal)
    wire sclk_rising_edge = (sclk_sync2 == 1'b1) && (sclk_prev == 1'b0);

    // Detect nCS rising edge (edge-sensitive signal)
    wire nCS_posedge = (nCS_sync2 == 1'b1) && (nCS_prev == 1'b0);

    // Process SPI protocol in the clk domain
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            bit_count <= 5'b0;
            shift_reg <= 16'b0;
            transaction_ready <= 1'b0;
        end else if (nCS_sync2 == 1'b0) begin
            // Transaction active (nCS is LOW)
            // Shift in data on rising edge of sclk (Mode 0)
            if (sclk_rising_edge) begin
                shift_reg <= {shift_reg[14:0], copi_sync2};
                bit_count <= bit_count + 1;
            end
        end else begin
            // When nCS goes high (transaction ends), validate the complete transaction
            if (nCS_posedge) begin
                transaction_ready <= 1'b1;
            end else if (transaction_processed) begin
                // Clear ready flag once processed
                transaction_ready <= 1'b0;
            end
            // Reset bit counter for next transaction after processing
            if (transaction_processed) begin
                bit_count <= 5'b0;
            end
        end
    end

    // Update registers only after the complete transaction has finished and been validated
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // omitted code
            transaction_processed <= 1'b0;
        end else if (transaction_ready && !transaction_processed) begin
            // Transaction is ready and not yet processed
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
            // Set the processed flag
            transaction_processed <= 1'b1;
        end else if (!transaction_ready && transaction_processed) begin
            // Reset processed flag when ready flag is cleared
            transaction_processed <= 1'b0;
        end
    end

endmodule
