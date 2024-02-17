import os
import sys
import logging
import threading
import json
import queue
import paho.mqtt.client as mqtt
import time
from datetime import datetime
import cv2
import numpy as np
from enum import Enum, auto
from turbojpeg import TurboJPEG
import shutil
import ast
from vidgear.gears import WriteGear

from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QComboBox, QWidget, QGridLayout, QLabel, QPushButton, QHBoxLayout, QSpinBox, QScrollArea, QDialog, QDoubleSpinBox
from PyQt5.QtCore import QSize, QThread, pyqtSignal, pyqtSlot, QTimer
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.Qt import *
from PyQt5.QtMultimedia import QSound

import gi
gi.require_version("Tcam", "0.1")
gi.require_version("Gst", "1.0")

from gi.repository import GLib, Gst, Tcam

DIRNAME = os.path.dirname(os.path.abspath(__file__))
ROOTDIR = os.path.dirname(os.path.dirname(DIRNAME))
ICONDIR = f"{ROOTDIR}/UI/icon"

sys.path.append(f"{ROOTDIR}/UI")
from UISettings import *
from Services import SystemService, MsgContract

sys.path.append(f"{ROOTDIR}/lib")
from nodes import CameraReader
from frame import Frame
from message import *
from common import insertById, loadConfig, saveConfig, setIntrinsicMtx

# bitrate control, replace None with:
# 2 mb/s : "2M"
# 500 kb/s : "500K"
CONSTANT_BITRATE = None

class FirstFrameState(Enum):
    NOT_READY = auto()
    KEEP = auto()
    DISCARD = auto()

class ClickLabel(QLabel):

    clicked = pyqtSignal(str)

    def __init__(self, imagename):
        super().__init__()
        self.imagename = imagename

    def mousePressEvent(self, event):
        self.clicked.emit(self.imagename)
        QLabel.mousePressEvent(self, event)

class CameraSystem(QGroupBox):
    def __init__(self, broker_ip, cfg, cameras:list, camera_widget):
        super().__init__()

        # initalize Service
        self.myService = None
        self.cameras = cameras
        self.broker = broker_ip
        self.cfg = cfg
        self.camera_widget = camera_widget
        self.isRecording = False
        self.record_done_cnt = 0
        self.snapshot_dir_path = os.path.join(ROOTDIR, "snapshot")
        os.makedirs(self.snapshot_dir_path, exist_ok=True)
        self.chessboard_path = f"{ROOTDIR}/Reader/{self.cameras[0].brand}/intrinsic_data/{self.cameras[0].hw_id}"
        os.makedirs(self.chessboard_path, exist_ok=True)

        self.snapshot = []
        self.image_size = QSize(480, 360)

        self.preview_fps = 30

        # always 4 in NOL_Playground
        self.num_cameras = 5
        # self.num_cameras = len(self.cameras)

        self.blockSize = 10


        # for first frame
        self.first_frame_time = [0] * self.num_cameras
        self.first_frame_cnt = 0

        # get the serial numbers of existing camera
        Gst.init(sys.argv)
        source = Gst.ElementFactory.make("tcambin")
        self.serials = source.get_device_serials_backend()
        # logging.debug(f"serials from cameraSystem: {self.serials}")

    def showEvent(self, event):
        logging.debug(f"{self.__class__.__name__}: shown.")
        self.setupUI()

        self.checkMaxRecord()
        self.camera_widget.startStreaming()

    def hideEvent(self, event):
        logging.debug(f"{self.__class__.__name__}: hided.")
        self.camera_widget.stopStreaming()
        self.deleteUI()

    def setBackgroundService(self, service:SystemService):
        self.myService = service

    def setupUI(self):
        self.camera_widget.initWidget(self.num_cameras, self.image_size)
        # 取得控制按鈕
        self.control_panel = self.getControlPanel()

        # 內參回首頁按鈕
        self.btn_home = QPushButton()
        self.btn_home.setText('回首頁')
        self.btn_home.setFixedSize(QSize(120, 50))
        self.btn_home.setStyleSheet('font: 24px')
        self.btn_home.clicked.connect(self.showHome)

        # 內參區塊
        self.creatIntrinsicGroupBox()

        self.layout_main = QHBoxLayout()
        self.layout_main.addWidget(self.control_panel, 1, alignment=Qt.AlignHCenter)
        self.layout_main.addWidget(self.btn_home, alignment=Qt.AlignTop)
        self.layout_main.addWidget(self.camera_widget, 5, alignment=Qt.AlignHCenter)
        self.layout_main.addWidget(self.gbox_camera_intrinsic, alignment=Qt.AlignCenter)

        self.btn_home.hide()
        self.gbox_camera_intrinsic.hide()

        self.setLayout(self.layout_main)

    def deleteUI(self):
        # notice here!!
        self.layout_main.removeWidget(self.camera_widget)
        while self.layout_main.count():
            item = self.layout_main.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.layout_main.deleteLater()

    def getControlPanel(self):
        container = QWidget()
        container_layout = QVBoxLayout()

        # 回選單按鈕
        self.btn_menu = QPushButton()
        self.btn_menu.setText('回選單')
        self.btn_menu.setFixedSize(QSize(160, 60))
        self.btn_menu.setStyleSheet('font: 24px')
        self.btn_menu.clicked.connect(self.backHome)
        # 設定相機參數按鈕
        self.btn_setting = QPushButton()
        self.btn_setting.setText('相機參數設定')
        self.btn_setting.setFixedSize(QSize(160, 60))
        self.btn_setting.setStyleSheet('font: 24px')
        self.btn_setting.clicked.connect(self.settingCamera)
        # 校正內部參數按鈕
        self.btn_intrinsic = QPushButton()
        self.btn_intrinsic.setText('棋盤格法校正')
        self.btn_intrinsic.setFixedSize(QSize(160, 60))
        self.btn_intrinsic.setStyleSheet('font: 24px')
        self.btn_intrinsic.clicked.connect(self.toggleIntrinsic)
        # 校正外部參數按鈕
        self.btn_extrinsic = QPushButton()
        self.btn_extrinsic.setText('世界座標設定')
        self.btn_extrinsic.setFixedSize(QSize(160, 60))
        self.btn_extrinsic.setStyleSheet('font: 24px')
        self.btn_extrinsic.clicked.connect(self.extrinsic)
        # 錄影按鈕
        self.btn_record = QPushButton()
        self.btn_record.setText('開始錄影')
        self.btn_record.setFixedSize(QSize(160, 60))
        self.btn_record.clicked.connect(self.toggleRecord)
        self.btn_record.setStyleSheet('font: 24px')
        # 拍照按鈕
        self.btn_snapshot = QPushButton()
        self.btn_snapshot.setText('拍照')
        self.btn_snapshot.setFixedSize(QSize(160, 60))
        self.btn_snapshot.setStyleSheet('font: 24px')
        self.btn_snapshot.clicked.connect(self.toggleSnapshot)
        # 回放按鈕
        self.btn_replay = QPushButton()
        self.btn_replay.setText('查看回放')
        self.btn_replay.setFixedSize(QSize(160, 60))
        self.btn_replay.setStyleSheet('font: 24px')
        self.btn_replay.clicked.connect(self.replay)
        # 3D驗證按鈕
        self.btn_check3d = QPushButton()
        self.btn_check3d.setText('3D座標驗證')
        self.btn_check3d.setFixedSize(QSize(160, 60))
        self.btn_check3d.setStyleSheet('font: 24px')
        self.btn_check3d.clicked.connect(self.check3d)

        container_layout.addWidget(self.btn_setting)
        container_layout.addWidget(self.btn_intrinsic)
        container_layout.addWidget(self.btn_extrinsic)
        container_layout.addWidget(self.btn_record)
        container_layout.addWidget(self.btn_snapshot)
        container_layout.addWidget(self.btn_replay)
        container_layout.addWidget(self.btn_check3d)
        container_layout.addWidget(self.btn_menu)

        container.setLayout(container_layout)
        return container

    def toggleRecord(self):
        if self.isRecording:
            self.isRecording = False
            self.btn_record.setText('開始錄影')
            self.btn_menu.setEnabled(True)
            self.btn_setting.setEnabled(True)
            self.btn_intrinsic.setEnabled(True)
            self.btn_extrinsic.setEnabled(True)
            self.btn_snapshot.setEnabled(True)
            self.btn_replay.setEnabled(True)
            self.btn_check3d.setEnabled(True)
            self.camera_widget.stopRecording()
        else:
            self.isRecording = True
            self.record_done_cnt = 0
            self.btn_record.setText('停止錄影')
            self.btn_menu.setEnabled(False)
            self.btn_setting.setEnabled(False)
            self.btn_intrinsic.setEnabled(False)
            self.btn_extrinsic.setEnabled(False)
            self.btn_snapshot.setEnabled(False)
            self.btn_replay.setEnabled(False)
            self.btn_check3d.setEnabled(False)
            self.camera_widget.startRecording()

    def toggleSnapshot(self):
        self.camera_widget.takeSnapshot()

    def settingCamera(self):
        msg = MsgContract(MsgContract.ID.PAGE_CHANGE, value='CameraSettingPage')
        msg.data = self.num_cameras
        self.myService.sendMessage(msg)

    def replay(self):
        msg = MsgContract(MsgContract.ID.PAGE_CHANGE, value='ReplayPage')
        self.myService.sendMessage(msg)

    def extrinsic(self):
        pixmaps = []
        original_sizes = []
        for image in self.camera_widget.snapshot:
            original_sizes.append(image.size())
            pixmap = QPixmap(image)
            pixmaps.append(pixmap)

        data = dict()
        data['Pixmaps'] = pixmaps
        data['SelectedCameras'] = 4
        data['Original_sizes'] = original_sizes

        msg = MsgContract(MsgContract.ID.PAGE_CHANGE, value='ExtrinsicPage', data=data)
        self.myService.sendMessage(msg)

    def check3d(self):
        pixmaps = []
        original_sizes = []
        for image in self.camera_widget.snapshot:
            original_sizes.append(image.size())
            pixmap = QPixmap(image)
            pixmaps.append(pixmap)

        data = dict()
        data['Pixmaps'] = pixmaps
        data['SelectedCameras'] = 4
        data['Original_sizes'] = original_sizes

        msg = MsgContract(MsgContract.ID.PAGE_CHANGE, value='Check3dPage', data=data)
        self.myService.sendMessage(msg)

    def backHome(self):
        msg = MsgContract(MsgContract.ID.PAGE_CHANGE, value='Home')
        self.myService.sendMessage(msg)

    def toggleIntrinsic(self):
        self.intrinsic_cb.setCurrentText('0')
        self.control_panel.hide()
        self.btn_home.show()
        self.showIntrinsic()

    def onComboBoxChanged(self):
        self.showIntrinsic()

    def checkMaxRecord(self):
        check_max = True
        for i in range(self.num_cameras):
            config_file = f"{ROOTDIR}/Reader/{self.cameras[i].brand}/config/{self.cameras[i].hw_id}.cfg"
            cameraCfg = loadConfig(config_file)
            if cameraCfg['Camera']['RecordResolution'] != '(1440, 1080)':
                check_max = False
        if check_max:
            self.btn_intrinsic.setEnabled(True)
        else:
            self.btn_intrinsic.setEnabled(False)

    def showIntrinsic(self):
        self.cur_camera = int(self.intrinsic_cb.currentText())
        self.chessboard_path = f"{ROOTDIR}/Reader/{self.cameras[self.cur_camera].brand}/intrinsic_data/{self.cameras[self.cur_camera].hw_id}"
        os.makedirs(self.chessboard_path, exist_ok=True)
        self.freshQscrollArea()

        preview_size = QSize(800, 600)
        self.camera_widget.setPreviewSize(preview_size)
        self.camera_widget.setHidden(False, [self.cur_camera])
        self.camera_widget.setHidden(True, [i for i in range(self.num_cameras) if i != self.cur_camera])

        self.gbox_camera_intrinsic.show()

    def showHome(self):
        self.camera_widget.setPreviewSize(self.image_size)
        self.camera_widget.setHidden(False, [i for i in range(self.num_cameras)])
        self.gbox_camera_intrinsic.hide()
        self.btn_home.hide()
        self.control_panel.show()

    def creatIntrinsicGroupBox(self):
        self.gbox_camera_intrinsic = QGroupBox()
        self.gbox_camera_intrinsic.setFixedSize(680,880)

        self.timer = QTimer(self)
        self.count = 0
        self.timer.timeout.connect(self.playSound)

        self.corner_x = 9
        self.corner_y = 9
        self.interval = 3
        self.times = 10

        # 選擇要設定哪台相機內部參數
        self.gbox_intrinsic = QGroupBox()
        self.layout_intrinsic = QHBoxLayout()
        self.label_intrinsic = QLabel("選擇相機:")
        self.label_intrinsic.setFont(UIFont.SpinBox)
        self.intrinsic_cb = QComboBox()
        self.intrinsic_cb.setFont(UIFont.SpinBox)
        self.intrinsic_cb.addItems([str(i) for i in range(self.num_cameras)])
        self.intrinsic_cb.setCurrentText('0')
        self.intrinsic_cb.currentIndexChanged.connect(self.onComboBoxChanged)
        self.layout_intrinsic.addWidget(self.label_intrinsic)
        self.layout_intrinsic.addWidget(self.intrinsic_cb)
        self.gbox_intrinsic.setLayout(self.layout_intrinsic)

        self.gbox_interval = QGroupBox()
        self.layout_interval = QHBoxLayout()
        self.gbox_interval.setFixedWidth(330)
        self.label_interval = QLabel("Interval second:")
        self.label_interval.setFont(UIFont.SpinBox)
        self.spin_interval = QSpinBox()
        self.spin_interval.setFont(UIFont.SpinBox)
        self.layout_interval.addWidget(self.label_interval)
        self.layout_interval.addWidget(self.spin_interval)
        self.gbox_interval.setLayout(self.layout_interval)


        self.gbox_times = QGroupBox()
        self.layout_times = QHBoxLayout()
        self.gbox_times.setFixedWidth(330)
        self.label_times = QLabel("Times:")
        self.label_times.setFont(UIFont.SpinBox)
        self.spin_times = QSpinBox()
        self.spin_times.setFont(UIFont.SpinBox)
        self.layout_times.addWidget(self.label_times)
        self.layout_times.addWidget(self.spin_times)
        self.gbox_times.setLayout(self.layout_times)

        self.gbox_chessboard_size = QGroupBox()
        self.layout_chessboard_size = QHBoxLayout()
        self.label_chessboard_size = QLabel("Chessboard size(N*N):")
        self.label_chessboard_size.setFont(UIFont.SpinBox)
        self.spin_chessboard_size = QSpinBox()
        self.spin_chessboard_size.setFont(UIFont.SpinBox)
        self.spin_chessboard_size.setValue(10)
        self.layout_chessboard_size.addWidget(self.label_chessboard_size)
        self.layout_chessboard_size.addWidget(self.spin_chessboard_size)
        self.gbox_chessboard_size.setLayout(self.layout_chessboard_size)

        self.gbox_block_size = QGroupBox()
        self.layout_block_size = QHBoxLayout()
        self.label_block_size = QLabel("Block size(mm):")
        self.label_block_size.setFont(UIFont.SpinBox)
        self.spin_block_size = QDoubleSpinBox()
        self.spin_block_size.setFont(UIFont.SpinBox)
        self.spin_block_size.setValue(10.0)
        self.spin_block_size.setSingleStep(0.1)
        self.layout_block_size.addWidget(self.label_block_size)
        self.layout_block_size.addWidget(self.spin_block_size)
        self.gbox_block_size.setLayout(self.layout_block_size)

        # qscrollarea
        self.qscrollarea_image_preview = QScrollArea()
        self.qscrollarea_image_preview.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.qscrollarea_image_preview.setWidgetResizable(True)
        self.qscrollarea_image_preview.setMinimumHeight(150)
        self.widget_qscrollarea = QWidget()
        self.layout_qscrollarea = QHBoxLayout()
        self.layout_qscrollarea.setAlignment(Qt.AlignLeft)
        self.widget_qscrollarea.setLayout(self.layout_qscrollarea)
        self.qscrollarea_image_preview.setWidget(self.widget_qscrollarea)

        self.freshQscrollArea()

        self.gbox_take_and_calculate = QGroupBox()
        self.layout_take_and_calculate = QHBoxLayout()
        self.btn_take = QPushButton("Take Chessboard")
        self.btn_take.setFont(UIFont.Combobox)
        self.btn_calculate = QPushButton("Calculate Intrinsic Matrix")
        self.btn_calculate.setFont(UIFont.Combobox)
        self.btn_deleteChess = QPushButton("Delete All Chessboard")
        self.btn_deleteChess.setFont(UIFont.Combobox)
        self.layout_take_and_calculate.addWidget(self.btn_take)
        self.layout_take_and_calculate.addWidget(self.btn_deleteChess)
        self.layout_take_and_calculate.addWidget(self.btn_calculate)
        self.gbox_take_and_calculate.setLayout(self.layout_take_and_calculate)

        self.label_intrinsic = QLabel("")
        self.label_intrinsic.setFixedSize(560,190)
        self.resetLabelIntrinsic()

        # Layout
        layout = QGridLayout()
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(0,0,0,0)

        layout.addWidget(self.gbox_intrinsic,0,0,1,2)
        layout.addWidget(self.gbox_interval,1,0)
        layout.addWidget(self.gbox_times,1,1)
        layout.addWidget(self.gbox_chessboard_size,2,0,1,2)
        layout.addWidget(self.gbox_block_size,3,0,1,2)
        layout.addWidget(self.qscrollarea_image_preview,4,0,4,2)
        layout.addWidget(self.gbox_take_and_calculate,8,0,1,2)
        layout.addWidget(self.label_intrinsic,9,0,3,2)
        self.gbox_camera_intrinsic.setLayout(layout)
        #self.gbox_camera_intrinsic.setFont(UIFont.CONTENT)

        # Default Value
        self.spin_interval.setValue(self.interval)
        self.spin_times.setValue(self.times)

        # SIGNAL & SLOT
        self.btn_deleteChess.clicked.connect(self.deleteChessboard)
        self.spin_interval.valueChanged.connect(self.intervalValuechange)
        self.spin_times.valueChanged.connect(self.timesValuechange)
        self.btn_take.clicked.connect(self.takePicture)
        self.btn_calculate.clicked.connect(self.calculateIntrinsic)
        self.spin_chessboard_size.valueChanged.connect(self.cornerValuechange)
        self.spin_block_size.valueChanged.connect(self.blockValuechange)

        #######################
        self.chessboard_idx = 0
        # Chessboard Index Starts From Current Max Index+1
        for filename in os.listdir(self.chessboard_path):
            if filename.startswith('chessboard_') and filename.endswith('.jpg'):
                self.chessboard_idx = max(self.chessboard_idx,int(filename[len('chessboard_'):len('chessboard_')+4])+1)

    def freshQscrollArea(self):
        # init scrollarea picture
        time.sleep(0.2)
        for i in reversed(range(self.layout_qscrollarea.count())):
            self.layout_qscrollarea.itemAt(i).widget().setParent(None)
        for filename in os.listdir(self.chessboard_path):
            if filename.startswith('chessboard_') and filename.endswith('.jpg'): # Only show chessboard
                fullpath = os.path.join(self.chessboard_path, filename)
                pix = QPixmap(fullpath).scaled(150, 150, Qt.KeepAspectRatio)
                object = ClickLabel(fullpath)
                object.setPixmap(pix)
                object.clicked.connect(self.showImage)
                self.layout_qscrollarea.addWidget(object)

    def showImage(self, image_fullpath):
        new_label = QLabel()
        new_label.setPixmap(QPixmap(image_fullpath).scaled(800, 800, Qt.KeepAspectRatio))
        self.bigpicture = QDialog()
        btn_delete_image = QPushButton('delete')
        btn_delete_image.clicked.connect(lambda: self.deleteImage(image_fullpath))
        layout = QVBoxLayout()
        self.bigpicture.setLayout(layout)
        layout.addWidget(btn_delete_image)
        layout.addWidget(new_label)
        self.bigpicture.setWindowTitle('big picture')
        self.bigpicture.setAttribute(Qt.WA_DeleteOnClose)
        self.bigpicture.exec_()

    def deleteImage(self, image_fullpath):
        os.remove(image_fullpath)
        self.bigpicture.close()
        self.freshQscrollArea()

    def resetLabelIntrinsic(self):
        self.label_intrinsic.setFont(UIFont.Combobox)
        self.label_intrinsic.clear()

    def intervalValuechange(self):
        self.interval = self.spin_interval.value()

    def timesValuechange(self):
        self.times = self.spin_times.value()

    def cornerValuechange(self):
        self.corner_x = self.spin_chessboard_size.value() - 1
        self.corner_y = self.spin_chessboard_size.value() - 1

    def blockValuechange(self):
        self.blockSize = self.spin_block_size.value()

    def playSound(self):
        if (self.interval != 0):
            self.count += 1
            if (self.count % self.interval != 0):
                pass
            else:
                filepath = (os.path.join(self.chessboard_path,'chessboard_'+'{:0>4d}.jpg'.format(self.chessboard_idx)))
                pixmap = QPixmap(self.camera_widget.snapshot[self.cur_camera])
                pixmap.save(filepath)
                self.label_intrinsic.setText("{}/{}".format(int(self.count/self.interval),self.times))
                self.label_intrinsic.repaint()
                self.chessboard_idx += 1
                self.freshQscrollArea()
            if (self.count >= self.interval * self.times):
                self.freshQscrollArea()
                self.count = 0
                self.timer.stop()

    def deleteChessboard(self):
        self.resetLabelIntrinsic()
        for filename in os.listdir(self.chessboard_path):
            fullpath = os.path.join(self.chessboard_path, filename)
            if filename.startswith('chessboard_') and filename.endswith('.jpg'):
                os.remove(fullpath)
        self.chessboard_idx = 0
        self.freshQscrollArea()

    def hideTakePictureBtn(self):
        self.btn_take.setEnabled(False)
        QTimer.singleShot(self.times * self.interval * 1000, lambda: self.btn_take.setDisabled(False))

    def takePicture(self):
        self.hideTakePictureBtn()
        self.label_intrinsic.setFont(QFont('Times', 100))
        self.label_intrinsic.setText("0/{}".format(self.times))
        self.label_intrinsic.repaint()
        if self.times != 0:
            if self.interval != 0:
                self.timer.start(1000)
            else:
                for i in range(self.times):
                    filepath = (os.path.join(self.chessboard_path,'chessboard_'+'{:0>4d}.jpg'.format(self.chessboard_idx)))
                    pixmap = QPixmap(self.camera_widget.snapshot[self.cur_camera])
                    pixmap.save(filepath)
                    self.label_intrinsic.setText("{}/{}".format(i+1,self.times))
                    self.label_intrinsic.repaint()
                    self.chessboard_idx += 1
                    self.freshQscrollArea()

    def calculateIntrinsic(self):
        camera = self.cameras[self.cur_camera]
        config_file = f"{ROOTDIR}/Reader/{camera.brand}/config/{camera.hw_id}.cfg"
        image_path = f"{ROOTDIR}/Reader/{camera.brand}/intrinsic_data/{camera.hw_id}"
        setIntrinsicMtx(config_file, image_path, '(1440, 1080)')
        self.resetLabelIntrinsic()
