import streamlit as st
import cv2
import numpy as np
from PIL import Image

# Set page layout
import streamlit as st
import cv2
import numpy as np

# Set the page layout as the first command
st.set_page_config(layout="wide")

# Start video capture
st.title("Webcam Live Stream")
run = st.checkbox('Run')

FRAME_WINDOW = st.image([])  # Placeholder for frames

camera = cv2.VideoCapture(0)

while run:
    _, frame = camera.read()
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    FRAME_WINDOW.image(frame)
else:
    st.write('Stopped')

camera.release()

#st.set_page_config(layout="wide")
# Display the Camera Capture UI using HTML and JavaScript
st.components.v1.html('''
    <div>
        <video id="video" width="320" height="240" autoplay></video>
        <button id="snap">Capture</button>
        <canvas id="canvas" width="320" height="240"></canvas>
    </div>
    <script>
        var video = document.getElementById('video');

        // Prompt the user for permission to access the camera
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia({ video: true }).then(function(stream) {
                video.srcObject = stream;
            });
        }

        // Capture the video frame
        document.getElementById("snap").addEventListener("click", function() {
            var canvas = document.getElementById("canvas");
            var context = canvas.getContext("2d");
            context.drawImage(video, 0, 0, 320, 240);
        });
    </script>
''', height=400)

# Install necessary libraries
#!pip install mediapipe opencv-python ipywidgets pandas scipy plotly

# Import required libraries
import cv2
import mediapipe as mp
import numpy as np
from IPython.display import display, Javascript
#from google.colab import output
import base64
from PIL import Image
import io
import threading
import time
import math
import ipywidgets as widgets
import pandas as pd
from datetime import datetime
import atexit
import plotly.graph_objs as go
import plotly.graph_objects as go
import os

# Use environment variable for PORT provided by Render
port = int(os.environ.get("PORT", 8501))

# Set server configurations in Streamlit
import streamlit as st
#st.set_page_config(layout="wide")

# Your existing Streamlit code


# Suppress deprecated warnings from protobuf
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='google.protobuf')

# Enable custom widget manager for Plotly in Colab
#output.enable_custom_widget_manager()

# Initialize MediaPipe Face Mesh
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    static_image_mode=False,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Define eye landmark indices for left and right eyes
LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
LEFT_IRIS_INDICES = [468, 469, 470, 471, 472, 473]
RIGHT_IRIS_INDICES = [474, 475, 476, 477, 478, 479]

# Initialize tracking variables
previous_center = None
speed = 0
prev_time = time.time()
frames = []
lock = threading.Lock()
blink_count = 0
blink_threshold = 0.20  # EAR threshold for blink detection
blink_flag = False
fixation_start_time = None
fixation_duration = 0
fixation_threshold = 2  # pixels
data_records = []
is_streaming = True  # Flag to control video stream
saccade_start_time = None
saccadic_latency = 0
smooth_pursuit_gain = 0
microsaccades = 0
head_pose = {"yaw": 0, "pitch": 0, "roll": 0}
eye_openness_left = 0.0
eye_openness_right = 0.0
pcr_ratio = 0.0
pupil_shape_deformation = 0.0
gaze_direction = 0.0

# Define helper functions
def calculate_eye_center(landmarks, indices, width, height):
    x = [landmarks[i].x for i in indices]
    y = [landmarks[i].y for i in indices]
    return (int(np.mean(x) * width), int(np.mean(y) * height))

def calculate_pupil_diameter(landmarks, iris_indices, width, height):
    if len(iris_indices) == 0:
        return 0.0  # Return 0 if iris landmarks are not available

    iris_landmarks = [landmarks[i] for i in iris_indices if i < len(landmarks)]  # Ensure valid indices
    if len(iris_landmarks) < 2:
        return 0.0  # Return 0 if not enough landmarks for calculation

    center_x = np.mean([lm.x for lm in iris_landmarks]) * width
    center_y = np.mean([lm.y for lm in iris_landmarks]) * height
    distances = [math.sqrt((lm.x * width - center_x)**2 + (lm.y * height - center_y)**2) for lm in iris_landmarks]
    diameter = 2 * np.mean(distances)
    return diameter

def classify_speed(speed):
    if speed < 5:
        return "Very Slow"
    elif speed < 25:
        return "Slow"
    elif speed < 50:
        return "Normal"
    elif speed < 100:
        return "High"
    else:
        return "Very High"

def calculate_gaze_deviation(eye_center, width, height):
    center_x, center_y = width / 2, height / 2
    dx = eye_center[0] - center_x
    dy = eye_center[1] - center_y
    angle = math.degrees(math.atan2(dy, dx))
    return angle

def detect_blink(landmarks, width, height):
    # Eye Aspect Ratio (EAR) calculation
    def eye_aspect_ratio(eye):
        # Compute the distances between the vertical eye landmarks
        A = math.dist((eye[1].x * width, eye[1].y * height), (eye[5].x * width, eye[5].y * height))
        B = math.dist((eye[2].x * width, eye[2].y * height), (eye[4].x * width, eye[4].y * height))
        # Compute the distance between the horizontal eye landmarks
        C = math.dist((eye[0].x * width, eye[0].y * height), (eye[3].x * width, eye[3].y * height))
        # Compute EAR
        ear = (A + B) / (2.0 * C)
        return ear

    # Left eye EAR
    left_eye = [landmarks[i] for i in LEFT_EYE_INDICES if i < len(landmarks)]
    right_eye = [landmarks[i] for i in RIGHT_EYE_INDICES if i < len(landmarks)]

    if len(left_eye) == 6 and len(right_eye) == 6:
        left_ear = eye_aspect_ratio(left_eye)
        right_ear = eye_aspect_ratio(right_eye)
        avg_ear = (left_ear + right_ear) / 2.0
        return avg_ear < blink_threshold
    return False

def calculate_smooth_pursuit_gain(eye_center, previous_center, width, height):
    if previous_center is None:
        return 0.0

    # Calculate movement distance
    eye_movement = math.sqrt((eye_center[0] - previous_center[0])**2 + (eye_center[1] - previous_center[1])**2)
    # Approximate target velocity using movement (can be improved with actual target data)
    target_movement = math.sqrt(width**2 + height**2) / 60  # Assuming a screen-sized target moving at 60Hz
    return eye_movement / target_movement

# New Feature Functions
def calculate_pcr_ratio(landmarks, width, height):
    eye_top = landmarks[1]  # Assuming landmark 1 is the top reflection point
    eye_bottom = landmarks[5]  # Assuming landmark 5 is the bottom reflection point
    vertical_distance = math.dist(
        (eye_top.x * width, eye_top.y * height),
        (eye_bottom.x * width, eye_bottom.y * height)
    )
    # Compute the PCR ratio
    return vertical_distance / height  # Normalize by the frame height

def calculate_3d_gaze_direction(landmarks):
    eye_vector = np.array([landmarks[1].x - landmarks[5].x, landmarks[1].y - landmarks[5].y])
    gaze_angle = np.degrees(np.arctan2(eye_vector[1], eye_vector[0]))
    return gaze_angle

def calculate_eye_openness(landmarks, indices, width, height):
    eye_top = landmarks[indices[1]]
    eye_bottom = landmarks[indices[5]]
    vertical_distance = math.dist(
        (eye_top.x * width, eye_top.y * height),
        (eye_bottom.x * width, eye_bottom.y * height)
    )
    return vertical_distance

def calculate_pupil_shape_deformation(landmarks, iris_indices, width, height):
    if len(iris_indices) == 0:
        return 0.0
    iris_landmarks = [landmarks[i] for i in iris_indices if i < len(landmarks)]
    if len(iris_landmarks) < 4:
        return 0.0
    distances = [
        math.dist(
            (iris_landmarks[i].x * width, iris_landmarks[i].y * height),
            (iris_landmarks[j].x * width, iris_landmarks[j].y * height)
        )
        for i in range(len(iris_landmarks))
        for j in range(i+1, len(iris_landmarks))
    ]
    max_dist = max(distances)
    min_dist = min(distances)
    return max_dist / min_dist if min_dist > 0 else 0.0

def estimate_head_pose(landmarks, width, height):
    # Use specific landmarks to approximate head orientation
    nose_tip = landmarks[1]  # Assuming 1 is the nose tip
    left_eye = landmarks[33]  # Assuming 33 is the left eye corner
    right_eye = landmarks[263]  # Assuming 263 is the right eye corner

    eye_vector = np.array([left_eye.x - right_eye.x, left_eye.y - right_eye.y])
    yaw = np.degrees(np.arctan2(eye_vector[1], eye_vector[0]))
    pitch = np.degrees(np.arctan2(
        nose_tip.y - (left_eye.y + right_eye.y) / 2,
        nose_tip.x - (left_eye.x + right_eye.x) / 2
    ))

    return {"yaw": yaw, "pitch": pitch, "roll": 0}  # Simplified roll estimation

def detect_microsaccades(eye_center, previous_center):
    if previous_center is None:
        return 0
    movement = math.sqrt(
        (eye_center[0] - previous_center[0]) ** 2 +
        (eye_center[1] - previous_center[1]) ** 2
    )
    if 0.1 < movement < 1.0:  # Threshold range for microsaccades
        return 1
    return 0

# Define the callback function to receive frames from JavaScript
def receive_frame(dataURL):
    global frames
    try:
        header, encoded = dataURL.split(",", 1)
        data = base64.b64decode(encoded)
        img = Image.open(io.BytesIO(data))
        img = img.convert('RGB')
        img = np.array(img)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        with lock:
            frames.append(img)
    except Exception as e:
        print(f"Error in receive_frame: {e}")

# Register the callback
#output.register_callback('notebook.receive_frame', receive_frame)

# JavaScript code to capture video frames and send to Python
def capture_video():
    display(Javascript('''
        async function startVideo() {
            const video = document.createElement('video');
            video.width = 640;
            video.height = 480;
            video.autoplay = true;
            video.style.display = 'none';
            document.body.appendChild(video);

            const stream = await navigator.mediaDevices.getUserMedia({video: true});
            video.srcObject = stream;

            // Function to send frames to Python
            const sendFrame = () => {
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                const dataURL = canvas.toDataURL('image/jpeg');
                google.colab.kernel.invokeFunction('notebook.receive_frame', [dataURL], {});
                setTimeout(sendFrame, 50);  // Send frame every 50ms (20 FPS)
            }

            video.addEventListener('play', () => {
                sendFrame();
            });
        }

        startVideo();
    '''))

# Start capturing video
capture_video()

# Create Image widgets for real-time streams
face_image = widgets.Image(format='jpeg', width=640, height=480)        # Face with mesh and eye movement
yellow_dot_image = widgets.Image(format='jpeg', width=224, height=224)  # Yellow dot movement

# Create Plotly real-time graphs with predefined traces
saccade_speed_fig = go.Figure(
    data=[go.Scatter(x=[], y=[], mode='lines+markers', line=dict(color='blue'), name='Saccade Speed')],
    layout=go.Layout(
        title="Saccade Speed Over Time",
        xaxis_title="Time",
        yaxis_title="Speed (pixels/sec)",
        height=300
    )
)
st.plotly_chart(saccade_speed_fig )
blink_count_fig = go.Figure(
    data=[go.Scatter(x=[], y=[], mode='lines+markers', line=dict(color='orange'), name='Blink Count')],
    layout=go.Layout(
        title="Blink Count Over Time",
        xaxis_title="Time",
        yaxis_title="Blinks",
        height=300
    )
)
st.plotly_chart(blink_count_fig)
fixation_duration_fig = go.Figure(
    data=[go.Scatter(x=[], y=[], mode='lines+markers', line=dict(color='green'), name='Fixation Duration')],
    layout=go.Layout(
        title="Fixation Duration Over Time",
        xaxis_title="Time",
        yaxis_title="Duration (sec)",
        height=300
    )
)
st.plotly_chart(fixation_duration_fig)
pupil_diameter_fig = go.Figure(
    data=[go.Scatter(x=[], y=[], mode='lines+markers', line=dict(color='purple'), name='Pupil Diameter')],
    layout=go.Layout(
        title="Pupil Diameter Over Time",
        xaxis_title="Time",
        yaxis_title="Diameter (mm)",
        height=300
    )
)
st.plotly_chart(pupil_diameter_fig)
# Create labels for all 13 metrics with fixed width
speed_label = widgets.HTML(value="<b>Saccade Speed:</b> 0.00 pixels/sec (N/A)",
                           layout=widgets.Layout(width='100%', margin='5px'))
blink_label = widgets.HTML(value="<b>Blinks:</b> 0",
                           layout=widgets.Layout(width='100%', margin='5px'))
fixation_label = widgets.HTML(value="<b>Fixation Duration:</b> 0.00 sec",
                              layout=widgets.Layout(width='100%', margin='5px'))
pupil_label = widgets.HTML(value="<b>Pupil Diameter:</b> 0.00 mm",
                           layout=widgets.Layout(width='100%', margin='5px'))
gaze_label = widgets.HTML(value="<b>Gaze Deviation:</b> 0.00°",
                          layout=widgets.Layout(width='100%', margin='5px'))
latency_label = widgets.HTML(value="<b>Saccadic Latency:</b> 0.00 ms",
                             layout=widgets.Layout(width='100%', margin='5px'))
smooth_pursuit_label = widgets.HTML(value="<b>Smooth Pursuit Gain:</b> 0.00",
                                    layout=widgets.Layout(width='100%', margin='5px'))
microsaccades_label = widgets.HTML(value="<b>Microsaccades:</b> 0",
                                   layout=widgets.Layout(width='100%', margin='5px'))
head_pose_label = widgets.HTML(value="<b>Head Pose:</b> Yaw: 0.00°, Pitch: 0.00°, Roll: 0.00°",
                               layout=widgets.Layout(width='100%', margin='5px'))
eye_openness_label = widgets.HTML(value="<b>Eye Openness:</b> Left: 0.00, Right: 0.00",
                                   layout=widgets.Layout(width='100%', margin='5px'))
pcr_ratio_label = widgets.HTML(value="<b>PCR Ratio:</b> 0.00",
                                layout=widgets.Layout(width='100%', margin='5px'))
pupil_deformation_label = widgets.HTML(value="<b>Pupil Shape Deformation:</b> 0.00",
                                       layout=widgets.Layout(width='100%', margin='5px'))
gaze_direction_label = widgets.HTML(value="<b>3D Gaze Direction:</b> 0.00°",
                                     layout=widgets.Layout(width='100%', margin='5px'))

# Button to stop the video stream
stop_button = widgets.Button(description="Stop Stream",
                             button_style='danger',
                             tooltip='Click to stop the video stream and save data',
                             layout=widgets.Layout(width='150px', height='40px', margin='10px'))

# Organize metrics into multiple rows with two labels each
metrics_row1 = widgets.HBox([speed_label, blink_label], layout=widgets.Layout(width='100%'))
metrics_row2 = widgets.HBox([fixation_label, pupil_label], layout=widgets.Layout(width='100%'))
metrics_row3 = widgets.HBox([gaze_label, latency_label], layout=widgets.Layout(width='100%'))
metrics_row4 = widgets.HBox([smooth_pursuit_label, microsaccades_label], layout=widgets.Layout(width='100%'))
metrics_row5 = widgets.HBox([head_pose_label, eye_openness_label], layout=widgets.Layout(width='100%'))
metrics_row6 = widgets.HBox([pcr_ratio_label, pupil_deformation_label], layout=widgets.Layout(width='100%'))
metrics_row7 = widgets.HBox([gaze_direction_label], layout=widgets.Layout(width='100%'))

# Combine all metric rows into a single VBox
metrics_box = widgets.VBox([
    metrics_row1,
    metrics_row2,
    metrics_row3,
    metrics_row4,
    metrics_row5,
    metrics_row6,
    metrics_row7
], layout=widgets.Layout(width='100%', justify_content='space-between'))

# Arrange the Plotly graphs in a grid with two columns
graphs_grid = widgets.GridBox(
    children=[
        widgets.Output(),  # Placeholder for saccade_speed_fig
        widgets.Output(),  # Placeholder for blink_count_fig
        widgets.Output(),  # Placeholder for fixation_duration_fig
        widgets.Output()   # Placeholder for pupil_diameter_fig
    ],
    layout=widgets.Layout(
        grid_template_columns='50% 50%',
        grid_template_rows='50% 50%',
        width='100%',
        height='auto',
        grid_gap='10px'
    )
)

# Display the Plotly figures inside the GridBox
with graphs_grid.children[0]:
    display(saccade_speed_fig)
with graphs_grid.children[1]:
    display(blink_count_fig)
with graphs_grid.children[2]:
    display(fixation_duration_fig)
with graphs_grid.children[3]:
    display(pupil_diameter_fig)

# Arrange the images side by side
images_box = widgets.HBox([face_image, yellow_dot_image],
                          layout=widgets.Layout(justify_content='space-between', width='100%'))

# Combine all controls
controls_box = widgets.VBox([
    metrics_box,
    graphs_grid,
    stop_button
], layout=widgets.Layout(justify_content='space-between', padding='10px', width='100%'))

# Combine all into a main VBox with a header
main_box = widgets.VBox([
    widgets.HTML(value="<h2 style='text-align: center; color: #4CAF50;'>Eye Movement Tracking Dashboard</h2>"),
    images_box,
    controls_box
], layout=widgets.Layout(align_items='center', padding='20px', width='100%'))

display(main_box)

# Process frames with all features
def process_frames():
    global previous_center, speed, prev_time, blink_count, blink_flag
    global fixation_start_time, fixation_duration, data_records, is_streaming
    global microsaccades, head_pose, eye_openness_left, eye_openness_right
    global pcr_ratio, pupil_shape_deformation, gaze_direction
    global saccade_start_time, saccadic_latency, smooth_pursuit_gain

    amplification_factor = 30  # Increased amplification for clearer movement

    while is_streaming:
        with lock:
            if len(frames) > 0:
                frame = frames.pop(0)
            else:
                frame = None
        if frame is not None:
            height, width, _ = frame.shape
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(image_rgb)
            yellow_dot_frame = np.ones((224, 224, 3), dtype=np.uint8) * 255  # White background

            # Initialize dx and dy to handle cases where no face is detected
            dx, dy = 0, 0

            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    # Draw face mesh on the original frame
                    mp_drawing.draw_landmarks(
                        image=frame,
                        landmark_list=face_landmarks,
                        connections=mp_face_mesh.FACEMESH_TESSELATION,
                        landmark_drawing_spec=None,
                        connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_tesselation_style()
                    )
                    mp_drawing.draw_landmarks(
                        image=frame,
                        landmark_list=face_landmarks,
                        connections=mp_face_mesh.FACEMESH_CONTOURS,
                        landmark_drawing_spec=None,
                        connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_contours_style()
                    )

                    # Calculate centers of left and right eyes
                    left_center = calculate_eye_center(face_landmarks.landmark, LEFT_EYE_INDICES, width, height)
                    right_center = calculate_eye_center(face_landmarks.landmark, RIGHT_EYE_INDICES, width, height)

                    # Calculate the overall eye center
                    eye_center = ((left_center[0] + right_center[0]) // 2, (left_center[1] + right_center[1]) // 2)

                    # Draw a yellow dot at the eye center in the face frame
                    cv2.circle(frame, eye_center, 15, (0, 255, 255), -1)  # Increased radius for visibility

                    # Calculate speed based on movement
                    current_time = time.time()
                    if previous_center is not None:
                        dx = eye_center[0] - previous_center[0]
                        dy = eye_center[1] - previous_center[1]
                        dt = current_time - prev_time
                        speed = math.sqrt(dx**2 + dy**2) / dt if dt > 0 else 0
                        speed_class = classify_speed(speed)
                    else:
                        speed = 0.0
                        speed_class = "N/A"

                    # Update previous position and time
                    previous_center = eye_center
                    prev_time = current_time

                    # Calculate Smooth Pursuit Gain
                    smooth_pursuit_gain = calculate_smooth_pursuit_gain(eye_center, previous_center, width, height)

                    # Draw the yellow dot on a separate frame (amplified)
                    rel_x = (eye_center[0] - width / 2) * amplification_factor
                    rel_y = (eye_center[1] - height / 2) * amplification_factor
                    norm_x = 112 + rel_x  # Center of 224x224 frame is 112
                    norm_y = 112 + rel_y
                    norm_x = int(np.clip(norm_x, 0, 223))
                    norm_y = int(np.clip(norm_y, 0, 223))
                    cv2.circle(yellow_dot_frame, (norm_x, norm_y), 15, (0, 255, 255), -1)  # Increased radius

                    # Pupil Diameter
                    pupil_diameter = calculate_pupil_diameter(face_landmarks.landmark, LEFT_IRIS_INDICES + RIGHT_IRIS_INDICES, width, height)

                    # Gaze Deviation
                    gaze_deviation = calculate_gaze_deviation(eye_center, width, height)

                    # Blink Detection
                    blink_detected = detect_blink(face_landmarks.landmark, width, height)
                    if blink_detected and not blink_flag:
                        blink_count += 1
                        blink_flag = True
                    elif not blink_detected and blink_flag:
                        blink_flag = False

                    # Saccadic Latency
                    if saccade_start_time is None:
                        saccade_start_time = current_time
                    else:
                        saccadic_latency = (current_time - saccade_start_time) * 1000  # in ms
                        saccade_start_time = None

                    # Fixation Duration
                    movement = math.sqrt(dx**2 + dy**2)
                    if movement < fixation_threshold:
                        if fixation_start_time is None:
                            fixation_start_time = current_time
                        else:
                            fixation_duration = current_time - fixation_start_time
                    else:
                        if fixation_start_time is not None:
                            fixation_duration = current_time - fixation_start_time
                            fixation_start_time = None

                    # New Features Calculations
                    microsaccades += detect_microsaccades(eye_center, previous_center)
                    head_pose = estimate_head_pose(face_landmarks.landmark, width, height)
                    eye_openness_left = calculate_eye_openness(face_landmarks.landmark, LEFT_EYE_INDICES, width, height)
                    eye_openness_right = calculate_eye_openness(face_landmarks.landmark, RIGHT_EYE_INDICES, width, height)
                    pcr_ratio = calculate_pcr_ratio(face_landmarks.landmark, width, height)
                    pupil_shape_deformation = calculate_pupil_shape_deformation(face_landmarks.landmark, LEFT_IRIS_INDICES + RIGHT_IRIS_INDICES, width, height)
                    gaze_direction = calculate_3d_gaze_direction(face_landmarks.landmark)

                    # Data Recording
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    data_records.append({
                        "Timestamp": timestamp,
                        "Saccade_Speed_pixels_sec": speed,
                        "Saccade_Speed_Class": speed_class,
                        "Blink_Count": blink_count,
                        "Fixation_Duration_sec": fixation_duration,
                        "Pupil_Diameter_mm": pupil_diameter,
                        "Gaze_Deviation_deg": gaze_deviation,
                        "Saccadic_Latency_ms": saccadic_latency,
                        "Smooth_Pursuit_Gain": smooth_pursuit_gain,
                        "Microsaccades": microsaccades,
                        "Head_Pose_Yaw_deg": head_pose["yaw"],
                        "Head_Pose_Pitch_deg": head_pose["pitch"],
                        "Head_Pose_Roll_deg": head_pose["roll"],
                        "Eye_Openness_Left": eye_openness_left,
                        "Eye_Openness_Right": eye_openness_right,
                        "PCR_Ratio": pcr_ratio,
                        "Pupil_Shape_Deformation": pupil_shape_deformation,
                        "3D_Gaze_Direction_deg": gaze_direction
                    })

                    # Update Plotly graphs by appending data to existing traces
                    saccade_speed_fig.data[0].x += (timestamp,)
                    saccade_speed_fig.data[0].y += (speed,)
                    blink_count_fig.data[0].x += (timestamp,)
                    blink_count_fig.data[0].y += (blink_count,)
                    fixation_duration_fig.data[0].x += (timestamp,)
                    fixation_duration_fig.data[0].y += (fixation_duration,)
                    pupil_diameter_fig.data[0].x += (timestamp,)
                    pupil_diameter_fig.data[0].y += (pupil_diameter,)

            # Encode the face frame as JPEG
            _, encoded_face_frame = cv2.imencode('.jpg', frame)
            face_image.value = encoded_face_frame.tobytes()

            # Encode the yellow dot frame as JPEG
            _, encoded_dot_frame = cv2.imencode('.jpg', yellow_dot_frame)
            yellow_dot_image.value = encoded_dot_frame.tobytes()

            # Update labels for all features
            speed_label.value = f"<b>Saccade Speed:</b> {speed:.2f} pixels/sec ({speed_class})"
            blink_label.value = f"<b>Blinks:</b> {blink_count}"
            fixation_label.value = f"<b>Fixation Duration:</b> {fixation_duration:.2f} sec"
            pupil_label.value = f"<b>Pupil Diameter:</b> {pupil_diameter:.2f} mm"
            gaze_label.value = f"<b>Gaze Deviation:</b> {gaze_deviation:.2f}°"
            latency_label.value = f"<b>Saccadic Latency:</b> {saccadic_latency:.2f} ms"
            smooth_pursuit_label.value = f"<b>Smooth Pursuit Gain:</b> {smooth_pursuit_gain:.2f}"
            microsaccades_label.value = f"<b>Microsaccades:</b> {microsaccades}"
            head_pose_label.value = f"<b>Head Pose:</b> Yaw: {head_pose['yaw']:.2f}°, Pitch: {head_pose['pitch']:.2f}°, Roll: {head_pose['roll']:.2f}°"
            eye_openness_label.value = f"<b>Eye Openness:</b> Left: {eye_openness_left:.2f}, Right: {eye_openness_right:.2f}"
            pcr_ratio_label.value = f"<b>PCR Ratio:</b> {pcr_ratio:.2f}"
            pupil_deformation_label.value = f"<b>Pupil Shape Deformation:</b> {pupil_shape_deformation:.2f}"
            gaze_direction_label.value = f"<b>3D Gaze Direction:</b> {gaze_direction:.2f}°"

        # Control frame rate (20 FPS)
        time.sleep(0.05)

# Button event handler to stop the stream
def stop_stream(b):
    global is_streaming
    is_streaming = False
    save_data()

# Attach the event handler to the button
stop_button.on_click(stop_stream)

# Start processing frames in a separate thread
processing_thread = threading.Thread(target=process_frames)
processing_thread.daemon = True
processing_thread.start()

# Save data to CSV when the stop button is clicked
def save_data():
    global data_records
    if data_records:
        df = pd.DataFrame(data_records)
        filename = f"eye_movement_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(filename, index=False)
        print(f"Data saved to {filename}")
    else:
        print("No data to save.")

# Automatically save data when the kernel is interrupted
atexit.register(save_data)