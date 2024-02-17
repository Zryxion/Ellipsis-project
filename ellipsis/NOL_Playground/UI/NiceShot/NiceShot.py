import logging

from PyQt5.QtWidgets import QGroupBox, QPushButton, QHBoxLayout, QVBoxLayout, QSlider, QComboBox
from PyQt5.QtCore import QSize, QUrl
from PyQt5.QtGui import QIcon
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer

from UISettings import *
from Services import SystemService, MsgContract
from common import loadConfig, saveConfig, setIntrinsicMtx

DIRNAME = os.path.dirname(os.path.abspath(__file__))
ROOTDIR = os.path.dirname(os.path.dirname(DIRNAME))
ICONDIR = f"{os.path.dirname(DIRNAME)}/icon"

class NiceShot(QGroupBox):
    def __init__(self):
        super().__init__()

        self.fps = 120

        # setup UI
        self.setupUI()

    def hideEvent(self, event):
        logging.debug(f"{self.__class__.__name__}: hided.")

    def showEvent(self, event):
        logging.debug(f"{self.__class__.__name__}: shown.")
        self.openFile()

    def setBackgroundService(self, service:SystemService):
        self.myService = service

    def setupUI(self):
        # 回首頁按鈕
        self.right_part = QVBoxLayout()
        self.btn_home = QPushButton()
        self.btn_home.setIcon(QIcon(f"{ICONDIR}/home.png"))
        self.btn_home.setIconSize(QSize(50,50))
        self.btn_home.clicked.connect(self.showHome)
        self.right_part.addWidget(self.btn_home, alignment=Qt.AlignTop)

        # 上一頁按鈕
        self.left_part = QVBoxLayout()
        self.btn_prev_page = QPushButton()
        self.btn_prev_page.setIcon(QIcon(f"{ICONDIR}/previous.png"))
        self.btn_prev_page.setIconSize(QSize(50,50))
        self.btn_prev_page.clicked.connect(self.showPrevPage)
        self.left_part.addWidget(self.btn_prev_page, alignment=Qt.AlignTop)

        # 中間影片部分
        self.mid_part = QVBoxLayout()
        self.video_widget = QVideoWidget()

        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.setPosition)

        self.control_layout = QHBoxLayout()

        self.btn_backward = QPushButton()
        self.btn_backward.setIcon(QIcon(f"{ICONDIR}/backward.png"))
        self.btn_backward.setIconSize(QSize(30,30))
        self.btn_backward.clicked.connect(self.backward)

        self.btn_backward_one_frame = QPushButton()
        self.btn_backward_one_frame.setIcon(QIcon(f"{ICONDIR}/backward_one_frame.png"))
        self.btn_backward_one_frame.setIconSize(QSize(30,30))
        self.btn_backward_one_frame.clicked.connect(self.backwardOneFrame)

        self.btn_play = QPushButton()
        self.btn_play.setEnabled(False)
        self.btn_play.setIcon(QIcon(f"{ICONDIR}/play.png"))
        self.btn_play.setIconSize(QSize(30,30))
        self.btn_play.clicked.connect(self.play)

        self.btn_forward_one_frame = QPushButton()
        self.btn_forward_one_frame.setIcon(QIcon(f"{ICONDIR}/forward_one_frame.png"))
        self.btn_forward_one_frame.setIconSize(QSize(30,30))
        self.btn_forward_one_frame.clicked.connect(self.forwardOneFrame)

        self.btn_forward = QPushButton()
        self.btn_forward.setIcon(QIcon(f"{ICONDIR}/forward.png"))
        self.btn_forward.setIconSize(QSize(30,30))
        self.btn_forward.clicked.connect(self.forward)

        self.cb_speed = QComboBox()
        self.cb_speed.setFont(QFont('Times', 15))
        self.cb_speed.addItems(['X 0.75', 'X 1', 'X 1.25', 'X 1.5', 'X 1.75', 'X 2'])
        self.cb_speed.setCurrentText('X 1')
        self.cb_speed.currentIndexChanged.connect(self.onSpeedChanged)

        self.control_layout.addWidget(self.btn_backward)
        self.control_layout.addWidget(self.btn_backward_one_frame)
        self.control_layout.addWidget(self.btn_play)
        self.control_layout.addWidget(self.btn_forward_one_frame)
        self.control_layout.addWidget(self.btn_forward)
        self.control_layout.addWidget(self.cb_speed)

        self.mid_part.addWidget(self.video_widget)
        self.mid_part.addWidget(self.position_slider)
        self.mid_part.addLayout(self.control_layout)

        self.layout_main = QHBoxLayout()
        self.layout_main.addStretch(1)
        self.layout_main.addLayout(self.left_part, 1)
        self.layout_main.addLayout(self.mid_part, 13)
        self.layout_main.addLayout(self.right_part, 1)
        self.layout_main.addStretch(1)

        self.setLayout(self.layout_main)

        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.stateChanged.connect(self.mediaStateChanged)
        self.media_player.positionChanged.connect(self.positionChanged)
        self.media_player.durationChanged.connect(self.durationChanged)

    def openFile(self):
        video_dir = f'{ROOTDIR}/NiceShot'
        # file_name = os.path.join(video_dir, sorted(os.listdir(video_dir))[-1])
        file_name = os.path.join(video_dir, '2023-06-01_16-15-14_NiceShot.mp4') # for test

        if file_name != '':
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_name)))
            self.btn_play.setEnabled(True)
            self.media_player.setPosition(0)
            self.position_slider.setValue(0)
            self.media_player.pause()

    def play(self):
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def backward(self):
        position = self.media_player.position()
        duration = self.media_player.duration()
        position = max(0, position - duration / 10)
        self.position_slider.setValue(position)
        self.media_player.setPosition(position)

    def forward(self):
        position = self.media_player.position()
        duration = self.media_player.duration()
        position = min(duration, position + duration / 10)
        self.position_slider.setValue(position)
        self.media_player.setPosition(position)

    def backwardOneFrame(self):
        position = self.media_player.position()
        position = max(0, position - 1000.0 / self.fps)
        self.position_slider.setValue(position)
        self.media_player.setPosition(position)

    def forwardOneFrame(self):
        position = self.media_player.position()
        duration = self.media_player.duration()
        position = min(duration, position + 1000.0 / self.fps)
        self.position_slider.setValue(position)
        self.media_player.setPosition(position)
    
    def mediaStateChanged(self, state):
        if self.media_player.state() == QMediaPlayer.StoppedState:
            self.btn_play.setIcon(QIcon(f"{ICONDIR}/play.png"))
        elif self.media_player.state() == QMediaPlayer.PlayingState:
            self.btn_play.setIcon(QIcon(f"{ICONDIR}/pause.png"))
        else:
            self.btn_play.setIcon(QIcon(f"{ICONDIR}/play.png"))

    def positionChanged(self, position):
        self.position_slider.setValue(position)

    def durationChanged(self, duration):
        self.position_slider.setRange(0, duration)

    def setPosition(self, position):
        self.media_player.setPosition(position)

    def showHome(self):
        msg = MsgContract(MsgContract.ID.PAGE_CHANGE, value='Home')
        self.myService.sendMessage(msg)

    def showPrevPage(self):
        msg = MsgContract(MsgContract.ID.PAGE_CHANGE, value='NiceShotRecord')
        self.myService.sendMessage(msg)

    def onSpeedChanged(self):
        self.media_player.setPlaybackRate(float(self.cb_speed.currentText()[2:]))