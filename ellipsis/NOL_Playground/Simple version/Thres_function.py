import cv2
import os
import numpy as np
import sys
import paho.mqtt.client as mqtt
import json
import queue
from datetime import datetime
import math
import torch
from ultralytics import YOLO
DIRNAME = os.path.dirname(os.path.abspath(__file__))
ROOTDIR = os.path.dirname(DIRNAME)
sys.path.append(f"{ROOTDIR}/lib")


lowThreshold = 90
max_lowThreshold = 500
ratio = 5
kernel_size = 3

# model = YOLO("yolov8n.pt")
model = YOLO(f"{DIRNAME}/best.pt")
devide = "mps" if torch.backends.mps.is_available() else "cpu"
print(devide)
model.to(devide)


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



def Detect_Object(image):
    results = model.predict(source=image, verbose=False)

    for result in results:
        for bbox in result.boxes.xyxy:
            x1, y1, x2, y2 = int(bbox[0].item()), int(bbox[1].item()), int(bbox[2].item()), int(bbox[3].item())
            min_edge = (x1, y1)  # Top left
            min_edge2 = (x2, y1)  # Top right
            max_edge =  (x2, y2)  # Bottom left
            max_edge2 = (x1, y2)
            mid_x, mid_y = (x1 + x2) // 2, (y1 + y2) // 2
            middle = (mid_x, mid_y)
        
            return [min_edge, min_edge2, max_edge, max_edge2], middle
    return [(0, 0), (0, 0), (0, 0), (0, 0)], (0.0, 0.0)

if __name__ == '__main__':
    image_name = sys.argv[1]

    # "/home/nol/ellipsis/NOL_Playground/snapshot/2023-07-21_11-21-07/2023-07-21_11-21-07_1.png"
    # image_name =  "/home/nol/ellipsis/NOL_Playground/snapshot/2023-05-31_13-09-35/2023-05-31_13-09-35_0.png"

    image = cv2.imread(image_name)
    time1 = datetime.now()
    ellipse_coords, midpoint = Detect_Object(image)

    #
    # output, midp = Detect_Ellipse(image)
    # cv2.rectangle(image, output[0], output[2], (0, 255, 0), 2) # to grid the detected ellipse midpoint
    # cv2.imshow('img', image)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    time2 = datetime.now()
    delta = time2 - time1
    print(delta.total_seconds())
    print(ellipse_coords)