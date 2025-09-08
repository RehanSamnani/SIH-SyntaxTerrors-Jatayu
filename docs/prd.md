📄 Product Requirements Document (PRD)

Project: AI-Enabled Drone Companion System for Disaster Relief
Version: 1.0
Date: 08-09-2025
Author: [Your Name]

1. Problem Statement

During natural disasters (floods, earthquakes, landslides), road networks often become unusable. Delivering medical supplies and communication devices to affected regions is critical but difficult.
Drones can bypass blocked roads, but need AI-driven autonomy to navigate safely and mission coordination software for disaster teams.

Currently, you have essential components (Raspberry Pi 4, GPS, IMU, Camera, Servo, etc.) that can be used to build a prototype companion system — the brain of the drone. This system will be extended later into a full-scale autonomous drone with a Pixhawk flight controller and heavy-lift frame.

2. Objectives

Develop a prototype AI-enabled drone companion system using available hardware.

Demonstrate:

GPS + IMU telemetry capture

Camera-based obstacle detection (AI model)

Servo-controlled payload release simulation

Mission simulation (waypoints + telemetry updates)

Provide an interface to connect with backend (FastAPI + MQTT) for mission tracking.

Design system for future integration with Pixhawk + ArduPilot.

3. Target Users

Disaster response teams (paramedics, NGOs, emergency agencies).

Drone operators (mission setup, monitoring).

Researchers/engineers (testing AI models for drone autonomy).

4. User Needs

Mission creation & monitoring: Define drop points, monitor progress, confirm delivery.

Real-time telemetry: Position, heading, battery, status.

Obstacle avoidance: AI detection of hazards in path.

Payload release: Servo-driven drop mechanism simulation.

Scalability & safety: Must evolve into a full drone fleet system with security controls.

5. Product Scope

In-scope (prototype with current hardware):

Raspberry Pi companion system.

GPS + IMU + Camera + Servo integration.

AI obstacle detection (light model like MobileNet SSD / Tiny YOLO).

Local mission simulator.

MQTT/FastAPI-based backend for telemetry and mission data.

Future scope (full drone integration):

Pixhawk autopilot with ArduPilot/PX4 firmware.

Heavy-lift drone (≥5 kg payload).

Multi-drone coordination + swarm management.

Cold-chain payloads (vaccines, blood).

BVLOS compliance and national UTM integration.

6. Functional Requirements

Telemetry Capture

Read GPS data (lat/lon/time).

Read IMU (acceleration, gyro).

Store & publish telemetry logs.

AI Perception

Capture video feed from Pi Camera.

Run real-time object detection.

Publish obstacle events (MQTT).

Mission Execution

Load mission JSON (waypoints).

Simulate drone motion.

Pause/replan on obstacle event.

Payload Release

Servo control (release/reset).

Log proof of delivery action.

Backend Integration

Expose telemetry via FastAPI/MQTT.

Support mission upload & retrieval.

Store delivery confirmation.

7. Non-Functional Requirements

Performance: Obstacle detection ≥5 FPS on Pi 4.

Security: TLS for backend; JWT authentication; SSH key login on Pi.

Reliability: System should gracefully handle GPS loss, low FPS, or sensor disconnect.

Usability: Simple CLI + app interface; logs must be human-readable.

Scalability: Extendable to multi-drone architecture.

8. System Architecture (Prototype)

Components:

Raspberry Pi 4 (companion computer)

NEO-6M GPS (navigation input)

MPU-6050 IMU (motion sensing)

Pi Camera (vision input)

Micro Servo (payload release simulation)

FastAPI backend + MQTT broker

Workflow:

Mission uploaded via backend → sent to Pi.

Pi reads GPS/IMU data → logs & publishes telemetry.

Pi Camera runs AI → if obstacle, trigger pause/replan.

Mission runner executes waypoints → triggers servo for delivery.

Backend updates mission status & stores proof.

9. Tech Stack

Hardware: Raspberry Pi 4, NEO-6M GPS, MPU-6050 IMU, Pi Camera, Servo motor.

Software: Python 3, OpenCV, TensorFlow Lite / PyTorch (YOLO/MobileNet), FastAPI, PostgreSQL/PostGIS, Mosquitto MQTT.
Database: Supabase (Postgres) for missions, telemetry, and user data. Offline-first mode with local SQLite on Raspberry Pi; sync to Supabase when network available.

Simulation: Mission runner in Python (later → AirSim/Gazebo).

Security: SSH hardening, JWT auth, TLS for backend, MQTT authentication.

10. Success Metrics

GPS logging rate ≥ 1 Hz.

IMU logging rate ≥ 50 Hz.

AI obstacle detection ≥ 5 FPS.

Mission simulation with ≥90% successful waypoint completion.

Servo release test ≥ 95% reliability.

Backend mission tracking & telemetry available with <1s latency.

11. Risks & Mitigation

Pi overheating → use heatsinks/fan.

Low inference speed → use lighter models or frame skipping.

Servo overcurrent → external power supply.

GPS indoors unreliable → simulate or test outdoors.

Security threats → enforce TLS, access control, firewall rules.

12. Testing & QA

Unit tests: GPS, IMU, Camera, Servo scripts.

Integration tests: Mission runner + detector.

Load tests: Telemetry publishing over MQTT.

Simulation tests: Obstacle injection → confirm replan.

Security tests: Attempt fake MQTT client → must be rejected.

13. Future Enhancements

Connect to Pixhawk + ArduPilot SITL → real flight missions.

Multi-drone coordination backend.

Advanced obstacle avoidance (SLAM, LiDAR).

Cold-chain payload box with temperature sensor.

Integration with disaster response dashboards (GIS layers, live maps).