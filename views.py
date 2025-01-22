from django.views.decorators.clickjacking import xframe_options_exempt
import numpy as np
from django.shortcuts import render, redirect, reverse
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from .models import DocModel
import json
from django.views.decorators import gzip
import cv2
from .forms import DocumentForm
from django.conf import settings
from django.core.mail import send_mail
from playsound import playsound
import threading
import datetime
import os
from twilio.rest import Client  # Twilio import for calling

# Path to the alarm.wav file
ALARM_FILE_PATH = r'D:\Major\Project\Website\alarm.wav'

# Twilio credentials
TWILIO_ACCOUNT_SID = "ACd6da5f44cfe548d23a949d6d9300ed2b"
TWILIO_AUTH_TOKEN = "0e5719c4fc369eb5bd666132dfe44a0d"
TWILIO_PHONE_NUMBER = "+17174008172"
TO_PHONE_NUMBER = "+919308393403"

model = settings.MODEL

class VideoCamera(object):
    def _init_(self, url=None):
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.status = True
        self.fontScale = 0.9
        self.thickness = 1
        self.SIZE = (150, 150)
        self.THRESH = 0.725 # Threshold for sending email and playing alarm
        self.url = 0 if url is None else '.' + url
        self.video = cv2.VideoCapture(self.url)
        self.skipCount = 2
        self.prev = None
        self.fcount = 0
        self.call_made = False  # New flag to track if call has been made

        # Resize dimensions for the video frame
        self.output_width = 1920  # Reduced width of the output video frame
        self.output_height = 1080  # Reduced height of the output video frame

    def _del_(self):
        self.video.release()

    def play_alarm(self):
        """Play the alarm sound asynchronously."""
        if os.path.exists(ALARM_FILE_PATH):
            try:
                threading.Thread(target=playsound, args=(ALARM_FILE_PATH,), daemon=True).start()
            except Exception as e:
                print(f"Error playing sound: {e}")
        else:
            print(f"Alarm file not found: {ALARM_FILE_PATH}")

    def make_call(self):
        """Make a call using Twilio."""
        try:
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            call = client.calls.create(
                twiml='<Response><Say>Suspicious Activity Detected, please take necessary action !</Say></Response>',
                to=TO_PHONE_NUMBER,
                from_=TWILIO_PHONE_NUMBER
            )
            print(f"Call initiated: {call.sid}")
            self.call_made = True  # Set flag after successful call
        except Exception as e:
            print(f"Error making call: {e}")

    def get_frame(self):
        ret, image = self.video.read()
        if not ret:
            self.status = False
            pass

        # Resize the video frame
        image = cv2.resize(image, (self.output_width, self.output_height))

        if self.fcount % self.skipCount == 0:
            tmp = cv2.resize(image, self.SIZE)
            tmp = tmp / 255.0
            pred = model.predict(np.array([tmp]))
            string = " " if pred[0][0] > self.THRESH else " "
            string += f" {str(pred[0][0])}"
            self.prev = string

            # Trigger actions if prediction exceeds threshold
            if pred[0][0] > self.THRESH:
                # Send email
                
                # Play alarm
         
                # Make call only if it hasn't been made yet
                if not self.call_made:
                    self.make_call()
                    self.play_alarm()
                    send_mail(
                    'Alert: Suspicious Activity Detected',
                    f'Suspicious activity detected with confidence: {pred[0][0]}',
                    'anandraj28127@gmail.com',  # Sender email
                    ['anand.1si21ad009@gmail.com'],  # Recipient email
                    fail_silently=False,
                )

        else:
            string = self.prev

        # Get current date and time
        current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        text_to_display = f"{string} | {current_datetime}"

        # Minimize rectangle and place at bottom
        text_size = cv2.getTextSize(text_to_display, self.font, self.fontScale, self.thickness)[0]
        rect_height = text_size[1] + 35
        rect_width = text_size[0] + 40
        frame_height, frame_width, _ = image.shape

        bottom_left = (10, frame_height - 10)
        top_right = (bottom_left[0] + rect_width, bottom_left[1] - rect_height)

        # Draw rectangle with appropriate color
        if "Peaceful" in string:
            image = cv2.rectangle(image, bottom_left, top_right, (0, 200, 100), cv2.FILLED)
        else:
            image = cv2.rectangle(image, bottom_left, top_right, (0, 0, 255), cv2.FILLED)

        # Add text inside rectangle
        text_position = (bottom_left[0] + 10, bottom_left[1] - 5)
        image = cv2.putText(image, text_to_display, text_position, self.font,
                            self.fontScale, (255, 255, 255), self.thickness, cv2.LINE_AA)

        ret, jpeg = cv2.imencode('.jpg', image)
        self.fcount += 1
        return jpeg.tobytes()

def gen(camera):
    while camera.status:
        frame = camera.get_frame()
        yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

@gzip.gzip_page
def Stream(request):
    try:
        entry = DocModel.objects.all().last()
        return StreamingHttpResponse(gen(VideoCamera(entry.vid.url)), content_type="multipart/x-mixed-replace;boundary=frame")
    except StreamingHttpResponse.HttpResponseServerError as e:
        print("aborted")

@gzip.gzip_page
def StreamToken(request, token):
    try:
        entry = DocModel.objects.filter(stoken=token).last()
        return StreamingHttpResponse(gen(VideoCamera(entry.vid.url)), content_type="multipart/x-mixed-replace;boundary=frame")
    except StreamingHttpResponse.HttpResponseServerError as e:
        print("aborted")

def HomeView(request):
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('streamroom')
    else:
        form = DocumentForm()
        return render(request, 'home.html', {'form': form})

def StreamView(request):
    entry = DocModel.objects.all().last()
    if entry is None:
        return JsonResponse({'message': 'No Video Files Yet!'})
    return render(request, 'stream.html')

def StreamTokenView(request, token):
    try:
        entry = DocModel.objects.filter(stoken=token).last()
        if entry is None:
            return JsonResponse({'message': 'Token Not Registered'})
        return render(request, 'streamtoken.html', {'token': token})
    except DocModel.DoesNotExist:
        return JsonResponse({'message': 'Token Not Registered'})

@csrf_exempt
def APIEnd(request):
    if request.method == 'POST':
        try:
            stoken = request.POST['stoken']
            vidFile = request.FILES['vid']
            DocModel(stoken=stoken, vid=vidFile).save()
            baseurl = request.build_absolute_uri(reverse('home'))
            return JsonResponse({'status': 'ok', 'message': f'Files Received from sender {stoken}', 'vidurl': baseurl + 'streamtoken/' + stoken})
        except Exception as e:
            print(f"Error: {e}")
            return HttpResponse(status=400)
    return JsonResponse({'status': 'Wait '})