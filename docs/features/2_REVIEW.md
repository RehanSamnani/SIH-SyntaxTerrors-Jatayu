# Phase 2 — Telemetry Aggregator & Local Messaging: Code Review

Scope reviewed:
- `src/telemetry_service.py`
- `scripts/setup_mqtt_broker.sh`, `scripts/install_telemetry_service.sh`, `scripts/telemetry.service`
- `scripts/test_telemetry.py`, `scripts/monitor_telemetry.py`, `scripts/validate_phase2.py`
- `docs/phase2_telemetry.md`, `docs/phase2_quickstart.md`

Summary
- The plan was implemented correctly: a 1 Hz telemetry aggregator consumes GPS/IMU via MQTT (or simulates via `--dry-run`), publishes to `drone/<id>/telemetry`, and writes rotating logs (last ~500 packets, size-capped). A local Mosquitto setup script and a systemd unit are provided. Test and monitor scripts validate end-to-end behavior.

Strengths
- Modularity: Aggregation is isolated in `TelemetryAggregator`; logging/rotation in `RotatingLogWriter`.
- Robustness: Graceful shutdown, MQTT reconnect with retries, QoS 1, bounded log size.
- Operability: Systemd unit with security hardening and resource limits; quickstart and troubleshooting docs.
- DX/Testing: CLI flags (`--dry-run`, `--log-level`), validation and monitoring scripts, broker setup helper.
- Security options: MQTT auth/TLS supported by setup script; service runs non-root with restricted write paths.

Correctness & Data Alignment
- Telemetry packet fields meet acceptance criteria: timestamp, GPS lat/lon/alt (if available), IMU pitch/roll, battery estimate.
- Timestamps: both numeric `timestamp` and ISO `timestamp_iso` included.
- Topic scheme aligns with plan: `drone/<device_id>/telemetry` (and sensor topics `drone/<id>/gps`, `drone/<id>/imu`).
- JSON shapes are flat where needed; nested groups under `battery`, `camera`, `gps`, `imu` are consistent.

Potential Issues / Risks
1) IMU ingestion path:
   - `telemetry_service.py` subscribes to `drone/<id>/imu` but current `src/sensors/imu_reader.py` writes to a file only and does not publish to MQTT. Without a publisher, live IMU won’t reach the aggregator (except in `--dry-run`).
   - Recommendation: add MQTT publishing in `imu_reader.py` mirroring `gps_reader.py` (qos=1, `drone/<id>/imu`).

2) GPS payload variance:
   - `gps_reader.py` emits raw parsed NMEA fields (`type`, `lat`, `lon`, `alt`, etc.). Telemetry service expects the same, which is fine. If `RMC` arrives, telemetry still accepts but may lack `alt`. This is acceptable; `alt` is optional.

3) Battery estimation:
   - Currently simulated/time-based. If later wired to ADC, interface should remain the same (`battery.voltage`, `battery.percentage`) to avoid consumer breakage.

4) Logging duplication:
   - `telemetry_service.py` writes two logs: JSONL telemetry at `/home/pi/drone/telemetry/telemetry.log` (custom rotation) and service log via `RotatingFileHandler` at `/home/pi/drone/logs/telemetry_service.log` (system rotation). This is intentional but should be documented (it is) to avoid confusion.

5) Windows dev caveat:
   - `chmod` step fails on Windows shells (as observed). Docs mention Pi as the target; recommend noting that scripts are intended to run on Pi (Linux). This is mostly covered.

6) MQTT auth/TLS defaults:
   - Broker setup defaults to anonymous access. Safe for dev, but production guidance should emphasize enabling auth/TLS and topic ACLs.

7) Telemetry rate control:
   - Loop sleeps `0.1s` and publishes when `now - last >= interval`. Under heavy load, drift is possible but acceptable for 1 Hz.

8) Camera status:
   - Currently simulated. If later integrated with camera process, keep the shape stable.

Style/Readability
- Code is well-structured, uses descriptive names, and avoids deep nesting.
- Logging is consistent and informative; levels are appropriate.
- Type hints present where helpful; optionality handled.

Performance
- Bounded deque plus append-only JSONL is Pi-friendly.
- MQTT QoS 1 with small payloads is fine for 1 Hz.
- Systemd memory and CPU limits protect the system.

Security
- Non-root service, restricted `ReadWritePaths`, optional TLS/auth for MQTT.
- Recommend adding explicit broker ACL example for production.

Actionable Recommendations
1) Publish IMU to MQTT:
   - Extend `src/sensors/imu_reader.py` to publish messages to `drone/<DEVICE_ID>/imu` with QoS 1 at ~10–50 Hz (or downsample to 1–5 Hz), or add a lightweight `imu_publisher.py`.

2) Broker ACLs (production hardening):
   - Provide example `/etc/mosquitto/conf.d/acl` limiting clients to their device topics.

3) Health metrics hook (optional):
   - Consider adding `uptime_sec` and `seq` fields to telemetry for easier monitoring.

4) Clock sync note:
   - Add doc note to ensure NTP is enabled on Pi for accurate timestamps.

5) Tests:
   - Add a pytest unit for `RotatingLogWriter._should_rotate` and `create_telemetry_packet` shape validation.

Verdict
- Implementation meets Phase 2 acceptance criteria with good robustness and documentation. Addressing the IMU publisher gap will complete real-sensor integration.


