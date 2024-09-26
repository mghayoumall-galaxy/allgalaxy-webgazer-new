document.addEventListener('DOMContentLoaded', async function() {
    const videoElement = document.getElementById('webcamVideo');
    const demoImage = document.getElementById('demoImage');
    const gazeDataDiv = document.getElementById('gazeData');
    const calibrationDiv = document.getElementById('calibrationDiv');
    const calibrationPoints = document.getElementsByClassName('calibrationPoint');
    const cameraSelect = document.getElementById('cameraSelect');
    const startCalibrationButton = document.getElementById('startCalibrationButton');
    const calibrationCompleteMessage = document.getElementById('calibrationCompleteMessage');
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
    const totalCalibrationSteps = 9;
    let calibrationComplete = false;

    // Diagnostic logs
    console.log('cameraSelect element:', cameraSelect);
    console.log('startCalibrationButton element:', startCalibrationButton);

    function showNextImage() {
        if (calibrationComplete && currentImageIndex < images.length) {
            demoImage.src = images[currentImageIndex++];
            demoImage.style.display = 'block';
            setTimeout(showNextImage, 5000);
        } else if (calibrationComplete) {
            console.log('Image display complete. Gaze data collection finished.');
            currentImageIndex = 0;
            showNextImage();
        }
    }

    function setupWebGazer() {
        webgazer.setGazeListener(function(data, elapsedTime) {
            if (data) {
                const x = data.x;
                const y = data.y;
                gazeDataDiv.innerText = `Gaze coordinates: X ${x}, Y ${y}`;
                console.log(`Gaze coordinates: (${x}, ${y})`);
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
                videoElement.style.display = 'block';
                trackingInfo.style.display = 'block';
                setupWebGazer();
                detectFace();
            })
            .catch(error => {
                console.error('Error accessing the camera:', error);
                alert('Unable to access the camera. Please ensure permissions are granted.');
            });
    }

    function showCalibrationPoint() {
        if (calibrationStep < totalCalibrationSteps) {
            const point = calibrationPoints[calibrationStep];
            point.style.visibility = 'visible';
            setTimeout(() => {
                point.style.visibility = 'hidden';
                calibrationStep++;
                showCalibrationPoint();
            }, 2000);
        } else {
            console.log('Calibration complete.');
            calibrationDiv.style.display = 'none';
            calibrationComplete = true;
            calibrationCompleteMessage.style.display = 'block';
            gazeDataDiv.innerText = 'Calibration complete. Starting gaze data collection...';
            setTimeout(() => {
                calibrationCompleteMessage.style.display = 'none';
                showNextImage();
            }, 2000);
        }
    }

    function startCalibration() {
        console.log('Starting calibration...');
        calibrationDiv.style.display = 'flex';
        showCalibrationPoint();
    }

    async function getVideoInputs() {
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            const videoInputs = devices.filter(device => device.kind === 'videoinput');
            console.log('Video inputs:', videoInputs);
            videoInputs.forEach((input, index) => {
                const option = document.createElement('option');
                option.value = input.deviceId;
                option.text = input.label || `Camera ${index + 1}`;
                cameraSelect.appendChild(option);
            });

            if (videoInputs.length > 0) {
                console.log('Cameras found, enabling selection and start button.');
                cameraSelect.disabled = false;
                startCalibrationButton.disabled = false;
            } else {
                console.log('No cameras found, disabling selection and start button.');
                cameraSelect.disabled = true;
                startCalibrationButton.disabled = true;
                alert('No camera found.');
            }
        } catch (error) {
            console.error('Error accessing media devices:', error);
            alert('Failed to access media devices. Please check camera permissions.');
        }
    }

    cameraSelect.addEventListener('change', function() {
        console.log('Camera selection changed:', cameraSelect.value);
        if (cameraSelect.value) {
            setupCamera(cameraSelect.value);
        } else {
            console.warn('No camera ID found in the value.');
        }
    });

    startCalibrationButton.addEventListener('click', function() {
        console.log('Calibration button clicked.');
        if (!startCalibrationButton.disabled) {
            startCalibration();
        } else {
            console.warn('Button is disabled at the time of click.');
        }
    });

    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        try {
            console.log('Checking camera permissions...');
            await navigator.mediaDevices.getUserMedia({ video: true });
            await getVideoInputs();
        } catch (error) {
            console.error('Error accessing the camera:', error);
            alert('Unable to access the camera. Please ensure permissions are granted.');
        }
    } else {
        console.error('Browser API navigator.mediaDevices.getUserMedia not available');
        alert('Your browser does not support the required features. Try updating or switching browsers.');
    }
});
