# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb.triggers import ClockCycles
from cocotb.types import Logic
from cocotb.types import LogicArray

async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(unit="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100*100*0.5) < cocotb.utils.get_sim_time(unit="ns"):
            break
    return

def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")

async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data
    
    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)")
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)")
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)

@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, unit="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000) 

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x30, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")

@cocotb.test()
async def test_pwm_freq(dut):
    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, unit="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("PWM frequency test")

    # Configure output register (bits 4-7 high)
    await send_spi_transaction(dut, 1, 0x00, 0xF0)

    # Enable PWM on bits 4-7
    await send_spi_transaction(dut, 1, 0x02, 0xF0)

    # Set 50% duty cycle
    await send_spi_transaction(dut, 1, 0x04, 0x80)

    # Wait for PWM to stabilize
    await ClockCycles(dut.clk, 5000)

    # Wait for bit 4 to go low first (start from known state)
    max_wait = 100000
    wait_count = 0
    while wait_count < max_wait:
        await ClockCycles(dut.clk, 1)
        curr_val = (int(dut.uo_out.value) >> 4) & 1
        if curr_val == 0:
            break
        wait_count += 1

    # Wait for first rising edge and capture time
    prev_val = 0
    wait_count = 0
    while wait_count < max_wait:
        await ClockCycles(dut.clk, 1)
        curr_val = (int(dut.uo_out.value) >> 4) & 1
        if prev_val == 0 and curr_val == 1:
            time_first_edge = cocotb.utils.get_sim_time(unit='ns')
            break
        prev_val = curr_val
        wait_count += 1

    # Wait for the signal to go back low (falling edge)
    wait_count = 0
    while wait_count < max_wait:
        await ClockCycles(dut.clk, 1)
        curr_val = (int(dut.uo_out.value) >> 4) & 1
        if curr_val == 0:
            break
        wait_count += 1

    # Wait for second rising edge and capture time
    prev_val = 0
    wait_count = 0
    while wait_count < max_wait:
        await ClockCycles(dut.clk, 1)
        curr_val = (int(dut.uo_out.value) >> 4) & 1
        if prev_val == 0 and curr_val == 1:
            time_second_edge = cocotb.utils.get_sim_time(unit='ns')
            break
        prev_val = curr_val
        wait_count += 1
    
    # Calculate the period
    period = time_second_edge - time_first_edge
    dut._log.info(f"PWM Period: {period} ns")

    # Calculate frequency (convert from ns period to Hz)
    frequency_hz = 1e9 / period
    dut._log.info(f"PWM Frequency: {frequency_hz} Hz")

    expected_frequency = 3000
    tolerance_percent = 1.0  # ±1% tolerance
    tolerance_hz = expected_frequency * (tolerance_percent / 100.0)
    assert abs(frequency_hz - expected_frequency) < tolerance_hz, \
        f"Frequency mismatch! Expected: {expected_frequency} Hz ±{tolerance_percent}%, Got: {frequency_hz} Hz"

    dut._log.info("PWM Frequency test completed successfully")

@cocotb.test()
async def test_pwm_duty(dut):
    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, unit="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("PWM duty cycle test")

    # Test multiple duty cycle values
    test_cases = [
        (0x40, 25.0),  # 25% duty cycle (64/256)
        (0x80, 50.0),  # 50% duty cycle (128/256)
        (0xC0, 75.0),  # 75% duty cycle (192/256)
    ]

    for duty_value, expected_duty_percent in test_cases:
        dut._log.info(f"Testing duty cycle: {duty_value:#04x} (expected {expected_duty_percent}%)")

        # Configure output register (bits 4-7 high)
        await send_spi_transaction(dut, 1, 0x00, 0xF0)

        # Enable PWM on bits 4-7
        await send_spi_transaction(dut, 1, 0x02, 0xF0)

        # Set duty cycle
        await send_spi_transaction(dut, 1, 0x04, duty_value)

        # Wait for PWM to stabilize
        await ClockCycles(dut.clk, 5000)

        # Wait for bit 4 to go low first (start from known state)
        max_wait = 100000
        wait_count = 0
        while wait_count < max_wait:
            await ClockCycles(dut.clk, 1)
            curr_val = (int(dut.uo_out.value) >> 4) & 1
            if curr_val == 0:
                break
            wait_count += 1

        # Wait for rising edge and capture time
        prev_val = 0
        wait_count = 0
        while wait_count < max_wait:
            await ClockCycles(dut.clk, 1)
            curr_val = (int(dut.uo_out.value) >> 4) & 1
            if prev_val == 0 and curr_val == 1:
                t_rising_edge = cocotb.utils.get_sim_time(unit='ns')
                break
            prev_val = curr_val
            wait_count += 1

        # Wait for falling edge and capture time
        wait_count = 0
        while wait_count < max_wait:
            await ClockCycles(dut.clk, 1)
            curr_val = (int(dut.uo_out.value) >> 4) & 1
            if curr_val == 0:
                t_falling_edge = cocotb.utils.get_sim_time(unit='ns')
                break
            wait_count += 1

        # Wait for next rising edge to calculate period
        prev_val = 0
        wait_count = 0
        while wait_count < max_wait:
            await ClockCycles(dut.clk, 1)
            curr_val = (int(dut.uo_out.value) >> 4) & 1
            if prev_val == 0 and curr_val == 1:
                t_next_rising_edge = cocotb.utils.get_sim_time(unit='ns')
                break
            prev_val = curr_val
            wait_count += 1

        # Calculate high time and period
        high_time = t_falling_edge - t_rising_edge
        period = t_next_rising_edge - t_rising_edge

        # Calculate duty cycle percentage
        duty_cycle_percent = (high_time / period) * 100.0

        dut._log.info(f"High time: {high_time} ns, Period: {period} ns")
        dut._log.info(f"Measured duty cycle: {duty_cycle_percent:.2f}%")

        # Verify duty cycle (allow ±1% tolerance)
        tolerance_percent = 1.0
        assert abs(duty_cycle_percent - expected_duty_percent) < tolerance_percent, \
            f"Duty cycle mismatch! Expected: {expected_duty_percent}% ±{tolerance_percent}%, Got: {duty_cycle_percent:.2f}%"

    # Test 0% duty cycle - signal should always be low
    dut._log.info("Testing duty cycle: 0x00 (expected 0%)")
    await send_spi_transaction(dut, 1, 0x00, 0xF0)
    await send_spi_transaction(dut, 1, 0x02, 0xF0)
    await send_spi_transaction(dut, 1, 0x04, 0x00)
    await ClockCycles(dut.clk, 5000)

    # Check that bit 4 remains low for an extended period
    all_low = True
    for _ in range(10000):
        await ClockCycles(dut.clk, 1)
        curr_val = (int(dut.uo_out.value) >> 4) & 1
        if curr_val == 1:
            all_low = False
            break
    assert all_low, "0% duty cycle failed: signal went high"
    dut._log.info("0% duty cycle verified: signal stayed low")

    # Test 100% duty cycle - signal should always be high
    dut._log.info("Testing duty cycle: 0xff (expected 100%)")
    await send_spi_transaction(dut, 1, 0x00, 0xF0)
    await send_spi_transaction(dut, 1, 0x02, 0xF0)
    await send_spi_transaction(dut, 1, 0x04, 0xFF)
    await ClockCycles(dut.clk, 5000)

    # Check that bit 4 remains high for an extended period
    all_high = True
    for _ in range(10000):
        await ClockCycles(dut.clk, 1)
        curr_val = (int(dut.uo_out.value) >> 4) & 1
        if curr_val == 0:
            all_high = False
            break
    assert all_high, "100% duty cycle failed: signal went low"
    dut._log.info("100% duty cycle verified: signal stayed high")

    dut._log.info("PWM duty cycle test completed successfully")
