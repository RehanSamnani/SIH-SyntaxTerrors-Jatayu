# Phase 4 Quickstart — Obstacle Detection

Get obstacle detection running in 5 minutes with this quickstart guide.

## Prerequisites

- Phase 0-3 completed (Pi setup, sensors, telemetry, mission runner)
- Pi Camera connected and enabled
- MQTT broker running
- TFLite model file available

## Quick Setup

### 1. Download TFLite Model

```bash
# Create models directory
mkdir -p models

# Download a pre-trained MobileNet SSD model
# Option 1: Use TensorFlow Hub model
wget -O models/mobilenet_ssd_v1.tflite \
  "https://tfhub.dev/tensorflow/lite-model/ssd_mobilenet_v1/1/metadata/1?lite-format=tflite"

# Option 2: Use COCO-trained model from TensorFlow Model Zoo
# (Download and convert from TensorFlow SavedModel)
```

### 2. Test Camera Access

```bash
# Test camera with existing camera_stream.py
python src/vision/camera_stream.py --width 640 --height 480 --fps 15

# Should show FPS output. Press Ctrl+C to stop.
```

### 3. Start MQTT Broker

```bash
# Use existing setup script
bash scripts/setup_mqtt_broker.sh

# Verify broker is running
systemctl status mosquitto
```

### 4. Run Obstacle Detector

```bash
# Basic run with default settings
python src/vision/detector.py --drone_id pi01

# With custom settings for better performance
python src/vision/detector.py \
  --drone_id pi01 \
  --skip_frames 2 \
  --conf_threshold 0.5 \
  --model_width 300 \
  --model_height 300 \
  --verbose
```

### 5. Monitor Obstacle Events

```bash
# In another terminal, monitor MQTT obstacle events
mosquitto_sub -h localhost -p 1883 -t "drone/+/obstacles" -v

# Should show obstacle detection events when objects are detected
```

## Expected Output

### Detector Console Output
```
2024-01-15 10:30:15 [INFO] Starting detector for drone_id=pi01, MQTT localhost:1883, model=models/mobilenet_ssd_v1.tflite
2024-01-15 10:30:16 [INFO] FPS: 7
[warning] person 0.85 bbox=(100,120,80,160), 8.5m
[critical] car 0.92 bbox=(200,150,120,80), 3.2m
2024-01-15 10:30:17 [INFO] FPS: 7
```

### MQTT Obstacle Events
```
drone/pi01/obstacles {"timestamp_ms":1705312215000,"drone_id":"pi01","event":"obstacle","label":"person","confidence":0.85,"bbox":{"x":100,"y":120,"w":80,"h":160},"severity":"warning","distance_m":8.5}
```

## Integration Test

### Test with Mission Runner

```bash
# Terminal 1: Start mission runner
python src/mission_runner.py --dry-run

# Terminal 2: Start obstacle detector
python src/vision/detector.py --drone_id pi01

# Terminal 3: Monitor mission status
mosquitto_sub -h localhost -p 1883 -t "drone/+/mission/status" -v

# Terminal 4: Send test mission command
mosquitto_pub -h localhost -p 1883 -t "drone/pi01/mission/command" \
  -m '{"type":"start","mission_id":"sample_mission"}'
```

### Expected Behavior
1. Mission runner starts mission and transitions to ENROUTE
2. When obstacle is detected, mission runner pauses (state: PAUSED)
3. When obstacle clears, mission runner resumes (state: ENROUTE)

## Performance Tuning

### For Higher FPS

```bash
# Reduce model input size
python src/vision/detector.py \
  --model_width 224 \
  --model_height 224 \
  --skip_frames 3

# Reduce camera resolution
python src/vision/detector.py \
  --cam_width 320 \
  --cam_height 240 \
  --model_width 224 \
  --model_height 224
```

### For Better Accuracy

```bash
# Increase confidence threshold
python src/vision/detector.py \
  --conf_threshold 0.7 \
  --skip_frames 1

# Use higher camera resolution
python src/vision/detector.py \
  --cam_width 640 \
  --cam_height 480 \
  --model_width 300 \
  --model_height 300
```

## Troubleshooting

### Camera Issues
```bash
# Check camera is enabled
sudo raspi-config
# Interface Options → Camera → Enable

# Check camera access
ls /dev/video*
# Should show /dev/video0

# Test with camera_stream.py
python src/vision/camera_stream.py --width 320 --height 240
```

### Model Issues
```bash
# Check model file exists
ls -la models/mobilenet_ssd_v1.tflite

# Test model loading
python -c "
from tflite_runtime.interpreter import Interpreter
interpreter = Interpreter(model_path='models/mobilenet_ssd_v1.tflite')
print('Model loaded successfully')
"
```

### MQTT Issues
```bash
# Check broker status
systemctl status mosquitto

# Test MQTT connection
mosquitto_pub -h localhost -t test -m "hello"
mosquitto_sub -h localhost -t test
```

### Performance Issues
```bash
# Check CPU temperature
vcgencmd measure_temp

# Check CPU usage
htop

# Check memory usage
free -h

# Reduce load
python src/vision/detector.py --skip_frames 4 --model_width 224
```

## Next Steps

1. **Calibrate Distance Estimation**: Place known objects at known distances and adjust `--distance_k`
2. **Test with Real Obstacles**: Use people, vehicles, and other objects
3. **Integrate with Mission Runner**: Test pause/resume behavior
4. **Monitor Performance**: Check FPS and system resources
5. **Tune Parameters**: Adjust confidence thresholds and frame skipping

## Configuration Examples

### Development Mode (High FPS)
```bash
python src/vision/detector.py \
  --drone_id pi01 \
  --cam_width 320 \
  --cam_height 240 \
  --model_width 224 \
  --model_height 224 \
  --skip_frames 2 \
  --conf_threshold 0.3 \
  --verbose
```

### Production Mode (Balanced)
```bash
python src/vision/detector.py \
  --drone_id pi01 \
  --cam_width 640 \
  --cam_height 480 \
  --model_width 300 \
  --model_height 300 \
  --skip_frames 2 \
  --conf_threshold 0.5 \
  --distance_k 40.0
```

### High Accuracy Mode (Lower FPS)
```bash
python src/vision/detector.py \
  --drone_id pi01 \
  --cam_width 640 \
  --cam_height 480 \
  --model_width 300 \
  --model_height 300 \
  --skip_frames 1 \
  --conf_threshold 0.7 \
  --top_k 10
```

## Environment Variables

Create `.env` file for persistent configuration:

```bash
# .env
DRONE_ID=pi01
MQTT_HOST=localhost
MQTT_PORT=1883
MODEL_PATH=models/mobilenet_ssd_v1.tflite
CONF_THRESHOLD=0.5
SKIP_FRAMES=2
DIST_K=40.0
CAM_W=640
CAM_H=480
MODEL_W=300
MODEL_H=300
```

Then run:
```bash
python src/vision/detector.py
```

## Success Criteria

✅ **Camera Access**: FPS output shows 5+ FPS  
✅ **Model Loading**: No errors during model initialization  
✅ **MQTT Connection**: Connected to broker successfully  
✅ **Obstacle Detection**: Events published when objects detected  
✅ **Mission Integration**: Mission runner pauses on obstacles  
✅ **Performance**: Sustained 5+ FPS inference rate  

If all criteria are met, Phase 4 obstacle detection is working correctly!
