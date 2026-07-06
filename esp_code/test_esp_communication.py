"""
Samarth ESP32 Communication Test Script
========================================
Tests the ESP A ↔ ESP B ↔ Website communication loop.

Usage:
    pip install requests
    python test_esp_communication.py --ip 192.168.x.x

    (Replace 192.168.x.x with ESP B's IP from Serial Monitor)

What it tests:
    1. Ping    — GET /status  → Is ESP B alive?
    2. Data    — GET /data    → Are sensors sending telemetry?
    3. Command — POST /exercise → Does ESP A receive commands?
    4. Routes  — Tests all backend-compatible routes
    5. Loop    — Continuous read+command for 10 seconds
"""

import argparse
import time
import sys

try:
    import requests
except ImportError:
    print("❌ 'requests' not installed. Run: pip install requests")
    sys.exit(1)


def print_pass(test_name, detail=""):
    print(f"  ✅ {test_name}{(' — ' + detail) if detail else ''}")


def print_fail(test_name, detail=""):
    print(f"  ❌ {test_name}{(' — ' + detail) if detail else ''}")


def test_ping(base_url):
    """Test 1: Check if ESP B is alive via GET /status"""
    try:
        r = requests.get(f"{base_url}/status", timeout=3)
        if r.status_code == 200:
            data = r.json()
            device = data.get("device_id", "unknown")
            ip = data.get("ip", "?")
            channel = data.get("channel", "?")
            uptime = data.get("uptime_ms", 0) / 1000
            print_pass("Ping ESP B",
                       f"device={device}, ip={ip}, channel={channel}, uptime={uptime:.0f}s")
            return True
        else:
            print_fail("Ping ESP B", f"HTTP {r.status_code}")
            return False
    except requests.ConnectionError:
        print_fail("Ping ESP B", f"Cannot connect to {base_url} — is ESP B powered on and on same WiFi?")
        return False
    except requests.Timeout:
        print_fail("Ping ESP B", "Timeout — ESP B not responding")
        return False
    except Exception as e:
        print_fail("Ping ESP B", str(e))
        return False


def test_read_data(base_url):
    """Test 2: Read sensor telemetry via GET /data"""
    try:
        r = requests.get(f"{base_url}/data", timeout=3)
        if r.status_code == 200:
            data = r.json()
            knee = data.get("knee_angle", 0)
            hip = data.get("hip_angle", 0)
            force = data.get("foot_force", 0)
            stance = data.get("stance", False)
            motors = data.get("motors", "off")
            connected = data.get("connected", False)

            if connected:
                print_pass("Read telemetry",
                           f"knee={knee:.1f}° hip={hip:.1f}° force={force:.1f}N "
                           f"stance={'yes' if stance else 'no'} motors={motors}")
            else:
                print_pass("Read telemetry (ESP A not connected yet)",
                           "ESP B is up but hasn't received data from ESP A. "
                           "Check: ESP A powered on? MACs matched? Same WiFi channel?")
            return True
        else:
            print_fail("Read telemetry", f"HTTP {r.status_code}")
            return False
    except Exception as e:
        print_fail("Read telemetry", str(e))
        return False


def test_read_telemetry_legacy(base_url):
    """Test the legacy /telemetry route still works"""
    try:
        r = requests.get(f"{base_url}/telemetry", timeout=3)
        if r.status_code == 200:
            print_pass("Legacy /telemetry route", "OK")
            return True
        else:
            print_fail("Legacy /telemetry route", f"HTTP {r.status_code}")
            return False
    except Exception as e:
        print_fail("Legacy /telemetry route", str(e))
        return False


def test_send_command(base_url):
    """Test 3: Send a mode command via POST /exercise"""
    payload = {"mode_id": 1, "target_torque": 0.5}
    try:
        r = requests.post(f"{base_url}/exercise", json=payload, timeout=3)
        if r.status_code == 200:
            print_pass("Send command (/exercise)",
                       f"mode_id=1, torque=0.5 → {r.json()}")
            return True
        else:
            print_fail("Send command (/exercise)", f"HTTP {r.status_code}")
            return False
    except Exception as e:
        print_fail("Send command (/exercise)", str(e))
        return False


def test_send_command_backend_route(base_url):
    """Test the /command route (used by backend's RealSensorHub)"""
    payload = {"mode_id": 2, "target_torque": 1.0}
    try:
        r = requests.post(f"{base_url}/command", json=payload, timeout=3)
        if r.status_code == 200:
            print_pass("Send command (/command)", f"mode_id=2, torque=1.0 → {r.json()}")
            return True
        else:
            print_fail("Send command (/command)", f"HTTP {r.status_code}")
            return False
    except Exception as e:
        print_fail("Send command (/command)", str(e))
        return False


def test_calibrate(base_url):
    """Test the /calibrate route"""
    try:
        r = requests.post(f"{base_url}/calibrate", timeout=3)
        if r.status_code == 200:
            data = r.json()
            print_pass("Calibrate", f"status={data.get('calibration_status', '?')}")
            return True
        else:
            print_fail("Calibrate", f"HTTP {r.status_code}")
            return False
    except Exception as e:
        print_fail("Calibrate", str(e))
        return False


def test_stop_motors(base_url):
    """Safety: send mode_id=0 to stop all motors after testing"""
    payload = {"mode_id": 0, "target_torque": 0.0}
    try:
        r = requests.post(f"{base_url}/exercise", json=payload, timeout=3)
        if r.status_code == 200:
            print_pass("Stop motors (mode_id=0)", "Motors safely stopped")
            return True
        else:
            print_fail("Stop motors", f"HTTP {r.status_code}")
            return False
    except Exception as e:
        print_fail("Stop motors", str(e))
        return False


def test_loop(base_url, duration=10):
    """Test 5: Continuous read + command loop for specified duration"""
    print(f"\n  ⏳ Running loop test for {duration} seconds...")
    reads = 0
    commands = 0
    errors = 0
    start = time.time()

    while time.time() - start < duration:
        try:
            # Read telemetry
            r = requests.get(f"{base_url}/data", timeout=2)
            if r.status_code == 200:
                reads += 1
                data = r.json()
                elapsed = time.time() - start
                knee = data.get("knee_angle", 0)
                hip = data.get("hip_angle", 0)
                force = data.get("foot_force", 0)
                print(f"\r    [{elapsed:5.1f}s] knee={knee:6.1f}° hip={hip:6.1f}° "
                      f"force={force:5.2f}N  reads={reads} cmds={commands}", end="")
            else:
                errors += 1
        except Exception:
            errors += 1

        # Send a command every 1 second
        if reads > 0 and reads % 10 == 0:
            try:
                payload = {"mode_id": 1, "target_torque": 0.3}
                r = requests.post(f"{base_url}/exercise", json=payload, timeout=2)
                if r.status_code == 200:
                    commands += 1
            except Exception:
                pass

        time.sleep(0.1)  # ~10 Hz

    # Stop motors after loop test
    try:
        requests.post(f"{base_url}/exercise",
                      json={"mode_id": 0, "target_torque": 0.0}, timeout=2)
    except Exception:
        pass

    print()  # newline after \r
    if errors == 0:
        print_pass("Loop test",
                   f"{reads} reads, {commands} commands in {duration}s, 0 errors")
    elif errors < reads * 0.1:
        print_pass("Loop test (minor errors)",
                   f"{reads} reads, {commands} commands, {errors} errors")
    else:
        print_fail("Loop test",
                   f"{reads} reads, {commands} commands, {errors} errors")

    return errors < reads * 0.1 if reads > 0 else False


def main():
    parser = argparse.ArgumentParser(
        description="Test Samarth ESP32 communication loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python test_esp_communication.py --ip 192.168.43.229
  python test_esp_communication.py --ip 192.168.1.100 --loop-duration 30
        """
    )
    parser.add_argument("--ip", required=True,
                        help="ESP B IP address (from Serial Monitor)")
    parser.add_argument("--port", type=int, default=80,
                        help="HTTP port (default: 80)")
    parser.add_argument("--loop-duration", type=int, default=10,
                        help="Duration of loop test in seconds (default: 10)")
    parser.add_argument("--skip-loop", action="store_true",
                        help="Skip the loop test")
    args = parser.parse_args()

    base_url = f"http://{args.ip}:{args.port}"

    print(f"\n{'='*60}")
    print(f"  Samarth ESP32 Communication Test")
    print(f"  Target: {base_url}")
    print(f"{'='*60}\n")

    results = []

    # Test 1: Ping
    print("📡 Test 1: Ping ESP B")
    passed = test_ping(base_url)
    results.append(("Ping", passed))
    if not passed:
        print("\n⛔ ESP B is not reachable. Cannot continue.")
        print("   Check:")
        print("   • Is ESP B powered on?")
        print("   • Is your laptop on the same WiFi?")
        print("   • Is the IP address correct? (check Serial Monitor)")
        sys.exit(1)

    # Test 2: Read telemetry
    print("\n📊 Test 2: Read sensor data")
    results.append(("Read data", test_read_data(base_url)))
    results.append(("Legacy /telemetry", test_read_telemetry_legacy(base_url)))

    # Test 3: Send commands
    print("\n🎮 Test 3: Send motor commands")
    results.append(("POST /exercise", test_send_command(base_url)))
    results.append(("POST /command", test_send_command_backend_route(base_url)))
    results.append(("POST /calibrate", test_calibrate(base_url)))

    # Safety: stop motors
    print("\n🛑 Safety: Stop motors")
    test_stop_motors(base_url)

    # Test 4: Loop test
    if not args.skip_loop:
        print(f"\n🔄 Test 4: Loop test ({args.loop_duration}s)")
        results.append(("Loop test", test_loop(base_url, args.loop_duration)))

    # Summary
    passed_count = sum(1 for _, p in results if p)
    total = len(results)
    print(f"\n{'='*60}")
    if passed_count == total:
        print(f"  ✅ ALL {total} TESTS PASSED")
    else:
        print(f"  ⚠️  {passed_count}/{total} tests passed")
        for name, passed in results:
            if not passed:
                print(f"     ❌ Failed: {name}")
    print(f"{'='*60}\n")

    # Next steps
    print("📋 Next steps:")
    print(f"   1. Update .env: PS3_ESP_URL=http://{args.ip}")
    print("   2. Start backend: python -m uvicorn main:app --reload")
    print("   3. Open website → start a live session")
    print("   4. Check Serial Monitor for motor commands\n")


if __name__ == "__main__":
    main()
