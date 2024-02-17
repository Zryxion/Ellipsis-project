import sys
import os
import logging #

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QMainWindow, QGroupBox, QGridLayout, QWidget, QDialog, QMessageBox, QStatusBar, QLabel, QAction, QMenu
from PyQt5.QtCore import QSize, Qt

DIRNAME = os.path.dirname(os.path.abspath(__file__))
REPLAYDIR = f"{DIRNAME}/replay"
ICONDIR = f"{DIRNAME}/UI/icon"
sys.path.append(f"{DIRNAME}/lib")
from common import loadConfig, setupLogLevel
from nodes import setupCameras
from message import *
from CameraWidget import CameraWidget

sys.path.append(f"{DIRNAME}/UI")
from UISettings import *
from HomePage import HomePage
from Services import SystemService
from CameraSetting.CameraSystem import CameraSystem
from CameraSetting.CameraSettingPage import CameraSettingPage
from CameraSetting.ExtrinsicPage import ExtrinsicPage
# from CameraSetting.autoExtrinsicPage import ExtrinsicPage
from CameraSetting.ReplayPage import ReplayPage
from CameraSetting.Check3dPage import Check3dPage
from TestPage.TestPage import TestPage
from Boom.BoomPage import BoomPage
from MachineCalibration.VisualizePage import VisualizePage
from MachineCalibration.VisualizePage import VisualizePage
from MachineCalibration.CalibrationPage import CalibrationPage

from TrajectoryAnalyzing.TrajectoryAnalyzingPage import TrajectoryAnalyzingPage
from TrajectoryAnalyzing.WaitPage import WaitPage
from TrajectoryAnalyzing.Model3dPage import Model3dPage
from NiceShot.NiceShot import NiceShot
from NiceShot.NiceShotRecord import NiceShotRecord
from NiceShot.Processing import Processing


from pitcherUI.BaseballSettingPage import BaseballSettingPage
from pitcherUI.ResultPage_keyframe import ResultPage_keyframe
from pitcherUI.ResultPage_angleAnalyze import ResultPage_angleAnalyze
from pitcherUI.ResultPage_powerChain import ResultPage_powerChain
from pitcherUI.Result_angleDetail import Result_angleDetail
from pitcherUI.ResultPage_3Dplot import ResultPage_3Dplot

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        # set desktop icon
        self.setWindowIcon(QIcon(f"{ICONDIR}/desktop.png"))

        # initialize
        self.pages = {}
        self.myService = None

        # loading project config
        cfg_file = f"./config"
        cfg = loadConfig(cfg_file)

        # setup Logging Level
        setupLogLevel(level=cfg['Project']['logging_level'], log_file="UI")

        # setup background service
        service = SystemService(cfg)
        service.callback.connect(self.handleMessage)
        service.start()
        self.setBackgroundService(service)

        # setup UI
        self.setupUI(cfg)

    def closeEvent(self, event):
        if self.myService.isRunning():
            logging.debug("stop system service")
            self.myService.stop()
        logging.debug("closeEvent")

    def setupUI(self, cfg):
        self.layout_main = QGridLayout()
        mainWidget = QWidget()
        mainWidget.setLayout(self.layout_main)
        self.setCentralWidget(mainWidget)

        # setup Cameras Node of Project
        cameras = setupCameras(cfg)
        # start Camera Node
        self.addNodes(cameras)

        self.cameraWidget = CameraWidget(cfg, cameras, 4)
        self.cameraWidget.setBackgroundService(self.myService)

        # Page :: Home
        self.home_page = HomePage()
        self.addPage("Home", self.home_page)
        # Page :: CameraSystem
        self.camera_system_page = CameraSystem(cfg["Project"]["mqtt_broker"], cfg, cameras, self.cameraWidget)
        self.addPage("CameraSystem", self.camera_system_page)
        # Page :: CameraSettingPage
        self.camera_setting_page = CameraSettingPage(cameras)
        self.addPage("CameraSettingPage", self.camera_setting_page)
        # Page :: ExtrinsicPage
        self.extrinsic_page = ExtrinsicPage(cameras)
        self.addPage("ExtrinsicPage", self.extrinsic_page)
        # Page :: ReplayPage
        self.replay_page = ReplayPage(cfg)
        self.addPage("ReplayPage", self.replay_page)
        # Page :: Check3dPage
        self.check3d_page = Check3dPage(cameras)
        self.addPage("Check3dPage", self.check3d_page)
        #Page :: Boom
        self.BoomPage = BoomPage(self.cameraWidget, cfg["Project"]["mqtt_broker"], cfg, cameras)
        self.addPage("BoomPage", self.BoomPage)

        #self.machineCalibration = VisualizePage()
        self.machineCalibration = CalibrationPage(self.cameraWidget)
        self.addPage("MachineCalibration", self.machineCalibration)

        self.test_page = TestPage(self.cameraWidget)
        self.addPage("TestPage", self.test_page)

        # Page :: TrajectoryAnalyzing
        self.trajectory_analyzing_page = TrajectoryAnalyzingPage(self.cameraWidget)
        self.addPage("TrajectoryAnalyzingPage", self.trajectory_analyzing_page)
        # Page :: WaitPage
        self.wait_page = WaitPage(cfg)
        self.addPage("WaitPage", self.wait_page)
        # Page :: Model3dPage
        self.model3d_page = Model3dPage()
        self.addPage("Model3dPage", self.model3d_page)
        # Page :: NiceShot
        self.niceshot_page = NiceShot()
        self.addPage("NiceShot", self.niceshot_page)
        # Page :: NiceShotRecord
        self.niceshot_record_page = NiceShotRecord(self.cameraWidget)
        self.addPage("NiceShotRecord", self.niceshot_record_page)
        # Page :: Processing
        self.processing_page = Processing(cfg)
        self.addPage("Processing", self.processing_page)

        # page :: BaseballView
        self.baseball_page = BaseballSettingPage(self.cameraWidget)
        self.addPage("BaseballSettingPage", self.baseball_page)

        # Page :: ResultPage
        self.reault_keyframe_page = ResultPage_keyframe()
        self.addPage("ResultPage_keyframe", self.reault_keyframe_page)

        self.resultPage_angleAnalyze_page = ResultPage_angleAnalyze()
        self.addPage("ResultPage_angleAnalyze", self.resultPage_angleAnalyze_page)

        self.resultPage_angleDetail_page = Result_angleDetail()
        self.addPage("Result_angleDetail", self.resultPage_angleDetail_page)

        self.resultPage_powerChain_page = ResultPage_powerChain()
        self.addPage("ResultPage_powerChain", self.resultPage_powerChain_page)

        self.resultPage_3Dplot_page = ResultPage_3Dplot()
        self.addPage("ResultPage_3Dplot", self.resultPage_3Dplot_page)

        self.showPage("Home")

    def setBackgroundService(self, service:SystemService):
        if self.myService != None:
            self.closeService()
        self.myService = service

    def closeService(self):
        if self.myService.isRunning():
            logging.debug("stop system service")
            self.myService.stop()

    def addNodes(self, nodes):
        self.myService.addNodes(nodes)

    def addPage(self, name, page:QGroupBox):
        page.hide()
        page.setBackgroundService(self.myService)
        page.setFixedSize(PAGE_SIZE)
        page.setStyleSheet("background-color: #DDD9C3")

        self.layout_main.addWidget(page, 0, 1, Qt.AlignCenter)
        if name in self.pages:
            del self.pages[name]
        self.pages[name] = page

    def showPage(self, show_name):
        logging.debug(f"{self.__class__.__name__}: showPage -> {show_name}")
        if show_name not in self.pages:
            logging.warning(f"Page {name} is not exist.")
            return False
        for name, page in self.pages.items():
            if name is show_name:
                #self.setWindowTitle(name)
                page.show()
            else:
                page.hide()
        return True

    def handleMessage(self, msg:MsgContract):
        logging.debug(f"{self.__class__.__name__}: handleMessage")
        if msg.id == MsgContract.ID.PAGE_CHANGE:
            page_name = msg.value
            if page_name == "CameraSettingPage":
                self.camera_setting_page.setSelectedCameras(msg.data)
            if page_name == "ExtrinsicPage":
                self.extrinsic_page.setData(msg.data)
            if page_name == 'Check3dPage':
                self.check3d_page.setData(msg.data)
            self.showPage(page_name)
        elif msg.id == MsgContract.ID.TRACKNET_DONE:
            logging.debug(f"main page get [TRACKNET_DONE]")
            if msg.data == 'Processing':
                self.processing_page.startModel3D()
            else:
                self.wait_page.startModel3D()

if __name__ == '__main__':
    #updateLastExeDate()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    window.move(70,55)
    sys.exit(app.exec_())