import os
import cv2
import numpy as np
import face_recognition
from ultralytics import YOLO
from supabase import create_client
from dotenv import load_dotenv
import requests
from io import BytesIO
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Email configuration
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'anandraj28127@gmail.com'
EMAIL_HOST_PASSWORD = 'ebjg hebs epuo mnat'

# Supabase configuration
SUPABASE_URL = "https://hxxjgjnlvnlcggwbypzg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh4eGpnam5sdm5sY2dnd2J5cHpnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzUzMjU4MTAsImV4cCI6MjA1MDkwMTgxMH0.nogvxqHkcfuevDxzu1W8OpINTHuco2SjXUD15ezC3Lw"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

model = YOLO("yolov8n.pt")

def send_alert_email(match_accuracy):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_HOST_USER
        msg['To'] = EMAIL_HOST_USER  # Sending to the same email
        msg['Subject'] = "⚠️ Unauthorized Person Detected"
        
        body = f"""
        Security Alert:
        Unauthorized person detected at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        Match accuracy with known faces: {match_accuracy:.1f}%
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
            server.send_message(msg)
            
        print("Alert email sent successfully")
    except Exception as e:
        print(f"Error sending email: {e}")

def fetch_images_from_supabase():
    try:
        response = supabase.table("reference_images").select("image_path").execute()
        if response.data:
            return response.data
        else:
            print("No images found in Supabase.")
            return []
    except Exception as e:
        print(f"Error fetching images from Supabase: {e}")
        return []

def fetch_and_encode_image(image_url):
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        image = face_recognition.load_image_file(BytesIO(response.content))
        face_encodings = face_recognition.face_encodings(image)
        return face_encodings[0] if face_encodings else None
    except Exception as e:
        print(f"Error fetching or encoding image from {image_url}: {e}")
        return None

def compare_faces(captured_face_encoding, stored_encodings):
    if len(stored_encodings) == 0:
        return False, 0
    
    distances = face_recognition.face_distance(stored_encodings, captured_face_encoding)
    min_distance = np.min(distances)
    is_match = min_distance < 0.5
    accuracy = (1 - min_distance) * 100
    return is_match, accuracy

stored_data = fetch_images_from_supabase()
stored_encodings = []
for item in stored_data:
    encoding = fetch_and_encode_image(item["image_path"])
    if encoding is not None:
        stored_encodings.append(encoding)

camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

cv2.namedWindow("Camera", cv2.WINDOW_NORMAL)
cv2.setWindowProperty("Camera", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

print("Press 'q' to exit.")

FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 1.0
FONT_THICKNESS = 2

while True:
    ret, frame = camera.read()
    if not ret:
        break

    frame_height, frame_width = frame.shape[:2]
    cv2.putText(frame, "Face Recognition System", (10, 30), FONT, FONT_SCALE, (255, 255, 255), FONT_THICKNESS)

    results = model.predict(frame, stream=True)
    for result in results:
        if result.boxes is not None:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls = int(box.cls[0])
                conf = float(box.conf[0])

                if cls == 0:
                    face = frame[y1:y2, x1:x2]
                    if face.size == 0:
                        continue

                    rgb_face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)

                    try:
                        captured_face_encoding = face_recognition.face_encodings(rgb_face)[0]
                        is_match, accuracy = compare_faces(captured_face_encoding, stored_encodings)
                        
                        if is_match:
                            status = "AUTHORIZED"
                            color = (0, 255, 0)
                        else:
                            status = "UNAUTHORIZED"
                            color = (0, 0, 255)
                            send_alert_email(accuracy)
                            
                        text_x = x1
                        status_y = y1 - 50
                        accuracy_y = y1 - 20
                        
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
                        cv2.rectangle(frame, (text_x, status_y - 25), (text_x + 300, status_y + 5), (0, 0, 0), -1)
                        cv2.rectangle(frame, (text_x, accuracy_y - 25), (text_x + 300, accuracy_y + 5), (0, 0, 0), -1)
                        
                        cv2.putText(frame, f"{status}", (text_x, status_y), FONT, FONT_SCALE, color, FONT_THICKNESS)
                        cv2.putText(frame, f"Match: {accuracy:.1f}%", (text_x, accuracy_y), FONT, FONT_SCALE, color, FONT_THICKNESS)

                    except IndexError:
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 3)
                        cv2.rectangle(frame, (x1, y1 - 35), (x1 + 200, y1), (0, 0, 0), -1)
                        cv2.putText(frame, "NO FACE DETECTED", (x1, y1 - 10), FONT, FONT_SCALE, (0, 255, 255), FONT_THICKNESS)

    cv2.imshow("Camera", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

camera.release()
cv2.destroyAllWindows()