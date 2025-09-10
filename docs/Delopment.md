Hardware Setup:
       # Copy environment template
   cp env.example .env
   # Edit .env with your configuration
   
   # Run bootstrap
   bash scripts/bootstrap.sh

Install Services:
   # Install all systemd services
   sudo cp scripts/*.service /etc/systemd/system/
   sudo systemctl daemon-reload
   
   # Enable services
   sudo systemctl enable gps_reader.service
   sudo systemctl enable imu_reader.service
   sudo systemctl enable telemetry.service
   sudo systemctl enable mission_runner.service
   sudo systemctl enable obstacle_detector.service   

Download TFLite Model:
       # Place MobileNet SSD model in models/ directory
   wget -O models/mobilenet_ssd_v1.tflite "https://tfhub.dev/tensorflow/lite-model/ssd_mobilenet_v1/1/metadata/1?lite-format=tflite"

Test System:
      # Test individual components
   python src/sensors/gps_reader.py
   python src/sensors/imu_reader.py
   python src/telemetry_service.py --dry-run
   python src/mission_runner.py --dry-run
   python src/vision/detector.py --drone_id pi01