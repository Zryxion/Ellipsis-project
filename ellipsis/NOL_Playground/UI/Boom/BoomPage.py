import sys
import json
import os
import logging
import ast
import time
import queue
import shutil
import threading
from datetime import datetime
from functools import partial
from UISettings import *
import paho.mqtt.client as mqtt
from vidgear.gears import WriteGear
from turbojpeg import TurboJPEG
from Services import SystemService, MsgContract
from message import *
from common import insertById, loadConfig, saveConfig, setIntrinsicMtx
from nodes import CameraReader
from gi.repository import GLib, Gst, Tcam

from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QComboBox, QWidget, QGridLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QRadioButton, QLayout
from PyQt5.QtCore import QSize, QThread, pyqtSignal, pyqtSlot, QTimer, QLineF
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor
from PyQt5 import QtTest
from PyQt5.Qt import *

DIRNAME = os.path.dirname(os.path.abspath(__file__))
ROOTDIR = os.path.dirname(os.path.dirname(DIRNAME))
ICONDIR = f"{DIRNAME}/icon"

sys.path.append(f"{ROOTDIR}/ServeMachine/PC")
from MachineClient import MachineClient

sys.path.append(f"{ROOTDIR}/EllipseDetect")
import Thres_function as ellipsedetect

class BoomPage(QGroupBox):
    drawImageSignal = pyqtSignal(int, QPixmap)
    detectSignal = pyqtSignal(list, tuple, int)

    def __init__(self, camera_widget, broker_ip, cfg, cameras:list):
        super().__init__()
        self.prevtime = time.time()
        self.curtime = time.time()
        self.runtime = 0
        self.interval = 5
        self.shootingSystemOn = False

        self.cameraNumber = 2
        self.camera_widget = camera_widget
        self.broker_ip = broker_ip
        self.cfg = cfg
        self.cameras = cameras

        self.image_size = QSize(800, 600)

        # for ellipse detection
        self.detectSignal.connect(self.updateEllipseCoords)
        self.ellipse_coords = [None, None]
        self.midpoint = [None, None]

        self.detector = []

        self.velo = f"Velocity: {0}"
        self.yaw = f"Yaw: {0}"
        self.pitch = f"Pitch: {0}"
        self.tooBig = f" "
        self.pitchOut = f" "
        self.PrevRec_Oversize = False
        self.MachineCal = [0,0,0]
        # self.Adj = [0,0,0]

        self.machineClient = MachineClient("140.113.213.131")
        self.machineStatus = self.machineClient.connect("MachineA")

        self.t = QTimer(self)
        self.t2 = QTimer(self)
        self.t.timeout.connect(self.updatePrev)
        self.t2.timeout.connect(self.shootingSystem)

        self.flag = False

    def updateEllipseCoords(self, ellipse_coords, midpoint, index):
        self.ellipse_coords[index] = ellipse_coords
        self.midpoint[index] = midpoint
        # print(index, ellipse_coords, midpoint)

    def hideEvent(self, event):
        logging.debug(f"{self.__class__.__name__}: hided.")
        for detector in self.detector:
            detector.stop()
        self.ellipse_coords = [None, None]
        self.midpoint = [None, None]
        self.camera_widget.stopStreaming()
        self.deleteUI()

    def showEvent(self, event):
        logging.debug(f"{self.__class__.__name__}: shown.")
        for i in range(self.cameraNumber):
            detector = ellipsedetect.DetectThread(self.broker_ip, self.cameras[i], self.detectSignal, i)
            self.detector.append(detector)
        for detector in self.detector:
            detector.start()
        self.setupUI()
        self.camera_widget.startStreaming()

    def setBackgroundService(self, service:SystemService):
        self.myService = service

    def setupUI(self):
        # main layout
        self.layout_main = QGridLayout()

        # input shooting machine coordinates
        self.lineX = QLineEdit(self)
        self.lineY = QLineEdit(self)
        self.lineZ = QLineEdit(self)
        self.lineX.setText('0')
        self.lineY.setText('-2.25')
        self.lineZ.setText('1.5')

        # output boxes
        self.output_box1 = QLineEdit(self) # velocity
        self.output_box2 = QLineEdit(self) # yaw
        self.output_box3 = QLineEdit(self) # pitch
        self.output_box4 = QLineEdit(self) # tooBig
        self.output_box5 = QLineEdit(self) # pitchOut
        self.output_box6 = QLineEdit(self) # Time

        self.output_box1.setFrame(False)
        self.output_box2.setFrame(False)
        self.output_box3.setFrame(False)
        self.output_box4.setFrame(False)
        self.output_box5.setFrame(False)
        self.output_box6.setFrame(False)

        self.coords = self.getCoordsUI()
        self.time_btn = self.time_range()
        self.control_bar = self.getControlBar()
        self.pic_btn = self.getPicBtn()
        self.camera_widget.initWidget(2, self.image_size)
        self.output_box = self.printOutput()
        # self.calibration = self.calibrate()

        # self.coords.move(500, 0)

        # can turn off FPS display
        # self.camera_widget.toggleFPS()

        # connect signals
        self.camera_widget.getImageSignal.connect(self.receiveImage)
        self.drawImageSignal.connect(self.camera_widget.trueDrawImage)

        self.layout_main.addWidget(self.coords, 0, 0, Qt.AlignLeft)
        # self.layout_main.addWidget(self.calibration, 0, 1, Qt.AlignRight)
        self.layout_main.addWidget(self.time_btn, 0, 0, Qt.AlignRight)
        self.layout_main.addWidget(self.camera_widget, 1, 0, Qt.AlignCenter)
        
        self.layout_main.addWidget(self.output_box, 2, 0, Qt.AlignLeft)
        self.layout_main.addWidget(self.pic_btn, 2, 0, Qt.AlignCenter)
        self.layout_main.addWidget(self.control_bar, 2, 0, Qt.AlignRight)

        # self.layout_main.addWidget(self.start_btn, 2, 1, Qt.AlignCenter)

        self.setLayout(self.layout_main)

    def deleteUI(self):
        # disconnect signals
        try:
            self.camera_widget.getImageSignal.disconnect(self.receiveImage)
            self.drawImageSignal.disconnect(self.camera_widget.trueDrawImage)
        except TypeError:
            # I don't know why it will be ok when switching page,
            #  but it will throw error when closing the application.
            pass

        self.layout_main.removeWidget(self.camera_widget)
        while self.layout_main.count():
            item = self.layout_main.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.layout_main.deleteLater()

    def getControlBar(self):
        container = QWidget()
        container_layout = QVBoxLayout()

        btn_home = QPushButton()
        btn_home.setText('回首頁')
        btn_home.setFixedSize(QSize(160, 60))
        btn_home.setStyleSheet('font: 24px')
        btn_home.clicked.connect(self.backhome)

        container_layout.addWidget(btn_home)
        container_layout.setContentsMargins(0,0,120,20)
        container.setLayout(container_layout)
        return container
    
    def getCoordsUI(self):
        container = QWidget()
        container_layout = QHBoxLayout()

        # labels

        nameLabelX = QLabel(self)
        nameLabelX.setText('X:')
        nameLabelX.setStyleSheet('font: 24px')

        nameLabelY = QLabel(self)
        nameLabelY.setText('Y:')
        nameLabelY.setStyleSheet('font: 24px')


        nameLabelZ = QLabel(self)
        nameLabelZ.setText('Z:')
        nameLabelZ.setStyleSheet('font: 24px')


        container_layout.addWidget(nameLabelX)
        container_layout.addWidget(self.lineX)
        container_layout.addWidget(nameLabelY)
        container_layout.addWidget(self.lineY)
        container_layout.addWidget(nameLabelZ)
        container_layout.addWidget(self.lineZ)

        # button
        
        btn_getStartPoint = QPushButton()
        btn_getStartPoint.setText('config')
        btn_getStartPoint.setFixedSize(QSize(160, 40))
        btn_getStartPoint.setStyleSheet('font: 24px')
        btn_getStartPoint.clicked.connect(self.toggleTraj) #change back to traj

        container_layout.addWidget(btn_getStartPoint)
        container_layout.setSpacing(30)
        container_layout.addStretch()
        
        container_layout.setContentsMargins(120,0,0,0)
        container.setLayout(container_layout)
        return container
        
    def time_range(self):
        container = QWidget()
        container_layout = QHBoxLayout()

        # radio buttons
        radioButton = QRadioButton("5s")
        radioButton.setChecked(True)
        radioButton.interval = 5
        radioButton.clicked.connect(self.rbOnClicked)
        container_layout.addWidget(radioButton)

        radioButton = QRadioButton("10s")
        radioButton.setChecked(False)
        radioButton.interval = 10
        radioButton.clicked.connect(self.rbOnClicked)
        container_layout.addWidget(radioButton)

        radioButton = QRadioButton("15s")
        radioButton.setChecked(False)
        radioButton.interval = 15
        radioButton.clicked.connect(self.rbOnClicked)
        container_layout.addWidget(radioButton)

        radioButton = QRadioButton("20s")
        radioButton.setChecked(False)
        radioButton.interval = 20
        radioButton.clicked.connect(self.rbOnClicked)
        container_layout.addWidget(radioButton)
    
        container_layout.setContentsMargins(0, 0, 120, 0)
        container_layout.setSpacing(10)
        container.setLayout(container_layout)
        return container
    
    def rbOnClicked(self):
        radioButton = self.sender()
        if radioButton.isChecked():
            self.interval = radioButton.interval
            # print("Country is %s" % (radioButton.country))
    
    # def angleplus(self):
    #     self.Adj[1] += round(0.2,2)
    #     self.updateOutput()

    # def angleminus(self):
    #     self.Adj[1] -= round(0.2,2)
    #     self.updateOutput()

    # def pitchplus(self):
    #     self.Adj[2] += round(0.2,2)
    #     self.updateOutput()

    # def pitchminus(self):
    #     self.Adj[2] -= round(0.2,2)
    #     self.updateOutput()
    
    
    def getStartPoint(self):
        xpoint = float(self.lineX.text())
        ypoint = float(self.lineY.text())
        zpoint = float(self.lineZ.text())

        startpoint = [xpoint, ypoint, zpoint]

        return startpoint
        
    
    def getPicBtn(self):
        container = QWidget()
        container_layout = QHBoxLayout()

        btn_home = QPushButton()
        btn_home.setText('拍照')
        btn_home.setFixedSize(QSize(160, 60))
        btn_home.setStyleSheet('font: 24px')
        btn_home.clicked.connect(self.toggleSnapshot)
        # contrain        

        btn_start = QPushButton()
        btn_start.setText('Start')
        btn_start.setFixedSize(QSize(160, 60))
        btn_start.setStyleSheet('font: 24px')
        btn_start.clicked.connect(self.toggleLive)

        container_layout.addWidget(btn_home)
        container_layout.addWidget(btn_start)
        container_layout.setContentsMargins(0,0,0,20)
        container.setLayout(container_layout)
        return container

    def toggleSnapshot(self):
        self.camera_widget.takeSnapshot()

    def toggleTraj(self):
        output = list(self.camera_widget.getTrajData(self.getStartPoint()))
        self.MachineCal,self.Rec_Oversize = output[:-1],output[-1]
        
        
        self.MachineCal[0] =  round(self.MachineCal[0]/160 * 100 ) + 1
        self.MachineCal[2] = self.MachineCal[2] + 13
        self.MachineCal[1] = self.MachineCal[1] - 4

        self.updateOutput()

        if not self.machineStatus: return #if machine status is not connected -> exit

        if not self.Rec_Oversize and not self.PrevRec_Oversize and self.MachineCal[2] in range(0,30):
            self.machineClient.setSpeed(self.MachineCal[0] ) #// 9~45  and tje unit is %of160km/hr 
            self.machineClient.setYaw(self.MachineCal[2]) #// yaw range is from 0~30. mid point is 12 (left - right)
            time.sleep(2) # time for machine to move

            self.machineClient.setPitch(int(self.MachineCal[1])) #// pitch is -16 ~ 20 mid = 0 (up - down)
            self.machineClient.serve(1, 500)

    def shootingSystem(self):
        print('SHOOT')
        #===========================
        # self.predTargetpoint = self.curTargetpoint
        # self.predTargetpoint[0] += self.Xspeed * 2.5 # 2s for callibration
        # # print(Xspeed)
        # if self.predTargetpoint[0] < -1.159:
        #     self.predTargetpoint[0] =  -1.159 * 2 - self.predTargetpoint[0]
        # if self.predTargetpoint[0] > 1.159:
        #     self.predTargetpoint[0] =  1.159 * 2 - self.predTargetpoint[0]

        # # print(Xspeed)
        # # self.shootingSystem() #Machine Shoot

        # if not self.Rec_Oversize and not self.PrevRec_Oversize:
        #     self.t.timeout.connect(self.updatePrev)
        #     self.t2.timeout.connect(self.shootingSystem)
        #     self.t.start(100)
        #     self.t2.start(200)
        #     return
        #============================
        self.predTargetpoint = self.curTargetpoint
        output = list(self.camera_widget.getMachineConfig(self.getStartPoint(),self.predTargetpoint)) # get machine configuration
        self.MachineCal = output
        
        
        self.MachineCal[0] =  round(self.MachineCal[0]/160 * 100 ) + 1
        self.MachineCal[2] = self.MachineCal[2] + 13
        self.MachineCal[1] = self.MachineCal[1] - 4

        self.updateOutput()
        # y = ax   y is km/h  and x is the setting numger  a is 1.309 

        if not self.machineStatus: return #if machine status is not connected -> exit

        if not self.Rec_Oversize and self.MachineCal[2] in range(0,30):
            self.machineClient.setSpeed(self.MachineCal[0] ) #// 9~45  and tje unit is %of160km/hr 
            self.machineClient.setYaw(self.MachineCal[2]) #// yaw range is from 0~30. mid point is 12 (left - right)
            time.sleep(2) # time for machine to move

            self.machineClient.setPitch(int(self.MachineCal[1])) #// pitch is -16 ~ 20 mid = 0 (up - down)
            self.machineClient.serve(1, 500)
            
    def updateOutput(self):
        # print(self.MachineCal + self.Adj)
        # Velocity, Yaw, Pitch = [(x + y) for x, y in zip(self.MachineCal,self.Adj)]
        self.pitchOut = ""
        Velocity, Pitch, Yaw = self.MachineCal
        if self.Rec_Oversize is True :
            self.tooBig = "RECTANGLE ERROR"
        elif self.Rec_Oversize is False:
            self.tooBig = "RECTANGLE OK"

        # pitch < -20 or pitch > 20
        if (Yaw + 12 < 0 or Yaw + 12 > 30):
            self.pitchOut = "Yaw ERROR"
        else:
            self.pitchOut = "Yaw OK"
        
        self.velo = f"Velocity: {Velocity}" #.format()
        self.yaw = f"Yaw: {Yaw}"
        self.pitch = f"Pitch: {round(Pitch,3)}"
        self.output_box1.setText(self.velo)
        self.output_box2.setText(self.yaw)
        self.output_box3.setText(self.pitch)
        self.output_box4.setText(self.tooBig)
        self.output_box5.setText(self.pitchOut)
        self.output_box6.setText(f'Runtime : {round(self.runtime,2)} / {self.interval}')

    def printOutput(self):
        container = QWidget()
        container_layout = QVBoxLayout()

        self.output_box1.setText(self.velo)
        self.output_box2.setText(self.yaw)
        self.output_box3.setText(self.pitch)
        self.output_box4.setText(self.tooBig)
        self.output_box5.setText(self.pitchOut)
        self.output_box6.setText(f'')

        container_layout.addWidget(self.output_box1)
        container_layout.addWidget(self.output_box2)
        container_layout.addWidget(self.output_box3)
        container_layout.addWidget(self.output_box4)
        container_layout.addWidget(self.output_box5)
        container_layout.addWidget(self.output_box6)
        # setContentsMargins(left, top, right, bottom)
        container_layout.setContentsMargins(120,0,0,20)
        
        container.setLayout(container_layout)
        return container

    def getLiveBtn(self):
        container = QWidget()
        container_layout = QHBoxLayout()


        container.setLayout(container_layout)
        return container
    
    def updatePrev(self):
        self.curTargetpoint,self.Rec_Oversize = self.camera_widget.get3DPoint(self.ellipse_coords,self.midpoint) # get current target 3d point
        # if int(self.runtime) % 2 == 0:
        self.Xspeed = (self.curTargetpoint[0] - self.prevTargetpoint[0])/1 # count x speed
        self.prevTargetpoint = self.curTargetpoint
        self.PrevRec_Oversize = self.Rec_Oversize
        print('UPDATED')

    def flagtog(self):
        self.flag = not self.flag#new
        self.toggleLive()

    def toggleLive(self):
        self.prevtime = time.time()
        # self.flag = not self.flag#new

        # set previous target 3d point when starts the system
        self.prevTargetpoint,self.Rec_Oversize = self.camera_widget.get3DPoint(self.ellipse_coords,self.midpoint)
        # self.updatePrev()
        # #new
        if not self.flag:
            self.t.start(1000)
            self.t2.start(int(self.interval)*1000)
            self.flag = not self.flag
        else:
            self.t.stop()
            self.t2.stop()
            self.flag = not self.flag
    
    @pyqtSlot(int, QPixmap)
    def receiveImage(self, camera_id: int, image: QPixmap):
        try:
            ellipse_coords = self.ellipse_coords[camera_id]
        except:
            ellipse_coords = []
            
        if ellipse_coords is not None:
            painter = QPainter()
            painter.begin(image)
            color = QColor()
            color.setRgb(0,255,0,50)
            painter.setPen(QPen(color, 20))
            for i in range(len(ellipse_coords)):
                painter.drawLine(QLineF(ellipse_coords[i][0], ellipse_coords[i][1], ellipse_coords[(i+1)%len(ellipse_coords)][0], ellipse_coords[(i+1)%len(ellipse_coords)][1]))
            painter.end()
            # t = QTimer()
            # t.timeout.connect(self.detectSpeed)
            # t.start(2000)

            # Pushbottom 
            # def detectSpeed(self):
            #     a =sdf
            #     asdfsadf

            #     if flag == False :
            #         print("FINISHED")
            #     else:
            #         t.start(2000)

            # Check if shooting system is on
            # if self.shootingSystemOn: 
            #     # Start counting runtime
            #     self.curtime = time.time()
            #     diff_time = self.curtime - self.prevtime
            #     self.prevtime = self.curtime
            #     self.runtime += diff_time
                
            #     self.updateOutput()
                
            #     self.curTargetpoint,self.Rec_Oversize = self.camera_widget.get3DPoint(self.ellipse_coords,self.midpoint) # get current target 3d point
            #     # if int(self.runtime) % 2 == 0:
            #     Xspeed = (self.curTargetpoint[0] - self.prevTargetpoint[0])/diff_time # count x speed
            #     self.prevTargetpoint = self.curTargetpoint

            #     # Check if target runtime is achieved
            #     if self.runtime > self.interval :
            #         self.predTargetpoint = self.curTargetpoint
            #         # self.predTargetpoint[0] += Xspeed * 4 # 2s for callibration
            #         print(Xspeed)
            #         if self.predTargetpoint[0] < -1.159:
            #            self.predTargetpoint[0] =  -1.159 * 2 - self.predTargetpoint[0]
            #         if self.predTargetpoint[0] > 1.159:
            #            self.predTargetpoint[0] =  1.159 * 2 - self.predTargetpoint[0]

            #         print(Xspeed)
            #         self.shootingSystem() #Machine Shoot

            #         if not self.Rec_Oversize and not self.PrevRec_Oversize:
            #             self.runtime = 0           
            #     self.PrevRec_Oversize = self.Rec_Oversize
            
        self.drawImageSignal.emit(camera_id, image)

    def backhome(self):
        msg = MsgContract(MsgContract.ID.PAGE_CHANGE, value='Home')
        self.myService.sendMessage(msg)
