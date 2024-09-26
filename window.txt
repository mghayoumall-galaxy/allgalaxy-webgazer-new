window.onload = async function() {
    const videoElement = document.getElementById('webcamVideo');
    const demoImage = document.getElementById('demoImage');
    const gazeDataDiv = document.getElementById('gazeData');
    const calibrationDiv = document.getElementById('calibrationDiv');
    const calibrationPoints = document.getElementsByClassName('calibrationPoint');
    const cameraSelect = document.getElementById('cameraSelect');
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
    const totalCalibrationSteps = 9;
    let gazeData = [];
    let startTime;

    // Function to show next image
    function showNextImage() {
        if (currentImageIndex < images.length) {
            demoImage.src = images[currentImageIndex++];
            demoImage.style.display = 'block';
            setTimeout(showNextImage, 5000); // Display each image for 5 seconds
        } else {
            endSession(); // End session after the last image
        }
    }

    // Function to initialize WebGazer
    function setupWebGazer() {
        webgazer.setGazeListener(function(data, elapsedTime) {
            if (data) {
                const x = data.x;
                const y = data.y;
                const timestamp = performance.now() - startTime;
                
                // Calculate and store gaze metrics
                gazeData.push({ eyeX: x, eyeY: y, timestamp });

                // Example: Calculate fixation duration (if gaze stays within a threshold area)
                const lastGaze = gazeData[gazeData.length - 2];
                if (lastGaze) {
                    const distance = Math.sqrt(Math.pow(x - lastGaze.eyeX, 2) + Math.pow(y - lastGaze.eyeY, 2));
                    if (distance < 50) { // Assume 50 pixels as a threshold for fixation
                        lastGaze.duration = timestamp - lastGaze.timestamp;
                    }
                }

                gazeDataDiv.innerText = `Gaze coordinates: X ${x}, Y ${y}`;
                console.log(`Gaze coordinates: (${x}, ${y}), Time: ${timestamp}`);
            }
        }).begin();

        webgazer.showVideoPreview(false) // Disable the default video preview
               .showPredictionPoints(true) // Shows where WebGazer is predicting the user is looking
               .applyKalmanFilter(true); // Apply Kalman filter for smoother tracking

        webgazer.setVideoElement(videoElement);
    }

    // Function to setup the camera
    async function setupCamera(deviceId) {
        if (videoElement.srcObject) {
            videoElement.srcObject.getTracks().forEach(track => track.stop());
        }

        const constraints = {
            video: {
                deviceId: deviceId ? { exact: deviceId } : undefined
            }
        };

        navigator.mediaDevices.getUserMedia(constraints)
            .then(stream => {
                videoElement.srcObject = stream;
                videoElement.play();
                console.log('Camera is now active.');
                setupWebGazer(); // Initialize WebGazer after the camera is active
                startTime = performance.now(); // Start timing for data collection
            })
            .catch(error => {
                console.error('Error accessing the camera:', error);
                alert('Unable to access the camera. Please ensure permissions are granted.');
            });
    }

    // Function to show calibration points sequentially
    function showCalibrationPoint() {
        if (calibrationStep < totalCalibrationSteps) {
            const point = calibrationPoints[calibrationStep];
            point.style.visibility = 'visible';
            setTimeout(() => {
                point.style.visibility = 'hidden';
                calibrationStep++;
                showCalibrationPoint();
            }, 2000); // Show each calibration point for 2 seconds
        } else {
            console.log('Calibration complete.');
            calibrationDiv.style.display = 'none';
            showNextImage(); // Start showing images after calibration
        }
    }

    // Function to start calibration
    function startCalibration() {
        calibrationDiv.style.display = 'flex';
        showCalibrationPoint();
    }

    // Function to start eye tracking
    function startEyeTracking() {
        console.log('Eye movement tracking started.');
        showNextImage(); // Begin image sequence
    }

    // Function to end session
    function endSession() {
        webgazer.end(); // Stop WebGazer
        demoImage.style.display = 'none'; // Hide the last image
        gazeDataDiv.innerText = 'Thank you! The session has ended.';
        console.log('Eye movement tracking stopped. Session ended.');

        // Send collected data to the server
        fetch('/save-gaze-data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(gazeData)
        }).then(response => response.text())
          .then(data => console.log(data))
          .catch(error => console.error('Error:', error));
    }

    // Populate the camera select dropdown
    async function getVideoInputs() {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoInputs = devices.filter(device => device.kind === 'videoinput');
        videoInputs.forEach((input, index) => {
            const option = document.createElement('option');
            option.value = input.deviceId;
            option.text = input.label || `Camera ${index + 1}`;
            cameraSelect.appendChild(option);
        });
    }

    cameraSelect.addEventListener('change', () => {
        setupCamera(cameraSelect.value);
    });

    // Ensure the browser supports the required features
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        getVideoInputs().then(() => {
            setupCamera(cameraSelect.value);
        });
    } else {
        console.error('Browser API navigator.mediaDevices.getUserMedia not available');
        alert('Your browser does not support the required features. Try updating or switching browsers.');
    }

    // Start the calibration process
    startCalibration();
};
