#!/usr/bin/env python3
"""
Phase 2 validation script.

This script validates that all Phase 2 components are working correctly:
- MQTT broker connectivity
- Telemetry service functionality
- Message format validation
- Log file creation
- Service management

Usage:
    python scripts/validate_phase2.py [--verbose]
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import paho.mqtt.client as mqtt  # type: ignore


class Phase2Validator:
    """Validate Phase 2 telemetry system components."""
    
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.results: List[Dict[str, Any]] = []
        self.device_id = "pi-drone-01"
        self.telemetry_topic = f"drone/{self.device_id}/telemetry"
        
    def setup_logging(self) -> None:
        """Configure logging."""
        level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)]
        )
    
    def log_result(self, test_name: str, passed: bool, message: str, details: Any = None) -> None:
        """Log test result."""
        status = "✅ PASS" if passed else "❌ FAIL"
        logging.info("%s %s: %s", status, test_name, message)
        
        self.results.append({
            "test": test_name,
            "passed": passed,
            "message": message,
            "details": details
        })
    
    def test_mqtt_broker(self) -> bool:
        """Test MQTT broker connectivity."""
        try:
            client = mqtt.Client()
            client.connect("localhost", 1883, 5)
            client.disconnect()
            self.log_result("MQTT Broker", True, "Broker is accessible on localhost:1883")
            return True
        except Exception as exc:
            self.log_result("MQTT Broker", False, f"Broker connection failed: {exc}")
            return False
    
    def test_telemetry_service_file(self) -> bool:
        """Test telemetry service file exists and is executable."""
        service_file = Path("src/telemetry_service.py")
        if not service_file.exists():
            self.log_result("Telemetry Service File", False, "telemetry_service.py not found")
            return False
        
        # Check if file is readable
        try:
            with service_file.open("r") as f:
                content = f.read()
                if "class TelemetryAggregator" in content:
                    self.log_result("Telemetry Service File", True, "Service file exists and contains main class")
                    return True
                else:
                    self.log_result("Telemetry Service File", False, "Service file missing main class")
                    return False
        except Exception as exc:
            self.log_result("Telemetry Service File", False, f"Failed to read service file: {exc}")
            return False
    
    def test_systemd_service(self) -> bool:
        """Test systemd service file exists."""
        service_file = Path("scripts/telemetry.service")
        if not service_file.exists():
            self.log_result("Systemd Service File", False, "telemetry.service not found")
            return False
        
        try:
            with service_file.open("r") as f:
                content = f.read()
                if "[Unit]" in content and "[Service]" in content:
                    self.log_result("Systemd Service File", True, "Service file has correct format")
                    return True
                else:
                    self.log_result("Systemd Service File", False, "Service file missing required sections")
                    return False
        except Exception as exc:
            self.log_result("Systemd Service File", False, f"Failed to read service file: {exc}")
            return False
    
    def test_telemetry_dry_run(self) -> bool:
        """Test telemetry service in dry-run mode."""
        try:
            # Start telemetry service in dry-run mode
            process = subprocess.Popen(
                [sys.executable, "src/telemetry_service.py", "--dry-run", "--log-level", "WARNING"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Let it run for 5 seconds
            time.sleep(5)
            
            # Check if process is still running
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
                self.log_result("Telemetry Dry-Run", True, "Service started and ran successfully in dry-run mode")
                return True
            else:
                stdout, stderr = process.communicate()
                self.log_result("Telemetry Dry-Run", False, f"Service exited early. stderr: {stderr}")
                return False
                
        except Exception as exc:
            self.log_result("Telemetry Dry-Run", False, f"Failed to test dry-run mode: {exc}")
            return False
    
    def test_telemetry_message_format(self) -> bool:
        """Test telemetry message format by subscribing to MQTT."""
        try:
            received_messages = []
            
            def on_message(client, userdata, msg):
                try:
                    data = json.loads(msg.payload.decode("utf-8"))
                    received_messages.append(data)
                except Exception:
                    pass
            
            client = mqtt.Client()
            client.on_message = on_message
            client.connect("localhost", 1883, 5)
            client.subscribe(self.telemetry_topic)
            client.loop_start()
            
            # Wait for messages
            time.sleep(3)
            client.loop_stop()
            client.disconnect()
            
            if received_messages:
                # Validate message format
                msg = received_messages[0]
                required_fields = ["device_id", "timestamp", "battery", "camera"]
                missing_fields = [field for field in required_fields if field not in msg]
                
                if not missing_fields:
                    self.log_result("Telemetry Message Format", True, 
                                  f"Received {len(received_messages)} messages with correct format")
                    return True
                else:
                    self.log_result("Telemetry Message Format", False, 
                                  f"Missing required fields: {missing_fields}")
                    return False
            else:
                self.log_result("Telemetry Message Format", False, "No telemetry messages received")
                return False
                
        except Exception as exc:
            self.log_result("Telemetry Message Format", False, f"Failed to test message format: {exc}")
            return False
    
    def test_log_files(self) -> bool:
        """Test log file creation and structure."""
        log_path = Path("/home/pi/drone/telemetry/telemetry.log")
        
        # Check if log directory exists
        if not log_path.parent.exists():
            self.log_result("Log Files", False, "Log directory does not exist")
            return False
        
        # Check if log file exists (might not exist if service hasn't run)
        if log_path.exists():
            try:
                with log_path.open("r") as f:
                    lines = f.readlines()
                    if lines:
                        # Try to parse last line as JSON
                        last_line = lines[-1].strip()
                        json.loads(last_line)
                        self.log_result("Log Files", True, f"Log file exists with {len(lines)} entries")
                        return True
                    else:
                        self.log_result("Log Files", False, "Log file is empty")
                        return False
            except Exception as exc:
                self.log_result("Log Files", False, f"Failed to read log file: {exc}")
                return False
        else:
            self.log_result("Log Files", True, "Log directory exists (file will be created when service runs)")
            return True
    
    def test_script_files(self) -> bool:
        """Test that all required script files exist."""
        required_files = [
            "scripts/setup_mqtt_broker.sh",
            "scripts/install_telemetry_service.sh", 
            "scripts/test_telemetry.py",
            "scripts/monitor_telemetry.py"
        ]
        
        missing_files = []
        for file_path in required_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        if not missing_files:
            self.log_result("Script Files", True, f"All {len(required_files)} required scripts exist")
            return True
        else:
            self.log_result("Script Files", False, f"Missing files: {missing_files}")
            return False
    
    def test_dependencies(self) -> bool:
        """Test that required Python dependencies are available."""
        required_modules = [
            "paho.mqtt.client",
            "json",
            "logging",
            "pathlib",
            "collections"
        ]
        
        missing_modules = []
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)
        
        if not missing_modules:
            self.log_result("Dependencies", True, "All required Python modules are available")
            return True
        else:
            self.log_result("Dependencies", False, f"Missing modules: {missing_modules}")
            return False
    
    def run_validation(self) -> bool:
        """Run all validation tests."""
        logging.info("Starting Phase 2 validation...")
        
        tests = [
            self.test_dependencies,
            self.test_script_files,
            self.test_telemetry_service_file,
            self.test_systemd_service,
            self.test_mqtt_broker,
            self.test_telemetry_dry_run,
            self.test_telemetry_message_format,
            self.test_log_files
        ]
        
        passed_tests = 0
        for test in tests:
            try:
                if test():
                    passed_tests += 1
            except Exception as exc:
                logging.error("Test failed with exception: %s", exc)
        
        return passed_tests == len(tests)
    
    def print_summary(self) -> None:
        """Print validation summary."""
        print("\n" + "="*60)
        print("PHASE 2 VALIDATION SUMMARY")
        print("="*60)
        
        passed = sum(1 for result in self.results if result["passed"])
        total = len(self.results)
        
        for result in self.results:
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            print(f"{status} {result['test']}: {result['message']}")
        
        print("-"*60)
        print(f"Overall Result: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 Phase 2 validation PASSED! All components are working correctly.")
        else:
            print("⚠️  Phase 2 validation FAILED! Some components need attention.")
            print("\nTroubleshooting tips:")
            for result in self.results:
                if not result["passed"]:
                    print(f"- {result['test']}: {result['message']}")
        
        print("="*60)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Validate Phase 2 telemetry system")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    validator = Phase2Validator(verbose=args.verbose)
    validator.setup_logging()
    
    try:
        success = validator.run_validation()
        validator.print_summary()
        
        if not success:
            sys.exit(1)
            
    except KeyboardInterrupt:
        logging.info("Validation interrupted by user")
        sys.exit(1)
    except Exception as exc:
        logging.exception("Validation failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
