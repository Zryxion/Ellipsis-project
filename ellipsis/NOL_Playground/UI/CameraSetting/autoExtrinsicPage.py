import os
import json
import logging
import numpy as np
import time
import re
import subprocess
import pickle
from functools import partial

from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QWidget, QHBoxLayout, QPushButton, QLabel, QGridLayout, QCheckBox
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QPixmap, QPainter
from PyQt5.Qt import *

from UISettings import *
from nodes import CameraReader
from Services import SystemService, MsgContract
from message import *
from common import *
from h2pose.H2Pose import H2Pose
from h2pose.Hfinder2 import Hfinder2
from auto.corner import corner
from auto.cornerDL import cornerDL
from auto.mapping import mapping
from auto.court_mapping import court_mapping
from auto.points_after_map import points_mapping

DIRNAME = os.path.dirname(os.path.abspath(__file__))
ROOTDIR = os.path.dirname(os.path.dirname(DIRNAME))
ICONDIR = f"{ROOTDIR}/UI/icon"

CORNER_SIZE = 15
STAR_SIZE = 20
CORNERS_ZOOM_X = [17, 47, 200, 350, 381]
CORNERS_ZOOM_Y = [20, 70, 305, 548, 784, 831]
CORNERS_TYPE = [8, 2, 2, 2, 2, 7,   3, 1, 1, 1, 1, 5,   3, 1, 5, 3, 1, 5,   3, 1, 1, 1, 1, 5,   9, 4, 4, 4, 4, 6]
CORNERS_2D_X = [14-CORNER_SIZE, 20, 44-CORNER_SIZE, 50, 197-CORNER_SIZE, 203, 347-CORNER_SIZE, 353, 378-CORNER_SIZE, 384]
CORNERS_2D_Y = [17-CORNER_SIZE, 23, 67-CORNER_SIZE, 73, 302-CORNER_SIZE, 308, 545-CORNER_SIZE, 551, 781-CORNER_SIZE, 787, 828-CORNER_SIZE, 834]
# CORNERS_3D_X = [-3.05, -3.01, -2.59, -2.55, -0.02, 0.02, 2.55, 2.59, 3.01, 3.05] # corner position in reality (unit: meter)
CORNERS_3D_X = [-1.159, -1.1438, -0.9842, -0.969, -0.0076, 0.0076, 0.969, 0.9842, 1.1438, 1.159]
# CORNERS_3D_Y = [ 6.7, 6.66, 5.94, 5.9, 2.02, 1.98, -1.98, -2.02, -5.9, -5.94, -6.66, -6.7]
CORNERS_3D_Y = [2.546, 2.5308, 2.2572, 2.242, 0.7676, 0.7524, -0.7524, -0.7676, -2.242, -2.2572, -2.5308, -2.546]
COURT_IMAGE = f"{ICONDIR}/court/std_court.png"
STAR_IMAGE = f"{ICONDIR}/court/star.png"
RESIZE_RATIO_W = 1440/800
RESIZE_RATIO_H = 1080/600

IMG_PATH = f"{ROOTDIR}/lib/auto/demo.jpg"  #img output
YOLO_TXT_PATH = f"{ROOTDIR}/lib/auto/yolo_output/exp/labels/demo.txt" #yolo output
COURT_PATH = f"{ROOTDIR}/lib/auto/court.pickle" #court output
WEIGHT_PATH = f"{ROOTDIR}/lib/auto/weight/model_weights_2023-09-07_14-49-59.h5" #weight
IMG_FOLDER = f"{ROOTDIR}/lib/auto/cropped_images" #cropped image file


def calculateExtrinsic(camera:CameraReader, court2D, court3D):
    config_file = f"{ROOTDIR}/Reader/{camera.brand}/config/{camera.hw_id}.cfg"
    cameraCfg = loadConfig(config_file)
    camera_ks = np.array(json.loads(cameraCfg['Other']['ks']))
    dist = np.array(json.loads(cameraCfg['Other']['dist']))
    nmtx = np.array(json.loads(cameraCfg['Other']['newcameramtx']))

    hf = Hfinder2(camera_ks=camera_ks, dist=dist, nmtx=nmtx, court2D=court2D, court3D=court3D)
    Hmtx = hf.getH()
    Kmtx = nmtx
    projection_mat = hf.getProjection_mat()
    extrinsic_mat = hf.getExtrinsic_mat()
    h2p = H2Pose(Kmtx, Hmtx)
    poses = h2p.getC2W()
    eye = h2p.getCamera().T
    eye[0][2] = abs(eye[0][2])
    # [TODO] Check if keys not in [Other] Section
    cameraCfg['Other']['poses'] = str(poses.tolist())
    cameraCfg['Other']['eye'] = str(eye.tolist())
    cameraCfg['Other']['hmtx'] = str(Hmtx.tolist())
    cameraCfg['Other']['projection_mat'] = str(projection_mat.tolist())
    cameraCfg['Other']['extrinsic_mat'] = str(extrinsic_mat.tolist())
    # msg = ID.SAVE_DEVICE_CONFIG
    logging.info('Poses:\n{}\n'.format(poses))
    logging.info('Eye:\n{}\n'.format(eye))
    logging.info('Hmtx:\n{}\n'.format(Hmtx))
    logging.info('projection_mat:\n{}\n'.format(projection_mat))
    logging.info('extrinsic_mat:\n{}\n'.format(extrinsic_mat))
    saveConfig(config_file, cameraCfg)

class ExtrinsicPage(QGroupBox):
    def __init__(self, cameras:list, big_image_size = QSize(1440, 1080)):
        super().__init__()

        self.big_image_size = big_image_size
        self.small_image_size = QSize(480, 360)
        self.cameras = cameras

        # two camera snapshot
        self.no_image = QPixmap(f"{ICONDIR}/no_camera.png").scaled(self.big_image_size)
        self.snapshots = [self.no_image, self.no_image]

        # setup UI
        self.setupUI()

        self.num_cameras = 4
        self.selected_num_cameras = 0

        self.original_sizes = []
        self.resize_ratio_x = 1
        self.resize_ratio_y = 1
        #up(0)/down(1) court
        self.court_type = 0
        self.nonauto = 0

    def hideEvent(self, event):
        logging.debug(f"{self.__class__.__name__}: hided.")

    def showEvent(self, event):
        self.clearManualExtrinsic()
        for i in range(self.selected_num_cameras):
            self.snapshot_list[i].setPixmap(self.snapshots[i].scaled(self.small_image_size))

        for i in range(self.selected_num_cameras):
            self.snapshot_list[i].show()
        for i in range(self.selected_num_cameras, self.num_cameras):
            self.snapshot_list[i].hide()

        self.gb_manual_extrinsic.hide()

        logging.debug(f"{self.__class__.__name__}: shown.")

    def setBackgroundService(self, service:SystemService):
        self.myService = service

    def setupUI(self):
        self.control_bar = self.getControlBar()
        self.snapshot_block = self.getSnapshot(number=len(self.cameras))
        self.gb_manual_extrinsic = self.setupManualExtrinsicPage()
        self.gb_manual_extrinsic.hide()

        left_container = QWidget()
        left_layout = QVBoxLayout()
        left_layout.addWidget(self.control_bar, stretch=1, alignment=(Qt.AlignVCenter | Qt.AlignLeft))
        left_layout.addWidget(self.snapshot_block, stretch=9)
        left_container.setLayout(left_layout)

        layout_main = QHBoxLayout()
        layout_main.addWidget(left_container, stretch=7)
        layout_main.addWidget(self.gb_manual_extrinsic, stretch=3)

        self.setLayout(layout_main)

    def getControlBar(self):
        container = QWidget()
        container_layout = QHBoxLayout()

        self.btn_home = QPushButton()
        self.btn_home.setText('回首頁')
        self.btn_home.setFixedSize(QSize(120, 50))
        self.btn_home.setStyleSheet('font: 24px')
        self.btn_home.clicked.connect(self.backhome)

        title_label = QLabel()
        title_label.setText("請點擊畫面以設定世界座標")
        title_label.setStyleSheet('font: 30px')

        container_layout.addWidget(self.btn_home, alignment=(Qt.AlignVCenter | Qt.AlignLeft))
        container_layout.addWidget(title_label, alignment=(Qt.AlignVCenter | Qt.AlignLeft))
        container.setLayout(container_layout)
        return container

    def getSnapshot(self, number=2):
        container = QWidget()
        container_layout = QGridLayout()

        self.snapshot_list = []
        for i in range(number):
            tmp_snapshot = QLabel()
            self.snapshot_list.append(tmp_snapshot)
            y = int(i / 2)
            x = i % 2
            container_layout.addWidget(tmp_snapshot, y * 2, x, alignment=Qt.AlignCenter)

        for i in range(number):
            self.snapshot_list[i].mousePressEvent = partial(self.pressEvent, i)
        container.setLayout(container_layout)
        return container

    def backhome(self):
        msg = MsgContract(MsgContract.ID.PAGE_CHANGE, value='CameraSystem')
        self.myService.sendMessage(msg)

    def setPixmap(self, images):
        self.snapshots = images

    def setData(self, data):
        self.snapshots = data['Pixmaps']
        self.selected_num_cameras = int(data['SelectedCameras'])
        self.original_sizes = data['Original_sizes']

    def pressEvent(self, index, event):
        self.snapshot_list[index].mousePressEvent = partial(self.court2DPressEvent, index)
        for i in range(self.selected_num_cameras):
            if i != index:
                self.snapshot_list[i].setHidden(True)
            else:
                self.snapshot_list[i].setPixmap(self.snapshots[i].scaled(self.big_image_size))

        self.gb_manual_extrinsic.show()
        self.camera = self.cameras[index]
        self.resize_ratio_x = self.original_sizes[index].width() / self.big_image_size.width()
        self.resize_ratio_y = self.original_sizes[index].height() / self.big_image_size.height()
        print("press ", index)

    def setupManualExtrinsicPage(self):
        gb = QGroupBox()
        layout = QGridLayout()

        # zoom image
        self.zoom_court = QLabel()
        self.zoom_court.setFixedSize(QSize(200, 200))
        self.zoom_court.setStyleSheet("border: 1px solid black;")
        self.zoom_court.mousePressEvent = self.zoomCourt3DPressEvent
        self.zoom_court_shown = False
        # hint image
        hint_image = QLabel()
        hint_image.setFixedSize(QSize(256, 64))
        hint_image.setPixmap(QPixmap(f"{ICONDIR}/court/hint_click_court.png").scaled(QSize(256, 64)))
        # corner coordinate
        self.ql_corner = QLabel()
        self.ql_corner.setStyleSheet(UIStyleSheet.ContentText)
        #checkbox
        self.checkbox1 = QCheckBox('下半場', self)
        self.checkbox1.clicked.connect(self.onCheckBox1Click)
        self.checkbox1.setStyleSheet('QCheckBox {spacing: 5px;font-size:25px;} QCheckBox::indicator {width:  33px;height: 33px;}')
        #checkbox
        self.checkbox2 = QCheckBox('手動調整', self)
        self.checkbox2.clicked.connect(self.onCheckBox2Click)
        self.checkbox2.setStyleSheet('QCheckBox {spacing: 5px;font-size:25px;} QCheckBox::indicator {width:  33px;height: 33px;}')

        # set court image
        self.court_image = QLabel()
        self.court_image.setFixedSize(QSize(400, 852))
        self.court_image.mousePressEvent = self.court3DPressEvent
        self.corners_3D = []
        self.corners_2D = []
        self.drawIdxOnCourt()
        # clear Button
        btn_clear = QPushButton()
        btn_clear.setFixedSize(UIComponentSize.ConfirmButton)
        btn_clear.setStyleSheet(UIStyleSheet.ResetButton)
        btn_clear.setText("重設")
        btn_clear.clicked.connect(self.clearManualExtrinsic)
        # calculate button
        btn_calculate = QPushButton()
        btn_calculate.setFixedSize(UIComponentSize.ConfirmButton)
        btn_calculate.setStyleSheet(UIStyleSheet.CalculateButton)
        btn_calculate.setText("確定")
        btn_calculate.clicked.connect(self.calculateExtrinsicMtx)

        layout.addWidget(self.ql_corner, 0, 4, 1, 1, Qt.AlignCenter)
        #layout.addWidget(hint_image, 1, 4, 1, 2, Qt.AlignCenter)
        #layout.addWidget(self.zoom_court, 1, 4, 2, 2, Qt.AlignCenter)
        layout.addWidget(self.court_image, 0, 0, 4, 3, Qt.AlignCenter)
        layout.addWidget(btn_clear, 4, 4, 1, 2, Qt.AlignCenter)
        layout.addWidget(btn_calculate, 5, 4, 1, 2, Qt.AlignCenter)
        layout.addWidget(self.checkbox1, 2, 4, 2, 2, Qt.AlignCenter)
        layout.addWidget(self.checkbox2, 3, 4, 2, 2, Qt.AlignCenter)
        gb.setLayout(layout)
        return gb

    def onCheckBox1Click(self):
        if self.checkbox1.isChecked():
            self.court_type = 1
            print('court_type = 1')
        else:
            self.court_type = 0
            print('court_type = 0')
    def onCheckBox2Click(self):
        if self.checkbox2.isChecked():
            self.nonauto = 1
            print('nonauto = 1')
        else:
            self.nonauto = 0
            print('nonauto = 0')

    def zoomCourt3DPressEvent(self, event):
        pass
    def drawIdxOnCourt(self):
        qpixmap = QPixmap(COURT_IMAGE).scaled(QSize(400, 852))
        painter = QPainter()
        painter.begin(qpixmap)

        # draw stars
        for x in CORNERS_ZOOM_X:
            for y in CORNERS_ZOOM_Y:
                painter.drawPixmap(x - STAR_SIZE // 2, y - STAR_SIZE // 2, \
                            QPixmap(STAR_IMAGE).scaled(QSize(STAR_SIZE, STAR_SIZE)))

        # draw points
        for idx, point in enumerate(self.corners_3D):
            point_x_idx = point[0]
            point_y_idx = point[1]
            painter.drawPixmap(CORNERS_2D_X[point_x_idx], CORNERS_2D_Y[point_y_idx],  QPixmap(f"{ICONDIR}/court/point{idx+1}.png").scaled(QSize(CORNER_SIZE, CORNER_SIZE)))
        painter.end()
        self.court_image.setPixmap(qpixmap)

    # Court 3D coordinate Manual setup
    def court3DPressEvent(self, event):
        if(self.nonauto == 0):
          if event.buttons() == Qt.LeftButton:
              # Read court map
              with open(COURT_PATH, "rb") as file:
                  court_data = pickle.load(file)
                  print('court_data')
                  print(court_data)
  
              if(self.court_type == 0): #upcourt
                self.corners_3D = []
                zero = [9,0],[8,1]
                one = [0,0],[1,1]
                two = [4,1],[5,1]
                three =  [4,2],[5,2],[5,3],[4,3]
                four =  [4,4],[5,4]
                five = [2,1],[3,1]
                six = [1,2],[1,3]
                seven = [2,2],[3,2],[3,3],[2,3]
                eight = [1,4],[1,5]
                nine = [2,4],[3,4],[3,5],[2,5]
                #ten =
                #eleven =
                twelve = [6,1],[7,1]
                thirdteen = [6,2],[7,2],[7,3],[6,3]
                fourteen = [8,2],[8,3]
                fifteen = [6,4],[7,4],[7,5],[6,5]
                sixteen = [8,4],[8,5]
                #seventeen =
                #eighteen =
                merged_list = []
                for i in range(len(court_data)):
                  for j in range(len(court_data[0])):
                      if(court_data[i][j]!=[0,0]):
                          if(i==0 and j == 4):
                              merged_list.extend(zero)
                          if(i==0 and j == 0):
                              merged_list.extend(one)
                          if(i==0 and j == 2):
                              merged_list.extend(two)
                          if(i==1 and j == 2):
                              merged_list.extend(three)
                          if(i==2 and j == 2):
                              merged_list.extend(four)
                          if(i==0 and j == 1):
                              merged_list.extend(five)
                          if(i==1 and j == 0):
                              merged_list.extend(six)
                          if(i==1 and j == 1):
                              merged_list.extend(seven)
                          if(i==2 and j == 0):
                              merged_list.extend(eight)
                          if(i==2 and j == 1):
                              merged_list.extend(nine)
                          if(i==0 and j == 3):
                              merged_list.extend(twelve)
                          if(i==1 and j == 3):
                              merged_list.extend(thirdteen)
                          if(i==1 and j == 4):
                              merged_list.extend(fourteen)
                          if(i==2 and j == 3):
                              merged_list.extend(fifteen)
                          if(i==2 and j == 4):
                              merged_list.extend(sixteen)
                      print(merged_list)
                self.corners_3D = merged_list
              elif(self.court_type == 1): #downcourt
                self.corners_3D = []
                zero = [0,11],[1,10]
                one = [9,11],[8,10]
                two = [5,10],[4,10]
                three =  [5,9],[4,9],[4,8],[5,8]
                four =  [5,7],[4,7]
                five = [7,10],[6,10]
                six = [8,9],[8,8]
                seven = [7,9],[6,9],[6,8],[7,8]
                eight = [8,7],[8,6]
                nine = [7,7],[6,7],[6,6],[7,6]
                #ten =
                #eleven =
                twelve = [3,10],[2,10]
                thirdteen = [3,9],[2,9],[2,8],[3,8]
                fourteen = [1,9],[1,8]
                fifteen = [3,7],[2,7],[2,6],[3,6]
                sixteen = [1,7],[1,6]
                #seventeen =
                #eighteen =
                merged_list = []
                for i in range(len(court_data)):
                  for j in range(len(court_data[0])):
                      if(court_data[i][j]!=[0,0]):
                          if(i==0 and j == 4):
                              merged_list.extend(zero)
                          if(i==0 and j == 0):
                              merged_list.extend(one)
                          if(i==0 and j == 2):
                              merged_list.extend(two)
                          if(i==1 and j == 2):
                              merged_list.extend(three)
                          if(i==2 and j == 2):
                              merged_list.extend(four)
                          if(i==0 and j == 1):
                              merged_list.extend(five)
                          if(i==1 and j == 0):
                              merged_list.extend(six)
                          if(i==1 and j == 1):
                              merged_list.extend(seven)
                          if(i==2 and j == 0):
                              merged_list.extend(eight)
                          if(i==2 and j == 1):
                              merged_list.extend(nine)
                          if(i==0 and j == 3):
                              merged_list.extend(twelve)
                          if(i==1 and j == 3):
                              merged_list.extend(thirdteen)
                          if(i==1 and j == 4):
                              merged_list.extend(fourteen)
                          if(i==2 and j == 3):
                              merged_list.extend(fifteen)
                          if(i==2 and j == 4):
                              merged_list.extend(sixteen)
                      print(merged_list)
                self.corners_3D = merged_list

        else:
            merged_list = self.corners_3D
            print(merged_list)
            if event.buttons() == Qt.RightButton:
              mouse_x = event.pos().x()
              mouse_y = event.pos().y()
              x_array = np.asarray(CORNERS_ZOOM_X)
              y_array = np.asarray(CORNERS_ZOOM_Y)
              self.zoom_x_idx = (np.abs(x_array-mouse_x)).argmin()
              self.zoom_y_idx = (np.abs(y_array-mouse_y)).argmin()
              corner_idx = self.zoom_x_idx*len(CORNERS_ZOOM_Y) + self.zoom_y_idx
              corner_type = CORNERS_TYPE[corner_idx]
              if(self.court_type == 0):
                zero = [9,0],[8,1]
                one = [0,0],[1,1]
                two = [4,1],[5,1]
                three =  [4,2],[5,2],[5,3],[4,3]
                four =  [4,4],[5,4]
                five = [2,1],[3,1]
                six = [1,2],[1,3]
                seven = [2,2],[3,2],[3,3],[2,3]
                eight = [1,4],[1,5]
                nine = [2,4],[3,4],[3,5],[2,5]
                twelve = [6,1],[7,1]
                thirdteen = [6,2],[7,2],[7,3],[6,3]
                fourteen = [8,2],[8,3]
                fifteen = [6,4],[7,4],[7,5],[6,5]
                sixteen = [8,4],[8,5]
                zoom_dict = {
                  (0, 0): one,
                  (1, 0): five,
                  (2, 0): two,
                  (3, 0): twelve,
                  (4, 0): zero,
                  (0, 1): six,
                  (1, 1): seven,
                  (2, 1): three,
                  (3, 1): thirdteen,
                  (4, 1): fourteen,
                  (0, 2): eight,
                  (1, 2): nine,
                  (2, 2): four,
                  (3, 2): fifteen,
                  (4, 2): sixteen,
                }
              else:
                zero = [0,11],[1,10]
                one = [9,11],[8,10]
                two = [5,10],[4,10]
                three =  [5,9],[4,9],[4,8],[5,8]
                four =  [5,7],[4,7]
                five = [7,10],[6,10]
                six = [8,9],[8,8]
                seven = [7,9],[6,9],[6,8],[7,8]
                eight = [8,7],[8,6]
                nine = [7,7],[6,7],[6,6],[7,6]
                twelve = [3,10],[2,10]
                thirdteen = [3,9],[2,9],[2,8],[3,8]
                fourteen = [1,9],[1,8]
                fifteen = [3,7],[2,7],[2,6],[3,6]
                sixteen = [1,7],[1,6]
                zoom_dict = {
                  (4, 5): one,
                  (3, 5): five,
                  (2, 5): two,
                  (1, 5): twelve,
                  (0, 5): zero,
                  (4, 4): six,
                  (3, 4): seven,
                  (2, 4): three,
                  (1, 4): thirdteen,
                  (0, 4): fourteen,
                  (4, 3): eight,
                  (3, 3): nine,
                  (2, 3): four,
                  (1, 3): fifteen,
                  (0, 3): sixteen,
                }
              key = (self.zoom_x_idx, self.zoom_y_idx)
              if key in zoom_dict:
                merged_list = [i for i in merged_list if i not in zoom_dict[key]]
              self.corners_3D = merged_list

        self.zoom_court_shown = False
        self.drawIdxOnCourt()

    def calculateExtrinsicMtx(self):
        if len(self.corners_2D) != len(self.corners_3D) or len(self.corners_3D) < 4:
            self.ql_corner.setText("<font color=red>參數錯誤(數量不同或小於4個參考點)</font>")
            print(len(self.corners_2D) )
            print(len(self.corners_3D) )
            return
        self.ql_corner.setText("<font color=blue>計算參數中</font>")

        court3D = []
        court2D = []
        court2D_tmp = self.corners_2D.copy()
        for point in court2D_tmp:
            point_x = point[0] * self.resize_ratio_x # * RESIZE_RATIO_W
            point_y = point[1] * self.resize_ratio_y # * RESIZE_RATIO_H
            court2D.append([point_x, point_y])
        for point_idx in self.corners_3D:
            actual_x_idx = point_idx[0]
            actual_y_idx = point_idx[1]
            point = [CORNERS_3D_X[actual_x_idx], CORNERS_3D_Y[actual_y_idx]]
            court3D.append(point)
        calculateExtrinsic(self.camera, court2D=court2D, court3D=court3D)
        self.clearManualExtrinsic()
        self.ql_corner.setText("設定成功")
        for i in range(self.selected_num_cameras):
            self.snapshot_list[i].setPixmap(self.snapshots[i].scaled(self.small_image_size))
            self.snapshot_list[i].setHidden(False)
        self.gb_manual_extrinsic.hide()

    def clearManualExtrinsic(self):
        self.corners_3D = []
        self.corners_2D = []
        self.drawIdxOnCourt()
        for i in range(self.selected_num_cameras):
            if(i==0):
              self.snapshot_list[i].setPixmap(QPixmap(f"{ROOTDIR}/UI/CameraSetting/test2.jpg").scaled(self.big_image_size))
            else:
              self.snapshot_list[i].setPixmap(self.snapshots[i].scaled(self.big_image_size))
            self.snapshot_list[i].mousePressEvent = partial(self.pressEvent, i)
        self.ql_corner.setText("")
        self.zoom_court_shown = False
        self.zoom_court.clear()

    def court2DPressEvent(self, index, event):
        if event.buttons() == Qt.LeftButton:
            #yolo&mapping&intersection
            os.chdir(f'{ROOTDIR}/lib/auto/yolov7')
            self.snapshot_list[index].pixmap().save(f'{IMG_PATH}','JPG')
            subprocess.run(['python3', f'detect.py', '--weights', 'best.pt', '--source', f'{IMG_PATH}', '--save-txt', '--project', f'../yolo_output', '--name', 'exp', '--exist-ok'])

            MAPPING_TXT_PATH = YOLO_TXT_PATH[:-4]+"_mapping.txt"
            AFTER_MAPPING_TXT_PATH = YOLO_TXT_PATH[:-4]+"_mapping_after.txt"
            mapping(IMG_PATH,YOLO_TXT_PATH)
            court_mapping(IMG_PATH,MAPPING_TXT_PATH,COURT_PATH)
            points_mapping(IMG_PATH,MAPPING_TXT_PATH,COURT_PATH)
            #intersection_path = corner(IMG_PATH,AFTER_MAPPING_TXT_PATH)
            intersection_path = cornerDL(IMG_PATH,AFTER_MAPPING_TXT_PATH,WEIGHT_PATH,IMG_FOLDER)

            fl = open(intersection_path, 'r')
            count = 0
            for string in fl:
                  points = re.findall(r'\((\d+), (\d+)\)', string)
                  if(count == 10 or count == 11 or count == 17 or count == 18):
                    for point in points:
                        x, y = map(int, point)
                        print(f"Point: ({x}, {y})")
                        if [x, y] in self.corners_2D:
                          return
                        self.corners_2D.append([x, y])
                    print("==================")
                  else:
                    for point in points:
                        x, y = map(int, point)
                        print(f"Point: ({x}, {y})")
                        if [x, y] in self.corners_2D:
                          return
                        self.corners_2D.append([x, y])
                    print("==================")
                  count+=1

            qpixmap = self.snapshot_list[index].pixmap()
            painter = QPainter()
            painter.begin(qpixmap)
            for idx, point in enumerate(self.corners_2D):
                painter.drawPixmap(point[0], point[1], \
                        QPixmap(f"{ICONDIR}/court/point{idx+1}.png").scaled(QSize(CORNER_SIZE, CORNER_SIZE)))
            painter.end()
            self.snapshot_list[index].setPixmap(qpixmap)

            yolo_file = f"{ROOTDIR}/lib/auto/yolo_output/exp/labels"
            for file in os.scandir(yolo_file):
                os.remove(file.path)