import sys
import os
import logging
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QGroupBox, QPushButton, QHBoxLayout, QVBoxLayout
from PyQt5.QtGui import QIcon

DIRNAME = os.path.dirname(os.path.abspath(__file__))
ROOTDIR = os.path.dirname(os.path.dirname(DIRNAME))
REPLAYDIR = f"{ROOTDIR}/replay"
sys.path.append(f"{DIRNAME}/../")

from UISettings import *
from Services import SystemService, MsgContract
from message import *

sys.path.append(f"{DIRNAME}/../lib")

class NiceShotRecord(QGroupBox):
    def __init__(self, camera_widget):
        super().__init__()

        self.camera_widget = camera_widget
        self.image_size = QSize(800, 600)

    def hideEvent(self, event):
        logging.debug(f"{self.__class__.__name__}: hided.")
        self.camera_widget.stopStreaming()
        self.deleteUI()

    def showEvent(self, event):
        # self.showProcessing()
        # return # for test
        logging.debug(f"{self.__class__.__name__}: shown.")
        self.setupUI()
        self.camera_widget.startStreaming()

    def setBackgroundService(self, service:SystemService):
        self.myService = service

    def setupUI(self):
        # 錄影按鈕
        self.top_bar = QHBoxLayout()
        self.top_bar.addStretch(1)

        self.btn_start_recording = QPushButton()
        self.btn_start_recording.setText('開始錄影')
        self.btn_start_recording.setFixedSize(QSize(300, 60))
        self.btn_start_recording.setStyleSheet('font: 24px')
        self.btn_start_recording.clicked.connect(self.startRecording)
        self.top_bar.addWidget(self.btn_start_recording)

        self.btn_stop_recording = QPushButton()
        self.btn_stop_recording.setEnabled(False)
        self.btn_stop_recording.setText('停止錄影')
        self.btn_stop_recording.setFixedSize(QSize(300, 60))
        self.btn_stop_recording.setStyleSheet('font: 24px')
        self.btn_stop_recording.clicked.connect(self.stopRecording)
        self.top_bar.addWidget(self.btn_stop_recording)

        self.top_bar.addStretch(10)

        self.btn_home = QPushButton()
        self.btn_home.setIcon(QIcon(f"{ICONDIR}/home.png"))
        self.btn_home.setIconSize(QSize(60,60))
        self.btn_home.clicked.connect(self.showHome)
        self.top_bar.addWidget(self.btn_home)

        self.top_bar.addStretch(1)

        # 相機畫面
        self.camera_widget.initWidget(2, self.image_size)
        self.camera_widget.toggleFPS()

        # 剪輯按鈕
        self.cutting_part = QHBoxLayout()
        self.cutting_part.addStretch(14)

        self.btn_cutting = QPushButton()
        self.btn_cutting.setEnabled(False)
        self.btn_cutting.setText('精彩剪輯')
        self.btn_cutting.setFixedSize(QSize(300, 60))
        self.btn_cutting.setStyleSheet('font: 24px')
        self.btn_cutting.clicked.connect(self.showProcessing)
        self.cutting_part.addWidget(self.btn_cutting)

        self.cutting_part.addStretch(1)

        self.layout_main = QVBoxLayout()
        self.layout_main.addStretch(1)
        self.layout_main.addLayout(self.top_bar)
        self.layout_main.addWidget(self.camera_widget, alignment=Qt.AlignCenter)
        self.layout_main.addLayout(self.cutting_part)
        self.layout_main.addStretch(1)

        self.setLayout(self.layout_main)

    def deleteUI(self):
        self.layout_main.removeWidget(self.camera_widget)
        while self.layout_main.count():
            item = self.layout_main.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.layout_main.deleteLater()

    def showHome(self):
        msg = MsgContract(MsgContract.ID.PAGE_CHANGE, value='Home')
        self.myService.sendMessage(msg)

    def showProcessing(self):
        msg = MsgContract(MsgContract.ID.PAGE_CHANGE, value='Processing')
        self.myService.sendMessage(msg)

    def showNiceShot(self):
        msg = MsgContract(MsgContract.ID.PAGE_CHANGE, value='NiceShot')
        self.myService.sendMessage(msg)

    def startRecording(self):
        self.btn_start_recording.setEnabled(False)
        self.btn_stop_recording.setEnabled(True)
        self.btn_home.setEnabled(False)
        self.btn_cutting.setEnabled(False)
        self.camera_widget.startRecording()

    def stopRecording(self):
        self.camera_widget.stopRecording()
        self.btn_start_recording.setEnabled(True)
        self.btn_stop_recording.setEnabled(False)
        self.btn_home.setEnabled(True)
        self.btn_cutting.setEnabled(True)