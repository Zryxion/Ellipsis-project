import logging
import sys
import os
import subprocess
import cv2
import csv
import numpy as np
from math import dist
from tqdm import tqdm
from sklearn.cluster import DBSCAN

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGroupBox, QLabel, QVBoxLayout

from UISettings import *
from Services import SystemService, MsgContract
from common import loadConfig, saveConfig, setIntrinsicMtx

DIRNAME = os.path.dirname(os.path.abspath(__file__))
ROOTDIR = os.path.dirname(os.path.dirname(DIRNAME))
REPLAYDIR = f"{ROOTDIR}/replay"
WINDOW_SIZE = 30

sys.path.append(f"{ROOTDIR}/lib")
from nodes import setupOfflineTrackingNodes

class Processing(QGroupBox):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.fps = 120

        # setup UI
        self.setupUI()

    def hideEvent(self, event):
        logging.debug(f"{self.__class__.__name__}: hided.")

    def showEvent(self, event):
        logging.debug(f"{self.__class__.__name__}: shown.")
        self.startTracking()
        # self.startModel3D() # for test

    def setBackgroundService(self, service:SystemService):
        self.myService = service

    def setupUI(self):
        self.layout_main = QVBoxLayout()
        self.layout_main.addStretch(1)
        self.title = QLabel()
        self.title.setText("Processing...")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("QLabel { background-color:transparent; color : blue; font: bold 80px 'Times'; }")
        self.layout_main.addWidget(self.title)
        self.layout_main.addStretch(1)
        self.setLayout(self.layout_main)

    def showNiceShot(self):
        msg = MsgContract(MsgContract.ID.PAGE_CHANGE, value='NiceShot')
        self.myService.sendMessage(msg)

    def startTracking(self):
        logging.debug(f"TrackNet start...")
        self.weights = "no114_30.tar"
        # replay_date = sorted(os.listdir(REPLAYDIR))[-1]
        replay_date = '2023-06-01_16-15-14'
        self.replay_dir = os.path.join(REPLAYDIR, replay_date)
        nodes = setupOfflineTrackingNodes('CameraSystem', self.cfg, self.replay_dir, self.weights, 'Processing')
        self.myService.addNodes(nodes)

    def startModel3D(self):
        logging.debug(f"Model3D start...")
        self.replay_dir = os.path.join(REPLAYDIR, '2023-06-01_16-15-14') # for test
        config = os.path.abspath(os.path.join(self.replay_dir, "config"))
        output_csv = os.path.abspath(os.path.join(self.replay_dir, "Model3D.csv"))
        cmd = f"python3 {ROOTDIR}/lib/Model3D_offline.py --config {config} --output_csv {output_csv} --atleast1hit"
        # logging.debug(cmd)
        subprocess.call(cmd, shell=True)
        # date = sorted(os.listdir(REPLAYDIR))[-1]
        date =  '2023-06-01_16-15-14' # for test
        self.removeOuterPoint(date)
        self.detectEvent(date)
        output_csv = os.path.abspath(os.path.join(self.replay_dir, "Model3D_event.csv"))
        sections = self.detectSmashs(output_csv)
        self.crop(sections)
        self.showNiceShot()

    def detectSmashs(self, csv_path):
        result = []
        threshold_v = 0
        margin = 30
        with open(csv_path, 'r', newline='') as csvFile:
            rows = csv.DictReader(csvFile)
            rows = list(rows)
            total_frames = len(rows)
            events = []
            for row in rows:
                if int(row['Event']) != 0:
                    events.append((int(row['Frame']), int(row['Event'])))
            print(events, '&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&')
            for i in range(len(events)):
                if events[i][1] == 1:
                    start_frame = events[i][0]
                    end_frame = events[i+1][0]
                    avg_v = self.computeAvgVelocity(start_frame, end_frame, rows)
                    print(self.isFalling(start_frame, end_frame, rows), '@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@2')
                    if avg_v > threshold_v and self.isFalling(start_frame, end_frame, rows):
                    # if avg_v > threshold_v: # for testing
                        result.append((max(0, start_frame-margin), min(end_frame+margin, total_frames - 1)))
            if len(result) == 0:
                result.append((0, total_frames - 1))
        return result
    
    def computeAvgVelocity(self, start_frame, end_frame, rows):
        total_dist = 0.0
        total_time = float(rows[end_frame]['Timestamp']) - float(rows[start_frame]['Timestamp'])
        last_pos = -1
        for i in range(start_frame, end_frame):
            if rows[i]['Visibility'] == '1':
                now_pos = (float(rows[i]['X']), float(rows[i]['Y']), float(rows[i]['Z']))
                if last_pos != -1:
                    total_dist += dist(last_pos, now_pos)
                last_pos = now_pos
        return total_dist / total_time

    def isFalling(self, start_frame, end_frame, rows):
        for i in range(start_frame+1, end_frame):
            if rows[i]['Visibility'] == '1':
                if float(rows[i]['Z']) > float(rows[start_frame]['Z']):
                    return False
        return True

    def crop(self, sections):
        video_dir = f'{ROOTDIR}/replay'
        # date = sorted(os.listdir(video_dir))[-1]
        date =  '2023-06-01_16-15-14' # for test
        input_file_0 = os.path.join(video_dir, date, 'CameraReader_0.mp4')
        input_file_1 = os.path.join(video_dir, date, 'CameraReader_1.mp4')
        output_path = os.path.join(f'{ROOTDIR}/NiceShot', date + '_NiceShot.mp4')
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        reader0 = cv2.VideoCapture(input_file_0)
        reader1 = cv2.VideoCapture(input_file_1)
        output_width = int(reader0.get(cv2.CAP_PROP_FRAME_WIDTH))
        output_height = int(reader0.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(reader0.get(cv2.CAP_PROP_FPS))
        writer = cv2.VideoWriter(output_path, fourcc, fps,(output_width, output_height))
        logging.debug(f"Open success: {reader0.isOpened()}")

        video_frame_list = []
        current_frame = 0
        current_section = 0
        
        if reader0.isOpened() and reader1.isOpened():
            video_frame_tmp = []
            while True:
                rval0, video_frame0 = reader0.read()
                rval1, video_frame1 = reader1.read()
                if rval0 and rval1:
                    if sections[current_section][0] <= current_frame <= sections[current_section][1]:
                        video_frame_list.append(video_frame0) 
                        video_frame_tmp.append(video_frame1)
                    current_frame += 1
                    if (current_section < len(sections) - 1) and (current_frame > sections[current_section][1]):
                        current_section += 1
                        video_frame_list.extend(video_frame_tmp)
                        video_frame_tmp = []
                else:
                    video_frame_list.extend(video_frame_tmp)
                    video_frame_tmp = []
                    break   
        else:
            logging.debug(f"Video open failed")

        for frame in video_frame_list:
            writer.write(frame)

        reader0.release()
        reader1.release()
        writer.release()
        cv2.destroyAllWindows()

    def removeOuterPoint(self, date):
        file_path = os.path.join(REPLAYDIR, date, 'Model3D.csv')
        output_path = os.path.join(REPLAYDIR, date, 'Model3D_mod.csv')
        with open(file_path, 'r', newline='') as csvFile:
            rows = list(csv.DictReader(csvFile))
            with open(output_path, 'w', newline='') as outputfile:
                writer = csv.writer(outputfile)
                writer.writerow(['Frame', 'Visibility', 'X', 'Y', 'Z', 'Event', 'Timestamp'])
                for row in rows:
                    x = float(row['X'])
                    y = float(row['Y'])
                    z = float(row['Z'])
                    if x > 2 or x < -2:
                        row['Visibility'] = 0
                    if y > 3 or y < -3:
                        row['Visibility'] = 0
                    if z > 4 or z < 0:
                        row['Visibility'] = 0
                    row['Frame'] = int(float(row['Frame']))
                    # writer.writerow([row['Frame'], row['Visibility'], row['X'], row['Y'], row['Z'], 0, row['Timestamp']])

                for idx in tqdm(range(0, len(rows) - WINDOW_SIZE + 1, 1)):
                    window = np.array([[float(rows[idx + j]['X']), float(rows[idx + j]['Y']), float(rows[idx + j]['Z'])] for j in range(WINDOW_SIZE)])
                    dbscan = DBSCAN(eps=0.5, min_samples=5, n_jobs=-1)
                    dbscan.fit(window)
                    labels = dbscan.labels_
                    for j in range(WINDOW_SIZE):
                        if labels[j] == -1:
                            rows[idx + j]['Visibility'] = 0

                for row in rows:
                    writer.writerow([row['Frame'], row['Visibility'], row['X'], row['Y'], row['Z'], 0, row['Timestamp']])

    def detectEvent(self, date, points=1):
        file = 'Model3D_mod.csv'
        file_path = os.path.join(REPLAYDIR, date, file)
        output_file = 'Model3D_event.csv'
        output_path = os.path.join(REPLAYDIR, date, output_file)
        serve = False
        with open(file_path, 'r', newline='') as csvFile:
            rows = list(csv.DictReader(csvFile))
            # detect serve
            for idx in range(len(rows)):
                if int(float(rows[idx]['Visibility'])) == 1:
                    rows[idx]['Event'] = 2
                    serve = True
                    break
            # detect dead
            dead = len(rows)-1
            while(dead > 0):
                if int(float(rows[dead]['Visibility'])) == 1:
                    rows[dead]['Event'] = 3
                    break
                else:
                    dead -= 1
            # detect hit
            go_big = 0
            go_small = 0
            min_y = 9
            max_y = -9
            find_min = False
            find_max = False
            count_done = 0
            TREND = self.fps / 24
            idx = 0
            while idx < len(rows):
                if find_max == True and int(float(rows[idx]['Visibility'])) == 1:
                    if float(rows[idx]['Y']) > max_y:
                        max_y = float(rows[idx]['Y'])
                        max_idx = idx
                        count_done = 0
                    else:
                        count_done += 1
                    if count_done > TREND:
                        rows[max_idx]['Event'] = 1
                        find_max = False
                        go_big = 0
                        go_small = 0
                        max_y = -9
                        min_y = 9
                        count_done = 0
                        idx = max_idx
                    print(idx,find_max, find_min, count_done,'&&&&&&&&&&&&&&&&&&&&&&&')
                elif find_min == True and int(float(rows[idx]['Visibility'])) == 1:
                    if float(rows[idx]['Y']) < min_y:
                        min_y = float(rows[idx]['Y'])
                        min_idx = idx
                        count_done = 0
                    else:
                        count_done += 1
                    if count_done > TREND:
                        rows[min_idx]['Event'] = 4 # 過網
                        find_min = False
                        go_small = 0
                        go_big = 0
                        min_y = 9
                        max_y = -9
                        count_done = 0
                        idx = min_idx
                    print(idx,find_max, find_min, count_done,'*********************')
                elif int(float(rows[idx]['Visibility'])) == 1 and serve == True:
                    print(idx, rows[idx]['Y'], max_y, min_y)
                    if float(rows[idx]['Y']) > max_y:
                        max_y = float(rows[idx]['Y'])
                        go_big += 1
                        print(go_big,'######################')
                        #print(f'go big: {idx}')
                        if go_big > TREND:
                            print('@@@@@@@@@@@@@@@@@@@@@@')
                            # print(f'go big > trend on {idx}')
                            max_idx = idx
                            find_max = True
                    elif float(rows[idx]['Y']) < min_y:
                        min_y = float(rows[idx]['Y'])
                        go_small += 1
                        print(go_small,'$$$$$$$$$$$$$$$$$$$$')
                        # print(f'go small: {idx}')
                        if go_small > TREND:
                            # print(f'go small > trend on {idx}')
                            min_idx = idx
                            find_min = True
                idx += 1
            # write back file
            with open(output_path, 'w', newline='') as outputfile:
                writer = csv.writer(outputfile)
                writer.writerow(['Frame', 'Visibility', 'X', 'Y', 'Z', 'Event', 'Timestamp'])
                for row in rows:
                    writer.writerow([row['Frame'], row['Visibility'], row['X'], row['Y'], row['Z'], row['Event'], row['Timestamp']])

