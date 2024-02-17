import os
import sys
import logging

from PyQt5.QtWidgets import QGroupBox, QPushButton, QHBoxLayout, QWidget, QVBoxLayout, QGridLayout
from PyQt5.QtCore import QSize
from PyQt5.Qt import *
from PyQt5.QtGui import *

DIRNAME = os.path.dirname(os.path.abspath(__file__))
ROOTDIR = os.path.dirname(os.path.dirname(DIRNAME))
sys.path.append(f"{ROOTDIR}/UI/")
from Services import SystemService, MsgContract

class TrajectoryAnalyzingPage(QGroupBox):
    def __init__(self, camera_widget):
        super().__init__()

        self.camera_widget = camera_widget
        self.image_size = QSize(480, 360)

        self.isRecording = False

    def hideEvent(self, event):
        logging.debug(f"{self.__class__.__name__}: hided.")
        self.camera_widget.stopStreaming()
        self.deleteUI()

    def showEvent(self, event):
        logging.debug(f"{self.__class__.__name__}: shown.")
        self.setupUI()
        self.camera_widget.startStreaming()

    def setBackgroundService(self, service:SystemService):
        self.myService = service

    def setupUI(self):
        self.control_bar = self.getControlBar()

        self.camera_widget.initWidget(4, self.image_size)

        self.layout_main = QHBoxLayout()
        self.layout_main.addWidget(self.control_bar, 1, Qt.AlignCenter)
        self.layout_main.addWidget(self.camera_widget, 8, Qt.AlignCenter)

        self.setLayout(self.layout_main)

    def deleteUI(self):
        self.layout_main.removeWidget(self.camera_widget)
        while self.layout_main.count():
            item = self.layout_main.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.layout_main.deleteLater()

    def getControlBar(self):
        container = QWidget()
        container.setFixedSize(QSize(180, 800)) # 天，超醜
        container_layout = QGridLayout()

        # 回選單按鈕
        self.btn_menu = QPushButton()
        self.btn_menu.setText('回選單')
        self.btn_menu.setFixedSize(QSize(160, 60))
        self.btn_menu.setStyleSheet('font: 24px')
        self.btn_menu.clicked.connect(self.backMenu)

        # 錄影按鈕
        self.btn_record = QPushButton()
        self.btn_record.setText('開始錄影')
        self.btn_record.setFixedSize(QSize(160, 60))
        self.btn_record.clicked.connect(self.toggleRecord)
        self.btn_record.setStyleSheet('font: 24px')

        container_layout.addWidget(self.btn_record, 0, 0, Qt.AlignBottom)
        container_layout.addWidget(self.btn_menu, 1, 0, Qt.AlignBottom)

        container.setLayout(container_layout)
        return container

    def backMenu(self):
        msg = MsgContract(MsgContract.ID.PAGE_CHANGE, value='Home')
        self.myService.sendMessage(msg)

    def toggleRecord(self):
        if self.isRecording:
            self.isRecording = False
            self.btn_record.setText('開始錄影')
            self.btn_menu.setEnabled(True)
            self.camera_widget.stopRecording()
            msg = MsgContract(MsgContract.ID.PAGE_CHANGE, value='WaitPage')
            self.myService.sendMessage(msg)
        else:
            self.isRecording = True
            self.btn_record.setText('停止錄影')
            self.btn_menu.setEnabled(False)
            self.camera_widget.startRecording()