window.onload = function() {
    const path = window.location.pathname;

    if (path.endsWith("gaze.html")) {
        console.log('Welcome page loaded');
    } else if (path.endsWith("gaze1.html")) {
        console.log('User information page loaded');
        document.getElementById('userInfoForm').addEventListener('submit', function(event) {
            event.preventDefault();
            const age = document.getElementById('age').value;
            const healthCondition = document.getElementById('healthCondition').value.toLowerCase();

            if (age < 50 || healthCondition.includes('cataracts') || healthCondition.includes('glaucoma')) {
                document.getElementById('eligibilityMessage').innerText = 'Unfortunately, you are not eligible for this study.';
            } else {
                window.location.href = 'gaze3.html';
            }
        });
    } else if (path.endsWith("gaze3.html")) {
        console.log('Eye movement data collection page loaded');

        const videoElement = document.getElementById('webcamVideo');
        const demoImage = document.getElementById('demoImage');
        const gazeDataDiv = document.getElementById('gazeData');
        const calibrationDiv = document.getElementById('calibrationDiv');
        const calibrationPoints = document.getElementsByClassName('calibrationPoint');
        const cameraSelect = document.getElementById('cameraSelect');
        const errorMessage = document.getElementById('errorMessage');
        const startCalibrationButton = document.getElementById('startCalibrationButton');
        const trackingInfo = document.getElementById('tracking-info');
        const images = [
            'images/image1.jpg',
            'images/image2.jpg',
            'images/image3.jpg',
            'images/image4.jpg',
            'images/image5.jpg',
            'images/image6.jpg',
            'images/image7.jpg',
            'images/image8.jpg',
            'images/image9.jpg',
            'images/image10.jpg'
        ];

        let currentImageIndex = 0;
        let calibrationStep = 0;
        const totalCalibrationSteps = calibrationPoints.length;
        let gazeData = [];
        let calibrationData = [];
        let startTime;

        const dynamicThreshold = Math.min(window.innerWidth, window.innerHeight) * 0.05;

        function showNextImage() {
            if (currentImageIndex < images.length) {
                demoImage.src = images[currentImageIndex++];
                demoImage.style.display = 'block';
                setTimeout(showNextImage, 5000);
            } else {
                endSession();
            }
        }

        function setupWebGazer() {
            webgazer.setGazeListener((data) => {
                if (data) {
                    const { x, y } = data;
                    const timestamp = performance.now() - startTime;

                    gazeData.push({ eyeX: x, eyeY: y, timestamp });

                    const lastGaze = gazeData[gazeData.length - 2];
                    if (lastGaze) {
                        const distance = Math.hypot(x - lastGaze.eyeX, y - lastGaze.eyeY);
                        if (distance < 50) {
                            lastGaze.duration = timestamp - lastGaze.timestamp;
                        }
                    }

                    gazeDataDiv.innerText = `Gaze coordinates: X ${x}, Y ${y}`;
                    console.log(`Gaze coordinates: (${x}, ${y}), Time: ${timestamp}`);
                }
            }).begin();

            webgazer.showVideoPreview(false)
                   .showPredictionPoints(true)
                   .applyKalmanFilter(true);

            webgazer.setVideoElement(videoElement);
        }

        async function setupCamera(deviceId) {
            if (videoElement.srcObject) {
                videoElement.srcObject.getTracks().forEach(track => track.stop());
            }

            try {
                const constraints = {
                    video: { deviceId: deviceId ? { exact: deviceId } : undefined }
                };

                const stream = await navigator.mediaDevices.getUserMedia(constraints);
                videoElement.srcObject = stream;
                videoElement.play();
                console.log('Camera is now active.');
                setupWebGazer();
                startTime = performance.now();
            } catch (error) {
                console.error('Error accessing the camera:', error);
                errorMessage.innerText = 'Unable to access the camera. Please ensure permissions are granted.';
                errorMessage.style.display = 'block';
            }
        }

        function showCalibrationPoint() {
            if (calibrationStep < totalCalibrationSteps) {
                const point = calibrationPoints[calibrationStep];
                point.style.visibility = 'visible';

                webgazer.setGazeListener((data) => {
                    if (data) {
                        calibrationData.push({ 
                            eyeX: data.x, 
                            eyeY: data.y, 
                            targetX: point.getBoundingClientRect().left + point.offsetWidth / 2,
                            targetY: point.getBoundingClientRect().top + point.offsetHeight / 2
                        });
                    }
                });

                setTimeout(() => {
                    point.style.visibility = 'hidden';
                    calibrationStep++;
                    showCalibrationPoint();
                }, 2000);
            } else {
                console.log('Calibration complete.');
                calibrationDiv.style.display = 'none';
                verifyCalibration(calibrationData);
                trackingInfo.style.display = 'block';
                showNextImage();
            }
        }

        function verifyCalibration(data) {
            let calibrationErrors = [];
            data.forEach(point => {
                const distance = Math.hypot(point.eyeX - point.targetX, point.eyeY - point.targetY);
                calibrationErrors.push(distance);
            });

            const averageError = calibrationErrors.reduce((acc, val) => acc + val, 0) / calibrationErrors.length;
            console.log(`Average calibration error: ${averageError}px`);

            if (averageError > dynamicThreshold) {
                console.log('Calibration is not accurate enough. Please recalibrate.');
                alert('Calibration accuracy is low. Consider recalibrating.');
            } else {
                console.log('Calibration is accurate.');
            }
        }

        function endSession() {
            webgazer.end();
            demoImage.style.display = 'none';
            gazeDataDiv.innerText = 'Thank you! The session has ended.';
            console.log('Eye movement tracking stopped. Session ended.');

            const expectedTargetPositions = images.map((img, index) => {
                return {
                    x: window.innerWidth / 2,
                    y: window.innerHeight / 2
                };
            });
            verifyEyeMovement(expectedTargetPositions);

            fetch('/save-gaze-data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(gazeData)
            }).then(response => response.text())
              .then(data => console.log(data))
              .catch(error => console.error('Error:', error));
        }

        async function populateCameraSelect() {
            try {
                const devices = await navigator.mediaDevices.enumerateDevices();
                const videoInputs = devices.filter(device => device.kind === 'videoinput');

                cameraSelect.innerHTML = '';
                videoInputs.forEach((input, index) => {
                    const option = document.createElement('option');
                    option.value = input.deviceId;
                    option.text = input.label || `Camera ${index + 1}`;
                    cameraSelect.appendChild(option);
                });

                if (videoInputs.length > 0) {
                    setupCamera(videoInputs[0].deviceId);
                } else {
                    errorMessage.innerText = 'No cameras found. Please connect a camera and try again.';
                    errorMessage.style.display = 'block';
                }
            } catch (error) {
                console.error('Error fetching video input devices:', error);
                errorMessage.innerText = 'Error fetching video input devices. Please try again.';
                errorMessage.style.display = 'block';
            }
        }

        cameraSelect.addEventListener('change', () => {
            setupCamera(cameraSelect.value);
        });

        startCalibrationButton.addEventListener('click', () => {
            calibrationDiv.style.display = 'flex';
            startCalibration();
        });

        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            populateCameraSelect();
        } else {
            console.error('Browser API navigator.mediaDevices.getUserMedia not available');
            errorMessage.innerText = 'Your browser does not support the required features. Try updating or switching browsers.';
            errorMessage.style.display = 'block';
        }
    }
};
