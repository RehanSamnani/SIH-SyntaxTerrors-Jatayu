## Feature Review — Phase 1: Sensor drivers & single-purpose scripts

Scope reviewed:
- `src/sensors/gps_reader.py`
- `src/sensors/imu_reader.py`
- `src/vision/camera_stream.py`
- `src/actuators/servo_release.py`
- `docs/phase1.md`

Findings:

1) Correctness and requirements
- GPS: Reads `/dev/serial0` @9600, parses GGA/RMC with `pynmea2`, writes JSON to `/home/pi/drone/telemetry/gps_latest.json`, publishes MQTT at `drone/<DEVICE_ID>/gps`. Meets acceptance (1 Hz when fix available) with throttling.
- IMU: Uses I2C (0x68), reads accel/gyro, complementary filter for pitch/roll (alpha=0.98), logs JSONL at ~50 Hz. Acceptance likely met (±2° jitter stationary) pending calibration check.
- Camera: Captures 640x480 and logs FPS, can save snapshot. Acceptance (10–20 FPS) subject to environment load.
- Servo: CLI arm/release/reset via gpiozero, logs actions. External 5V noted in docs.

2) Robustness
- All scripts include try/except and graceful shutdown; GPS has retry for serial/MQTT.
- Suggest adding exponential backoff bounds and persistent offline cache for GPS MQTT (future).

3) Style and structure
- Code is modular, short, and readable. Logging is consistent.
- Minor nit: `servo_release.py` logging line uses an arg guard; could simplify by formatting args directly.

4) Security and safety
- UART reserved for GPS only; docs reinforce disabling serial console.
- Running as unprivileged user is recommended; consider systemd units with `User=`.

5) Tests (next)
- Add unit tests with mocks for serial/I2C/camera/MQTT.
- Integration smoke: run GPS with simulated NMEA, verify JSON & MQTT publish once per second.

Action items:
- Add `.env.example` and config loader to centralize settings.
- Add systemd service examples for each script with proper sandboxing.
- Create unit tests for IMU complementary filter and GPS NMEA parsing.


