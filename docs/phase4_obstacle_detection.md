# Phase 4 — Obstacle Detection & Basic Avoidance

## Overview

Phase 4 implements real-time obstacle detection using lightweight AI models on the Raspberry Pi Camera. The system detects objects in the camera feed, estimates their distance, and publishes obstacle events to MQTT for integration with the mission runner's reactive avoidance system.

## Goals

- **Perception**: Detect obstacles in real-time using TFLite MobileNet SSD
- **Performance**: Achieve ≥5 FPS inference on Raspberry Pi 4
- **Integration**: Publish obstacle events to MQTT for mission runner consumption
- **Safety**: Trigger pause/resume logic in mission execution

## Architecture

```
Pi Camera → OpenCV → TFLite Inference → Postprocessing → MQTT → Mission Runner
```

### Components

1. **Camera Capture**: OpenCV VideoCapture with libcamera backend
2. **Model Inference**: TFLite MobileNet SSD with CPU optimization
3. **Postprocessing**: Detection filtering, distance estimation, severity classification
4. **MQTT Publishing**: Obstacle events to `drone/<id>/obstacles`
5. **Mission Integration**: Automatic pause/resume on obstacle detection

## Implementation Details

### Core Files

- `src/vision/detector.py` - Main obstacle detection service
- `models/mobilenet_ssd_v1.tflite` - TFLite MobileNet SSD model
- `models/coco_labels.txt` - Object class labels (optional)

### Key Features

#### Performance Optimization
- **Frame Resize**: Reduces input from camera resolution to 300x300 pixels
- **Frame Skipping**: Processes every Nth frame (default: every 2nd frame)
- **Top-K Filtering**: Limits detections to highest confidence results
- **Efficient Preprocessing**: Minimal memory allocations and conversions

#### Distance Estimation
- **Heuristic Formula**: `distance ≈ k / (bbox_h_px / frame_h_px)`
- **Configurable Constant**: `distance_k` parameter (default: 40.0)
- **Calibration Required**: Must be tuned for specific camera and object types

#### Severity Classification
- **Critical**: Distance < 5 meters
- **Warning**: Distance < 15 meters OR confidence ≥ 0.6
- **Info**: All other detections

### MQTT Message Format

```json
{
  "timestamp_ms": 1703123456789,
  "drone_id": "pi01",
  "event": "obstacle",
  "label": "person",
  "confidence": 0.85,
  "bbox": {
    "x": 100,
    "y": 120,
    "w": 80,
    "h": 160
  },
  "severity": "warning",
  "distance_m": 8.5
}
```

## Configuration

### Environment Variables

```bash
# MQTT Configuration
DRONE_ID=pi01
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_USERNAME=your_username
MQTT_PASSWORD=your_password

# Model Configuration
MODEL_PATH=models/mobilenet_ssd_v1.tflite
LABELS_PATH=models/coco_labels.txt
CONF_THRESHOLD=0.5
TOP_K=20
SKIP_FRAMES=2
DIST_K=40.0

# Camera Configuration
CAM_W=640
CAM_H=480
CAM_FPS=15
MODEL_W=300
MODEL_H=300
```

### Command Line Options

```bash
python src/vision/detector.py \
  --drone_id pi01 \
  --mqtt_host localhost \
  --mqtt_port 1883 \
  --model_path models/mobilenet_ssd_v1.tflite \
  --conf_threshold 0.5 \
  --skip_frames 2 \
  --distance_k 40.0 \
  --cam_width 640 \
  --cam_height 480 \
  --model_width 300 \
  --model_height 300 \
  --verbose
```

## Model Requirements

### TFLite MobileNet SSD

The detector expects a TFLite model with the following characteristics:

- **Input**: [1, 300, 300, 3] RGB image (uint8 or float32)
- **Outputs**: 
  - Boxes: [1, num_detections, 4] (ymin, xmin, ymax, xmax) normalized
  - Classes: [1, num_detections] (class indices)
  - Scores: [1, num_detections] (confidence scores)
  - Num detections: [1] (number of valid detections)

### Model Sources

1. **TensorFlow Hub**: Pre-trained MobileNet SSD models
2. **TensorFlow Model Zoo**: COCO-trained models
3. **Custom Training**: Train on specific obstacle types

### Model Conversion

```bash
# Convert TensorFlow model to TFLite
tflite_convert \
  --saved_model_dir=path/to/saved_model \
  --output_file=models/mobilenet_ssd_v1.tflite \
  --optimizations=default \
  --quantize_weights
```

## Performance Tuning

### Frame Rate Optimization

1. **Reduce Input Size**: Use 224x224 or 192x192 for higher FPS
2. **Increase Frame Skipping**: Set `--skip_frames 3` or higher
3. **Lower Camera Resolution**: Use 320x240 instead of 640x480
4. **Reduce Top-K**: Limit to 10-15 detections instead of 20

### Memory Optimization

1. **Model Quantization**: Use INT8 quantized models
2. **Frame Buffer Management**: Avoid storing multiple frames
3. **Garbage Collection**: Monitor memory usage during long runs

### System Optimization

1. **CPU Governor**: Set to performance mode
2. **Thermal Management**: Use heatsinks and fans
3. **Background Processes**: Minimize other running services

## Integration with Mission Runner

### Obstacle Handling Flow

1. **Detection**: Detector publishes obstacle event to MQTT
2. **Consumption**: Mission runner receives event on `drone/<id>/obstacles`
3. **Evaluation**: Checks confidence threshold (default: 0.7)
4. **Response**: Transitions to PAUSED state if obstacle detected
5. **Recovery**: Resumes mission when obstacle clears

### State Machine Integration

```
ENROUTE/HOLD → [Obstacle Detected] → PAUSED → [Obstacle Cleared] → ENROUTE/HOLD
```

### Configuration

Mission runner obstacle handling is configured in `src/mission_runner.py`:

```python
# Only react to high-confidence obstacles
if confidence > 0.7:
    logging.warning("Obstacle detected: %s (confidence: %.2f)", obstacle_type, confidence)
    self.obstacle_detected = True
    self._pause_mission()
```

## Testing and Validation

### Unit Testing

```bash
# Test model loading and inference
python -m pytest tests/unit/test_detector.py

# Test MQTT publishing
python -m pytest tests/unit/test_mqtt_integration.py
```

### Integration Testing

```bash
# End-to-end test with mock camera
python tests/integration/test_detector_integration.py

# Performance benchmark
python tests/integration/test_performance.py
```

### Manual Testing

1. **Camera Test**: Verify camera access and frame capture
2. **Model Test**: Load model and run inference on sample images
3. **MQTT Test**: Publish test obstacle events and verify reception
4. **Integration Test**: Run detector with mission runner

## Troubleshooting

### Common Issues

#### Camera Access Denied
```bash
# Add user to video group
sudo usermod -a -G video $USER
# Reboot or logout/login
```

#### Model Loading Failed
```bash
# Check model file exists and is readable
ls -la models/mobilenet_ssd_v1.tflite
# Verify TFLite runtime is installed
python -c "import tflite_runtime.interpreter"
```

#### Low Frame Rate
```bash
# Check CPU usage and temperature
htop
vcgencmd measure_temp
# Reduce model input size
python src/vision/detector.py --model_width 224 --model_height 224
```

#### MQTT Connection Failed
```bash
# Check broker is running
systemctl status mosquitto
# Test connection
mosquitto_pub -h localhost -t test -m "hello"
```

### Performance Monitoring

```bash
# Monitor FPS output in detector logs
tail -f /var/log/detector.log | grep "FPS:"

# Monitor MQTT messages
mosquitto_sub -h localhost -t "drone/+/obstacles" -v

# Monitor system resources
htop
iostat 1
```

## Security Considerations

### Model Security
- **Integrity**: Verify model file checksums
- **Source**: Use trusted model sources
- **Updates**: Implement secure model update mechanism

### MQTT Security
- **Authentication**: Use username/password or certificates
- **TLS**: Enable TLS for encrypted communication
- **ACLs**: Restrict topic access per client

### System Security
- **User Permissions**: Run detector as non-root user
- **File Access**: Restrict model and log file permissions
- **Network**: Use firewall rules for MQTT ports

## Future Enhancements

### Short Term
1. **MQTT Reconnection**: Automatic reconnection on broker failure
2. **Model Validation**: Checksum verification for model files
3. **Performance Metrics**: Detailed FPS and latency reporting
4. **Calibration Tools**: GUI for distance estimation calibration

### Medium Term
1. **Stereo Depth**: Add stereo camera support for accurate distance
2. **Multi-Model**: Support for different model architectures
3. **Edge Cases**: Handle low-light and adverse weather conditions
4. **Confidence Filtering**: Adaptive confidence thresholds

### Long Term
1. **Custom Training**: Train models on specific obstacle types
2. **Real-time Learning**: Online model adaptation
3. **3D Detection**: Full 3D object detection and tracking
4. **Predictive Avoidance**: Path planning with obstacle prediction

## Dependencies

### Required Packages
```
tflite-runtime==2.12.0
opencv-python==4.9.0.80
numpy==1.26.4
paho-mqtt==1.6.1
```

### System Requirements
- Raspberry Pi 4 (4GB RAM recommended)
- Pi Camera Module
- MQTT broker (Mosquitto)
- TFLite model file

### Optional Dependencies
```
tensorflow==2.12.0  # For model conversion and development
matplotlib==3.7.1   # For visualization and debugging
```

## References

- [TensorFlow Lite Documentation](https://www.tensorflow.org/lite)
- [MobileNet SSD Paper](https://arxiv.org/abs/1704.04861)
- [OpenCV Python Documentation](https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html)
- [MQTT Protocol Specification](https://mqtt.org/mqtt-specification/)
- [Raspberry Pi Camera Documentation](https://www.raspberrypi.org/documentation/usage/camera/)
