import os
import sys
import csv
import logging

from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QComboBox, QWidget, QHBoxLayout, QPushButton, QTableWidget, QGridLayout, QTableWidgetItem
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QIcon, QFont

DIRNAME = os.path.dirname(os.path.abspath(__file__))
ROOTDIR = os.path.dirname(os.path.dirname(DIRNAME))
REPLAYDIR = f"{ROOTDIR}/replay"
ICONDIR = f"{ROOTDIR}/UI/icon"

sys.path.append(f"{ROOTDIR}/UI")
from Services import SystemService, MsgContract
from TrajectoryAnalyzing.Trajectory3DVisualizeWidget import Trajectory3DVisualizeWidget

sys.path.append(f"{ROOTDIR}/lib")
from point import Point
from smooth import removeOuterPoint, detectEvent, smoothByEvent, detectBallTypeByEvent
from model3D_cut import cut_csv
from trajectory_pred import placement_predict
from BallInfo import getBallInfo, writeBallInfo

class Model3dPage(QGroupBox):
    def __init__(self):
        super().__init__()

        # 用來放每次讀檔的軌跡，一段存一起
        # visibility = 1, event = 0 是球在飛行
        # event = 1 是擊球
        # event = 2 是發球
        # event = 3 是死球
        self.tracks = []
        self.ball_type_a = {
            '小球': 0,
            '挑球': 0,
            '推球': 0,
            '平球': 0,
            '切球': 0,
            '殺球': 0,
            '長球': 0,
            '例外': 0
        }
        self.ball_type_b = {
            '小球': 0,
            '挑球': 0,
            '推球': 0,
            '平球': 0,
            '切球': 0,
            '殺球': 0,
            '長球': 0,
            '例外': 0
        }

        # current points in video
        self.cur_points = 1
        self.max_points = 1

        # setup UI
        self.setupUI()

    def hideEvent(self, event):
        self.widget_court.clearAll()
        logging.debug(f"{self.__class__.__name__}: hided.")

    def showEvent(self, event):
        self.date_cb.blockSignals(True)
        self.date_cb.clear()
        dates = [f for f in os.listdir(REPLAYDIR)]
        dates.sort()
        self.date_cb.addItem('')
        self.date_cb.addItems(dates)
        self.date_cb.setCurrentText(dates[-1])
        date = self.date_cb.currentText()
        self.date_cb.blockSignals(False)
        removeOuterPoint(date)
        # cut_csv(date)
        # files = [f for f in os.listdir(os.path.join(REPLAYDIR, date)) if f.startswith('Model3D_mod_')]
        self.max_points = 1
        self.showTrajectory(date)
        logging.debug(f"{self.__class__.__name__}: shown.")

    def setBackgroundService(self, service:SystemService):
        self.myService = service

    def setupUI(self):
        layout_main = QHBoxLayout()

        control_widget = QWidget()
        control_layout = QVBoxLayout()
        self.control_bar = self.getControlBar()
        self.control_3d = self.getControl3d()
        control_layout.addWidget(self.control_bar)
        control_layout.addWidget(self.control_3d)
        control_widget.setLayout(control_layout)

        table_widget = QWidget()
        table_layout = QVBoxLayout()
        self.balltype_tb = self.getTable()
        self.ballinfo_tb = self.getInfoTable()
        table_layout.addWidget(self.balltype_tb)
        table_layout.addWidget(self.ballinfo_tb)
        table_widget.setLayout(table_layout)

        layout_main.addWidget(control_widget)
        layout_main.addWidget(table_widget)
        self.setLayout(layout_main)

    def getControlBar(self):
        container = QWidget()
        container_layout = QHBoxLayout()

        self.btn_home = QPushButton()
        self.btn_home.setText('回首頁')
        self.btn_home.setFixedSize(QSize(120, 50))
        self.btn_home.setStyleSheet('font: 24px')
        self.btn_home.clicked.connect(self.backhome)

        # replay 日期選擇
        self.date_cb = QComboBox()
        self.date_cb.currentTextChanged.connect(self.date_cb_changed)
        self.date_cb.setFixedSize(1100,50)

        container_layout.addWidget(self.btn_home)
        container_layout.addWidget(self.date_cb)
        container.setLayout(container_layout)
        return container

    def getControl3d(self):
        container = QWidget()
        container_layout = QHBoxLayout()

        # 3D 軌跡圖
        self.widget_court = Trajectory3DVisualizeWidget()
        self.widget_court.setMinimumSize(800, 800)

        self.nextbtn = QPushButton(self)
        self.nextbtn.clicked.connect(self.onClickNext)
        self.nextbtn.setFixedSize(QSize(60, 96))
        self.nextbtn.setIcon(QIcon(f"{ICONDIR}/right_arrow.png"))
        self.nextbtn.setIconSize(QSize(55, 55))

        # change the court to show next shot
        self.lastbtn = QPushButton(self)
        self.lastbtn.clicked.connect(self.onClickLast)
        self.lastbtn.setFixedSize(QSize(60, 96))
        self.lastbtn.setIcon(QIcon(f"{ICONDIR}/left_arrow.png"))
        self.lastbtn.setIconSize(QSize(55, 55))

        container_layout.addWidget(self.lastbtn)
        container_layout.addWidget(self.widget_court)
        container_layout.addWidget(self.nextbtn)
        container.setLayout(container_layout)
        return container

    def getTable(self):
        table = QTableWidget(len(self.ball_type_a), 3)
        table.setColumnWidth(0, 150)
        table.setColumnWidth(1, 150)
        table.setColumnWidth(2, 150)
        i = 0
        for k in self.ball_type_a:
            table.setRowHeight(i, 49)
            type_item = QTableWidgetItem(k)
            type_item.setFont(QFont('Times', 20))
            count_item_a = QTableWidgetItem(str(0))
            count_item_a.setFont(QFont('Times', 20))
            count_item_b = QTableWidgetItem(str(0))
            count_item_b.setFont(QFont('Times', 20))
            table.setItem(i, 0, type_item)
            table.setItem(i, 1, count_item_a)
            table.setItem(i, 2, count_item_b)
            i += 1

        header = ['球種', '發球方', '接發球方']
        table.setHorizontalHeaderLabels(header)
        table.horizontalHeader().setFont(QFont('Times', 12))
        return table

    def getInfoTable(self):
        table = QTableWidget()
        table.setColumnCount(5)
        table.setRowCount(1)
        table.setColumnWidth(0, 95)
        table.setColumnWidth(1, 95)
        table.setColumnWidth(2, 80)
        table.setColumnWidth(3, 90)
        table.setColumnWidth(4, 90)

        header = ['球種', '球速(km/h)', '角度', '過網高度', '最大高度']
        table.setHorizontalHeaderLabels(header)
        table.horizontalHeader().setFont(QFont('Times', 12))
        return table

    def showTrack(self):
        total_tracks = 0
        self.widget_court.clearAll()
        for track in self.tracks:
            for point in track:
                if point.event == 1:
                    point.color = 'blue'
                if point.event == 2:
                    point.color = 'red'
                    # total_tracks += 1 (這邊還沒做事件偵測，先都通時呈現不分段)
                if point.event == 3:
                    point.color = 'green'
                    # total_tracks += 1 (理論上這段是雜訊)
                self.widget_court.addPointByTrackID(point, total_tracks)

    def readPoints(self, tracks_file):
        points = []
        with open(tracks_file, 'r', newline='') as csvFile:
            rows = csv.DictReader(csvFile)
            for row in rows:
                if int(float(row['Visibility'])) != 0:
                    point = Point(fid=row['Frame'], timestamp=row['Timestamp'], visibility=row['Visibility'],
                                    x=row['X'], y=row['Y'], z=row['Z'],
                                    event=row['Event'])
                    points.append(point)
        self.tracks.append(points)

    def showBallType(self, ball_type):
        if ball_type != []:
            for i, type in enumerate(ball_type):
                if i % 2 == 0:
                    self.ball_type_a[type] += 1
                else:
                    self.ball_type_b[type] += 1

        for i in range(self.balltype_tb.rowCount()):
            type = self.balltype_tb.item(i, 0).text()
            count_a = self.ball_type_a[type]
            count_a_item = QTableWidgetItem(str(count_a))
            count_a_item.setFont(QFont('Times', 20))
            count_b = self.ball_type_b[type]
            count_b_item = QTableWidgetItem(str(count_b))
            count_b_item.setFont(QFont('Times', 20))
            self.balltype_tb.setItem(i, 1, count_a_item)
            self.balltype_tb.setItem(i, 2, count_b_item)

    def showBallInfo(self, ball_info, ball_type):
        try:
            self.ballinfo_tb.setRowCount(len(ball_info))
            for i, r in enumerate(ball_info):
                self.ballinfo_tb.setRowHeight(i, 40)
                type_item = QTableWidgetItem(f'{ball_type[i]}')
                type_item.setFont(QFont('Times', 18))
                speed_item = QTableWidgetItem(f'{r["Speed"]:.2f}')
                speed_item.setFont(QFont('Times', 18))
                angle_item = QTableWidgetItem(f'{r["Angle"]:.1f}°')
                angle_item.setFont(QFont('Times', 18))
                midheight_item = QTableWidgetItem(f'{r["MidHeight"]:.2f}m')
                midheight_item.setFont(QFont('Times', 18))
                maxheight_item = QTableWidgetItem(f'{r["MaxHeight"]:.2f}m')
                maxheight_item.setFont(QFont('Times', 18))

                self.ballinfo_tb.setItem(i, 0, type_item)
                self.ballinfo_tb.setItem(i, 1, speed_item)
                self.ballinfo_tb.setItem(i, 2, angle_item)
                self.ballinfo_tb.setItem(i, 3, midheight_item)
                self.ballinfo_tb.setItem(i, 4, maxheight_item)
        except Exception as e:
            logging.error(f"error in showBallInfo {e}")

    def date_cb_changed(self):
        if self.date_cb.currentText() == '':
            self.widget_court.clearAll()
            self.cur_points = 1
            self.max_points = 1
            for k in self.ball_type_a:
                self.ball_type_a[k] = 0
                self.ball_type_b[k] = 0
        else:
            self.cur_points = 1
            self.max_points = 1
            date = self.date_cb.currentText()
            removeOuterPoint(date)
            # do something to cut mod to mod_1, mod_2, ...
            # cut_csv(date)
            # files = [f for f in os.listdir(os.path.join(REPLAYDIR, date)) if f.startswith('Model3D_mod_')]
            self.max_points = 1
            self.showTrajectory(date)

    def showTrajectory(self, date):
        self.widget_court.clearAll()
        for k in self.ball_type_a:
            self.ball_type_a[k] = 0
            self.ball_type_b[k] = 0
        self.tracks = []
        detectEvent(date, self.cur_points)
        smoothByEvent(date, self.cur_points)
        ball_type = detectBallTypeByEvent(date, self.cur_points)
        ball_info = getBallInfo(date, self.cur_points)

        ball_info_file = 'Model3D_info_' + str(self.cur_points) + '.csv'
        ball_info_path = os.path.join(REPLAYDIR, date, ball_info_file)
        writeBallInfo(ball_info_path, ball_info, ball_type)

        file = 'Model3D_smooth_' + str(self.cur_points) + '.csv'
        track_file = os.path.join(REPLAYDIR, date, file)
        #predict trajectory
        # placement_predict(date,file)
        try:
            self.readPoints(tracks_file = track_file)
            self.showTrack()
            self.widget_court.setShotText(self.cur_points)
            self.showBallType(ball_type = ball_type)
            self.showBallInfo(ball_info=ball_info, ball_type=ball_type)
        except:
            logging.warning("[Model3D_smooth] No Csv Files: {}".format(track_file))

    def backhome(self):
        msg = MsgContract(MsgContract.ID.PAGE_CHANGE, value='TrajectoryAnalyzingPage')
        self.myService.sendMessage(msg)

    def onClickNext(self):
        self.cur_points += 1
        if self.cur_points > self.max_points:
            self.cur_points = 1
        date = self.date_cb.currentText()
        self.showTrajectory(date)

    def onClickLast(self):
        self.cur_points -= 1
        if self.cur_points <= 0:
            self.cur_points = self.max_points
        date = self.date_cb.currentText()
        self.showTrajectory(date)