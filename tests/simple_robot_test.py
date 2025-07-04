#!/usr/bin/env python3
"""
Simple Robot Data Test
======================

This script tests if the robot is publishing any data at all,
bypassing RPC services to diagnose connection issues.

Usage:
    python3 simple_robot_test.py <interface>
"""

import sys
import time
import os
from datetime import datetime
from threading import Event

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_

# Color codes for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

class TestLogger:
    """Handles both console and file logging for the robot test"""
    
    def __init__(self, interface: str):
        self.interface = interface
        self.start_time = datetime.now()
        
        # Create logs directory if it doesn't exist
        self.log_dir = "test_logs"
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Create timestamped log file
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(self.log_dir, f"robot_test_{interface}_{timestamp}.txt")
        
        # Initialize log file with header
        self._write_header()
        
    def _write_header(self):
        """Write test header to log file"""
        header = f"""
================================================================================
UNITREE ROBOT DATA TEST LOG
================================================================================
Test Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
Interface: {self.interface}
Test Purpose: Check if robot is publishing data (bypass RPC services)
================================================================================

"""
        with open(self.log_file, 'w') as f:
            f.write(header)
    
    def log(self, message: str, status: str = "INFO", console_only: bool = False):
        """Log message to both console and file"""
        # Console output with colors
        color = Colors.BLUE
        if status == "SUCCESS":
            color = Colors.GREEN
        elif status == "ERROR":
            color = Colors.RED
        elif status == "WARNING":
            color = Colors.YELLOW
        
        console_msg = f"{color}[{status}]{Colors.RESET} {message}"
        print(console_msg)
        
        # File output without colors (unless console_only is True)
        if not console_only:
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]  # Include milliseconds
            file_msg = f"[{timestamp}] [{status}] {message}\n"
            
            with open(self.log_file, 'a') as f:
                f.write(file_msg)
    
    def log_data(self, data: str):
        """Log data without status prefix"""
        print(data)
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        file_msg = f"[{timestamp}] {data}\n"
        
        with open(self.log_file, 'a') as f:
            f.write(file_msg)
    
    def log_robot_data(self, msg: LowState_, packet_num: int):
        """Log detailed robot data"""
        data_log = f">>> ROBOT DATA PACKET #{packet_num} <<<"
        self.log_data(data_log)
        
        # IMU Data
        if hasattr(msg, 'imu_state') and hasattr(msg.imu_state, 'rpy'):
            imu_data = f"  IMU Roll/Pitch/Yaw: {msg.imu_state.rpy}"
            self.log_data(imu_data)
        
        # Robot Mode
        if hasattr(msg, 'mode_machine'):
            mode_data = f"  Robot Mode: {msg.mode_machine}"
            self.log_data(mode_data)
        
        # Motor State
        if hasattr(msg, 'motor_state') and msg.motor_state:
            try:
                motor_count = len(msg.motor_state)  # type: ignore
                motor_data = f"  Motor Count: {motor_count}"
                self.log_data(motor_data)
                
                if motor_count > 0:
                    first_motor = f"  First Motor Position: {msg.motor_state[0].q:.3f}"  # type: ignore
                    self.log_data(first_motor)
                    
                    # Log first few motor positions for more detail
                    if motor_count > 1:
                        motor_positions = "  Motor Positions (first 5): "
                        for i in range(min(5, motor_count)):
                            motor_positions += f"[{i}]={msg.motor_state[i].q:.3f} "  # type: ignore
                        self.log_data(motor_positions)
            except Exception as e:
                error_msg = f"  Motor State: Available (details not accessible: {str(e)})"
                self.log_data(error_msg)
        
        # Battery State (if available)
        if hasattr(msg, 'battery_state'):
            try:
                battery_data = f"  Battery Level: {msg.battery_state.level}%"  # type: ignore
                self.log_data(battery_data)
            except:
                self.log_data("  Battery State: Available (details not accessible)")
        
        # Foot contact state (if available)
        if hasattr(msg, 'foot_force'):
            try:
                foot_data = f"  Foot Forces: {msg.foot_force}"  # type: ignore
                self.log_data(foot_data)
            except:
                self.log_data("  Foot Contact: Available (details not accessible)")
        
        self.log_data("")  # Empty line for readability
    
    def finalize_log(self, success: bool, received_count: int, test_duration: float):
        """Write final test summary to log file"""
        end_time = datetime.now()
        
        summary = f"""
================================================================================
TEST SUMMARY
================================================================================
Test Completed: {end_time.strftime('%Y-%m-%d %H:%M:%S')}
Test Duration: {test_duration:.2f} seconds
Total Packets Received: {received_count}
Test Result: {'SUCCESS' if success else 'FAILED'}

Network Analysis:
- Interface Used: {self.interface}
- DDS Communication: {'WORKING' if success else 'FAILED'}
- Robot State Publishing: {'ACTIVE' if success else 'INACTIVE'}

"""
        
        if success:
            summary += """
DIAGNOSIS: Robot hardware connection is GOOD
- Network connectivity is working
- DDS communication is working  
- Robot is powered on and publishing data
- Only RPC services may not be responding

NEXT STEPS:
1. Robot hardware connection is verified as good
2. If RPC services still failing, check:
   - Robot mode (try robot app to check)
   - Services still starting up (wait and retry)
   - Robot in manual control mode
3. Low-level examples should work even with RPC issues
"""
        else:
            summary += """
DIAGNOSIS: Robot NOT publishing data
- Robot may not be publishing state data
- Robot might be in sleep/standby mode
- Robot services may not be running

TROUBLESHOOTING STEPS:
1. Check if robot is fully powered on
2. Check robot status via official app
3. Try restarting robot
4. Verify robot firmware version
5. Check robot documentation for startup sequence
"""
        
        summary += f"""
================================================================================
Log File Location: {self.log_file}
================================================================================
"""
        
        with open(self.log_file, 'a') as f:
            f.write(summary)
        
        print(f"\n{Colors.BOLD}📝 Complete test log saved to:{Colors.RESET} {self.log_file}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 simple_robot_test.py <interface>")
        print("Example: python3 simple_robot_test.py eth0")
        sys.exit(1)
    
    interface = sys.argv[1]
    
    # Initialize logger
    logger = TestLogger(interface)
    
    print(f"""
{Colors.BOLD}Simple Robot Data Test{Colors.RESET}
{Colors.BLUE}======================{Colors.RESET}

Testing if robot is publishing data on interface: {interface}
This test bypasses RPC services and just listens for robot state data.
""")
    
    logger.log("=== STARTING ROBOT DATA TEST ===")
    logger.log(f"Testing interface: {interface}")
    logger.log("Test purpose: Check if robot is publishing data (bypass RPC services)")
    
    test_start_time = time.time()
    
    try:
        # Initialize DDS communication
        logger.log("Initializing DDS communication...")
        ChannelFactoryInitialize(0, interface)  # type: ignore
        logger.log("DDS initialized successfully", "SUCCESS")
        
        # Set up data reception
        data_received = Event()
        received_count = 0
        
        def state_handler(msg: LowState_):
            nonlocal received_count
            received_count += 1
            
            logger.log(f"Received data packet #{received_count}", "SUCCESS")
            
            # Log detailed robot data
            logger.log_robot_data(msg, received_count)
            
            # Set the event after first successful data reception
            if not data_received.is_set():
                data_received.set()
        
        # Create subscriber for robot state
        logger.log("Creating robot state subscriber...")
        lowstate_subscriber = ChannelSubscriber("rt/lowstate", LowState_)
        lowstate_subscriber.Init(state_handler, 10)
        logger.log("Subscriber created successfully", "SUCCESS")
        
        # Wait for data
        logger.log("Listening for robot data (20 second timeout)...")
        print("Press Ctrl+C to stop early")
        
        start_time = time.time()
        timeout = 20.0
        
        try:
            while not data_received.is_set() and (time.time() - start_time) < timeout:
                time.sleep(0.1)
                
                # Show progress every 5 seconds
                elapsed = time.time() - start_time
                if int(elapsed) % 5 == 0 and elapsed > 0:
                    remaining = timeout - elapsed
                    logger.log(f"Still listening... {remaining:.0f} seconds remaining")
                    time.sleep(1)  # Avoid rapid repeated messages
        
        except KeyboardInterrupt:
            logger.log("\nTest interrupted by user", "WARNING")
        
        test_duration = time.time() - test_start_time
        
        # Results
        if data_received.is_set():
            logger.log("🎉 SUCCESS: Robot is publishing data!", "SUCCESS")
            logger.log(f"Received {received_count} data packets", "INFO")
            logger.log(f"Test completed in {test_duration:.2f} seconds", "INFO")
            logger.log_data("")
            logger.log_data("ANALYSIS:")
            logger.log_data("✅ Network connectivity is working")
            logger.log_data("✅ DDS communication is working")
            logger.log_data("✅ Robot is powered on and publishing data")
            logger.log_data("❌ Only RPC services are not responding")
            logger.log_data("")
            logger.log_data("NEXT STEPS:")
            logger.log_data("1. The robot hardware connection is good")
            logger.log_data("2. RPC service issue might be:")
            logger.log_data("   - Robot in wrong mode (try robot app to check)")
            logger.log_data("   - Services still starting up (wait and retry)")
            logger.log_data("   - Robot in manual control mode")
            logger.log_data("3. You can try running examples that don't require RPC:")
            logger.log_data(f"   python3 ./example/g1/low_level/g1_low_level_example.py {interface}")
            logger.log_data("   (The example might work even with RPC issues)")
        else:
            logger.log("❌ No robot data received", "ERROR")
            logger.log(f"Test completed in {test_duration:.2f} seconds", "INFO")
            logger.log_data("")
            logger.log_data("ANALYSIS:")
            logger.log_data("❌ Robot may not be publishing state data")
            logger.log_data("❌ Robot might be in sleep/standby mode")
            logger.log_data("❌ Robot services may not be running")
            logger.log_data("")
            logger.log_data("TROUBLESHOOTING:")
            logger.log_data("1. Check if robot is fully powered on")
            logger.log_data("2. Check robot status via official app")
            logger.log_data("3. Try restarting robot")
            logger.log_data("4. Verify robot firmware version")
            logger.log_data("5. Check robot documentation for startup sequence")
        
        # Finalize log file
        logger.finalize_log(data_received.is_set(), received_count, test_duration)
        
        # Clean up
        lowstate_subscriber.Close()
        
    except Exception as e:
        test_duration = time.time() - test_start_time
        logger.log(f"Test failed with error: {str(e)}", "ERROR")
        logger.log_data("\n=== EXCEPTION TRACEBACK ===")
        import traceback
        traceback.print_exc()
        
        # Log traceback to file
        with open(logger.log_file, 'a') as f:
            f.write(f"\n[{datetime.now().strftime('%H:%M:%S')}] EXCEPTION TRACEBACK:\n")
            f.write(traceback.format_exc())
        
        logger.finalize_log(False, 0, test_duration)
        sys.exit(1)

if __name__ == "__main__":
    main() 