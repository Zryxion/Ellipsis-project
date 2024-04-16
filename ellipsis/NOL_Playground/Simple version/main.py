import os
import sys
import logging
import threading
import multiprocessing as mp
import json
import queue
import time
import cv2
import numpy as np
from enum import Enum, auto

ROOTDIR = os.path.dirname(os.path.abspath(__file__))
from Model3D_offline import triangluation

from Thres_function import Detect_Object 

def get3DPoint(leftFrame, rightFrame):
    '''
    MAIN TASK:
    Use the triangluation function to calculate the 3D coordinates of the cans from the video
    '''
    import pandas as pd
    destfolder = "Snapshot"
    '''
    TASK:
    - Use Detect_Object function to get the object position in the form of [x , y]
    - Save the Coordinates into the csv files,
        CameraReader_0_ball.csv for leftFrame's coordinate
        CameraReader_1_ball.csv for rightFrame's coordinate
    IMPORTANT: only change the value of X and Y column, keep the rest of the file the same
    e.g
    Frame,Visibility,X,Y,Z,Event,Timestamp
    1,1,[x coordinate],[y coordinate],0,0,0
    Hint: You can search for 'pandas' and learn how to handle data with it
    '''
    # Start code


    # End code

    # triangluation function is called to calculate the 3D coordinates
    configs = destfolder + "/config"
    triangluation(atleast1hit=False, cameraNum=2, config=configs, output_csv=None)

    '''
    TASK:
    Load Model3D.csv and take the x, y, z point from the csv file
    use it as the output of the function e.g [px, py, pz]
    '''
    # Start code

    # End code
    return [px, py, pz]

def predCoordinates(prevCoor, curCoor):
    '''
    TASK:
    - Take the previous 3D coordinate(prevCoor) and the current 3D coordinate(curCoor)
      and Predict the object position after 2 second (predCoor)
    '''
    # Start code

    # End code
    return predCoor

if __name__ == '__main__':
    cap = cv2.VideoCapture('CameraReader_16.mp4')
    cap1 = cv2.VideoCapture('CameraReader_17.mp4')
    prevCoor = [0, 0, 0]
    startTime = 0
    for i in range(100):
        ret, leftFrame = cap.read()
        ret1, rightFrame = cap1.read()
        # cv2.rectangle(rightFrame, coords[0], coords[2], (0, 255, 0), 2)
        curCoor, mid = Detect_Object(rightFrame)
        # coords1, mid1 = Detect_Object(rightFrame)

        curCoor = get3DPoint(leftFrame, rightFrame)
        # Calculates the predicted coordinates after 2 second
        if time.time() - startTime > 2:
            startTime = time.time()
            predCoor = predCoordinates(prevCoor, curCoor)
            prevCoor = curCoor

        # cv2.imshow('frame',rightFrame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cap1.release()
    cv2.destroyAllWindows()