import cv2
import os
import numpy as np
import sys
import paho.mqtt.client as mqtt
import json
import queue
from turbojpeg import TurboJPEG
from datetime import datetime
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import qRed, qGreen, qBlue
import math
from scipy import stats

DIRNAME = os.path.dirname(os.path.abspath(__file__))
ROOTDIR = os.path.dirname(DIRNAME)
sys.path.append(f"{ROOTDIR}/lib")
from nodes import CameraReader
from frame import Frame
from common import *
from message import *

lowThreshold = 90
max_lowThreshold = 500
ratio = 5
kernel_size = 3

def hsv_mask(image):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # lower = np.array([42, 41, 190])
    # upper = np.array([44, 55 , 250])
    #current best:
    lower = np.array([87, 35, 85])
    upper = np.array([179, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    result = cv2.bitwise_and(image, image, mask=mask)
    result =  cv2.cvtColor(result, cv2.COLOR_HSV2BGR)
    return result

def Detect_Ellipse(image):
    masked = hsv_mask(image)

    blur = cv2.GaussianBlur(masked, (5,5), 0)
    sub = masked.astype(int) - blur
    detected_edges = np.clip(masked.astype(int) + sub*2, a_min = 0, a_max = 255).astype('uint8')
    detected_edges = cv2.Canny(detected_edges,100,500,apertureSize = kernel_size)

    ellipse = cv2.HoughCircles(detected_edges, cv2.HOUGH_GRADIENT, dp=1, minDist=0.01, param1=150, param2=12, minRadius=0, maxRadius=200)

    output = image.copy()
    # ensure at least some circles were found
    if ellipse is not None:
        # convert the (x, y) coordinates and radius of the circles to integers
        ellipse = np.round(ellipse[0, :]).astype("int")
        # loop over the (x, y) coordinates and radius of the circles
        test = [(x**2 + y**2)**0.5 for (x,y,_) in ellipse]

        #Remove outliers using z-score
        z = np.abs(stats.zscore(test))
        vals = np.where(z > 1)
        rem = np.delete(test,vals[0])

        max_y = max(rem)
        min_y = min(rem)
        max_ = test.index(max_y)
        min_ = test.index(min_y)
        (x, y, r) = ellipse[min_]
        (x1, y1, r1) = ellipse[max_]

        if(math.dist((x,y),(x1,y1)) < 210):
            
          min_edge = (int(min(x-r,x1-r)), int(min(y-r,y1-r)))#(x,y) #top left
          max_edge = (int(max(x+r,x1+r)), int(max(y+r,y1+r)))#(x,y) #bottom right
  
          min_edge2 = (int(max(x+r,x1+r)), int(min(y-r, y1-r))) #top right
          max_edge2 = (int(min(x-r,x1-r)), int(max(y+r,y1+r))) #bottom left
  
          middle = (int((min_edge[0] + max_edge[0])/2), int((min_edge[1] + min_edge[1])/2)) #middle point
  
  
        #   cv2.rectangle(output, min_edge, max_edge, (0, 255, 0), 2)
          return [min_edge, min_edge2, max_edge, max_edge2], middle
            # return ([(494, 622), (622, 622), (622, 754), (494, 754)], (558.0, 622.0))
    
    return [(0, 0), (0, 0), (0, 0), (0, 0)], (0.0, 0.0)

class DetectThread(QThread):
    def __init__(self, mqtt_broker, camera:CameraReader, detectSignal:pyqtSignal, index):
        super().__init__()
        self.camera = camera
        self.detectSignal = detectSignal
        self.index = index

        self.alive = True

        # frame Queue
        self.frameQueue = queue.Queue(maxsize=30)

        # Mqtt client for receive raw image
        client = mqtt.Client()
        client.on_connect = self.onConnect
        client.on_message = self.onMessage
        client.connect(mqtt_broker)
        self.client = client

        self.jpeg = TurboJPEG('/usr/lib/x86_64-linux-gnu/libturbojpeg.so.0')
        self.detectCounter = 0

    def onConnect(self, client, userdata, flag, rc):
        self.client.subscribe(self.camera.output_topic)

    def onMessage(self, client, userdata, msg):
        data = json.loads(msg.payload)
        if 'id' in data and 'timestamp' in data and 'raw_data' in data:
            if self.detectCounter == 0:
                frame = Frame(data['id'], data['timestamp'], data['raw_data'])
                self.frameQueue.put_nowait(frame)
            self.detectCounter = (self.detectCounter + 1) % 30

    def stop(self):
        self.alive = False

    def run(self):
        try:
            self.client.loop_start()
            while self.alive:
                try:
                    frame = self.frameQueue.get()
                    image = frame.coverToCV2ByTurboJPEG(self.jpeg)
                    ellipse_coords, midpoint = Detect_Ellipse(image)
                    self.detectSignal.emit(ellipse_coords, midpoint, self.index)
                except:
                    continue
        finally:
            self.client.loop_stop()

if __name__ == '__main__':
    import time
    vid = cv2.VideoCapture(0)

    # "/home/nol/ellipsis/NOL_Playground/snapshot/2023-07-21_11-21-07/2023-07-21_11-21-07_1.png"
    # image_name =  "/home/nol/ellipsis/NOL_Playground/snapshot/2023-05-31_13-09-35/2023-05-31_13-09-35_0.png"
    while(True): 
        
        # Capture the video frame 
        # by frame 
        ret, frame = vid.read() 

        # Display the resulting frame 
        ellipse_coords, midpoint = Detect_Ellipse(frame)

        print(ellipse_coords)
        frame = cv2.rectangle(frame, ellipse_coords[0], ellipse_coords[2], (255,0,0), 2) 
        cv2.imshow('frame', frame) 
        # the 'q' button is set as the 
        # quitting button you may use any 
        # desired button of your choice 
        if cv2.waitKey(1) & 0xFF == ord('q'): 
            break
        
        # time.sleep(1)
    
    # After the loop release the cap object 
    vid.release() 
    # Destroy all the windows 
    cv2.destroyAllWindows() 



    # image = cv2.imread(image_name)
    # time1 = datetime.now()
    # ellipse_coords, midpoint = Detect_Ellipse(frame)

    #
    # output, midp = Detect_Ellipse(image)
    # cv2.rectangle(image, output[0], output[2], (0, 255, 0), 2) # to grid the detected ellipse midpoint
    # cv2.imshow('img', image)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    # time2 = datetime.now()
    # delta = time2 - time1
    # print(delta.total_seconds())
    # print(ellipse_coords)