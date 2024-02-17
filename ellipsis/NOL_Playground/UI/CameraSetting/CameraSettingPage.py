import logging
import time
import ast
import multiprocessing as mp

from PyQt5.QtWidgets import QGroupBox, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QComboBox, QLabel, QSpinBox, QCheckBox
from PyQt5.QtCore import QSize

from UISettings import *
from Services import SystemService, MsgContract
from common import loadConfig, saveConfig, setIntrinsicMtx, loadCameraSetting, saveCameraSetting
from nodes import CameraReader

DIRNAME = os.path.dirname(os.path.abspath(__file__))
ROOTDIR = os.path.dirname(os.path.dirname(DIRNAME))

def applyOneResolutionFPS(brand, hw_id, fps, resolution):
    ret = 0
    try:
        tmp_info = dict({'node_type': None, 'brand': brand, 'hw_id': hw_id, 'output_topic': None})
        tmp_camera = CameraReader('tmp', tmp_info)
        tmp_cfg = loadCameraSetting(tmp_camera)
        tmp_cfg['Camera']['fps'] = fps
        tmp_cfg['Camera']['RecordResolution'] = resolution
        ret = saveCameraSetting(tmp_camera, tmp_cfg)
    except Exception as e:
        print(e)
        ret = -1
        return ret
    return ret

class CameraSettingPage(QGroupBox):
    def __init__(self, cameras:list):
        super().__init__()

        self.cameras = cameras
        self.cameraCfg = None

        self.selected_num_cameras = 0
        self.items_fps = ['30', '60', '120']
        self.items_resolution = ['(800, 600)', '(1024, 768)', '(1280, 720)', '(1440, 1080)']

        # setup UI
        self.setupUI()

    def hideEvent(self, event):
        logging.debug(f"{self.__class__.__name__}: hided.")

    def showEvent(self, event):
        logging.debug(f"{self.__class__.__name__}: shown.")

        # load default settings from config file(camera 0)
        self.init_combo_flag = True
        self.camera_cb.clear()
        items = [str(i) for i in range(self.selected_num_cameras)]
        self.camera_cb.addItems(items)
        self.camera_cb.setCurrentText('0')

        self.cameraCfg = loadCameraSetting(self.cameras[0])
        self.setLayoutValue()

    def setBackgroundService(self, service:SystemService):
        self.myService = service

    def setupUI(self):
        # 控制按鈕
        self.control_bar = self.getControlBar()

        # 設定區域
        self.setting_area = self.getSettingArea()

        layout_main = QHBoxLayout()
        layout_main.addWidget(self.control_bar)
        layout_main.addWidget(self.setting_area)

        self.setLayout(layout_main)

    def getControlBar(self):
        container = QWidget()
        container_layout = QVBoxLayout()

        # 選擇要設定哪台相機的參數
        self.camera_cb = QComboBox()
        self.camera_cb.currentIndexChanged.connect(self.onComboBoxChanged)
        self.camera_cb.setStyleSheet('font: 24px')
        self.camera_cb.setFixedSize(200,60)

        # Home
        self.btn_home = QPushButton()
        self.btn_home.setText('回首頁')
        self.btn_home.setFixedSize(QSize(200, 50))
        self.btn_home.setStyleSheet('font: 24px')
        self.btn_home.clicked.connect(self.backhome)

        # Apply
        self.btn_apply = QPushButton()
        self.btn_apply.setText('套用')
        self.btn_apply.setFixedSize(QSize(200, 50))
        self.btn_apply.setStyleSheet('font: 24px')
        self.btn_apply.clicked.connect(self.applySetting)

        # Apply resolution and fps to all cameras
        self.btn_apply_res_fps = QPushButton()
        self.btn_apply_res_fps.setText('套用至所有相機\n(解析度與FPS)')
        self.btn_apply_res_fps.setFixedSize(QSize(200, 100))
        self.btn_apply_res_fps.setStyleSheet('font: 24px')
        self.btn_apply_res_fps.clicked.connect(self.applyAllResolutionFPS)

        # Reset
        self.btn_reset = QPushButton()
        self.btn_reset.setText('重置')
        self.btn_reset.setFixedSize(QSize(200, 50))
        self.btn_reset.setStyleSheet('font: 24px')
        self.btn_reset.clicked.connect(self.resetSetting)

        container_layout.addWidget(self.camera_cb)
        container_layout.addWidget(self.btn_apply)
        container_layout.addWidget(self.btn_apply_res_fps)
        container_layout.addWidget(self.btn_reset)
        container_layout.addWidget(self.btn_home)
        container.setLayout(container_layout)
        return container

    def getSettingArea(self):
        spin_max_value = 99999999
        spin_min_value = -99999999

        container = QWidget()
        container_layout = QVBoxLayout()
        container.setFixedWidth(1200)

        # Brightness
        self.label_brightness = QLabel("Brightness:")
        self.label_brightness.setFont(UIFont.SpinBox)
        self.spin_brightness = QSpinBox()
        self.spin_brightness.setFont(UIFont.SpinBox)
        self.spin_brightness.setMinimum(spin_min_value)
        self.spin_brightness.setMaximum(spin_max_value)
        self.spin_brightness.setSingleStep(10)
        self.layout_brightness = QHBoxLayout()
        self.layout_brightness.addWidget(self.label_brightness)
        self.layout_brightness.addWidget(self.spin_brightness)

        # ExposureAuto
        self.label_exposure_auto = QLabel("ExposureAuto:")
        self.label_exposure_auto.setFont(UIFont.SpinBox)
        self.chkbox_exposure_auto = QCheckBox()
        self.chkbox_exposure_auto.clicked.connect(self.onExposureAutoClick)
        self.layout_exposure_auto = QHBoxLayout()
        self.layout_exposure_auto.addWidget(self.label_exposure_auto)
        self.layout_exposure_auto.addWidget(self.chkbox_exposure_auto)

        # ExposureTimeAbs
        self.label_exposure_time_abs = QLabel("ExposureTimeAbs:")
        self.label_exposure_time_abs.setFont(UIFont.SpinBox)
        self.spin_exposure_time_abs = QSpinBox()
        self.spin_exposure_time_abs.setFont(UIFont.SpinBox)
        self.spin_exposure_time_abs.setMinimum(spin_min_value)
        self.spin_exposure_time_abs.setMaximum(spin_max_value)
        self.layout_exposure_time_abs = QHBoxLayout()
        self.layout_exposure_time_abs.addWidget(self.label_exposure_time_abs)
        self.layout_exposure_time_abs.addWidget(self.spin_exposure_time_abs)

        # GainAuto
        self.label_gain_auto = QLabel("GainAuto:")
        self.label_gain_auto.setFont(UIFont.SpinBox)
        self.chkbox_gain_auto = QCheckBox()
        self.chkbox_gain_auto.clicked.connect(self.onGainAutoClick)
        self.layout_gain_auto = QHBoxLayout()
        self.layout_gain_auto.addWidget(self.label_gain_auto)
        self.layout_gain_auto.addWidget(self.chkbox_gain_auto)

        # Gain
        self.label_gain = QLabel("Gain:")
        self.label_gain.setFont(UIFont.SpinBox)
        self.spin_gain = QSpinBox()
        self.spin_gain.setFont(UIFont.SpinBox)
        self.spin_gain.setMinimum(spin_min_value)
        self.spin_gain.setMaximum(spin_max_value)
        self.spin_gain.setSingleStep(10)
        self.layout_gain = QHBoxLayout()
        self.layout_gain.addWidget(self.label_gain)
        self.layout_gain.addWidget(self.spin_gain)

        # BalanceWhiteAuto
        self.label_balance_white_auto = QLabel("BalanceWhiteAuto:")
        self.label_balance_white_auto.setFont(UIFont.SpinBox)
        self.chkbox_balance_white_auto = QCheckBox()
        self.chkbox_balance_white_auto.clicked.connect(self.onBalanceWhiteAutoClick)
        self.layout_balance_white_auto = QHBoxLayout()
        self.layout_balance_white_auto.addWidget(self.label_balance_white_auto)
        self.layout_balance_white_auto.addWidget(self.chkbox_balance_white_auto)

        # BalanceRatioRed
        self.label_balance_ratio_red = QLabel("BalanceRatioRed:")
        self.label_balance_ratio_red.setFont(UIFont.SpinBox)
        self.spin_balance_ratio_red = QSpinBox()
        self.spin_balance_ratio_red.setFont(UIFont.SpinBox)
        self.spin_balance_ratio_red.setMinimum(spin_min_value)
        self.spin_balance_ratio_red.setMaximum(spin_max_value)
        self.layout_balance_ratio_red = QHBoxLayout()
        self.layout_balance_ratio_red.addWidget(self.label_balance_ratio_red)
        self.layout_balance_ratio_red.addWidget(self.spin_balance_ratio_red)

        # BalanceRatioBlue
        self.label_balance_ratio_blue = QLabel("BalanceRatioBlue:")
        self.label_balance_ratio_blue.setFont(UIFont.SpinBox)
        self.spin_balance_ratio_blue = QSpinBox()
        self.spin_balance_ratio_blue.setFont(UIFont.SpinBox)
        self.spin_balance_ratio_blue.setMinimum(spin_min_value)
        self.spin_balance_ratio_blue.setMaximum(spin_max_value)
        self.layout_balance_ratio_blue = QHBoxLayout()
        self.layout_balance_ratio_blue.addWidget(self.label_balance_ratio_blue)
        self.layout_balance_ratio_blue.addWidget(self.spin_balance_ratio_blue)

        # FPS
        self.label_fps = QLabel("FPS:")
        self.label_fps.setFont(UIFont.SpinBox)
        self.combo_fps = QComboBox()
        self.combo_fps.addItems(self.items_fps)
        self.combo_fps.setFont(UIFont.SpinBox)
        self.combo_fps.currentIndexChanged.connect(self.changeFPS)
        self.layout_fps = QHBoxLayout()
        self.layout_fps.addWidget(self.label_fps)
        self.layout_fps.addWidget(self.combo_fps)

        # RecordResolution
        self.label_record_resolution = QLabel("RecordResolution:")
        self.label_record_resolution.setFont(UIFont.SpinBox)
        self.combo_record_resolution = QComboBox()
        self.combo_record_resolution.addItems(self.items_resolution)
        self.combo_record_resolution.setFont(UIFont.SpinBox)
        self.layout_record_resolution = QHBoxLayout()
        self.layout_record_resolution.addWidget(self.label_record_resolution)
        self.layout_record_resolution.addWidget(self.combo_record_resolution)

        container_layout.addLayout(self.layout_brightness)
        container_layout.addLayout(self.layout_exposure_time_abs)
        container_layout.addLayout(self.layout_exposure_auto)
        container_layout.addLayout(self.layout_gain)
        container_layout.addLayout(self.layout_gain_auto)
        container_layout.addLayout(self.layout_balance_ratio_red)
        container_layout.addLayout(self.layout_balance_ratio_blue)
        container_layout.addLayout(self.layout_balance_white_auto)
        container_layout.addLayout(self.layout_fps)
        container_layout.addLayout(self.layout_record_resolution)
        container.setLayout(container_layout)
        container.setFixedHeight(800)
        return container

    def setSelectedCameras(self, num):
        self.selected_num_cameras = num

    def changeFPS(self):
        pass

    def setLayoutValue(self):
        # set button value (camera number)
        self.btn_apply.setText(f'套用(相機 {self.camera_cb.currentText()})')
        self.btn_reset.setText(f'重置(相機 {self.camera_cb.currentText()})')

        self.spin_brightness.setValue(int(self.cameraCfg['Camera']['Brightness']))
        if self.cameraCfg['Camera']['ExposureAuto'] == 'On':
            self.chkbox_exposure_auto.setChecked(True)
        else:
            self.chkbox_exposure_auto.setChecked(False)
        self.spin_exposure_time_abs.setValue(int(self.cameraCfg['Camera']['ExposureTimeAbs']))
        if self.cameraCfg['Camera']['GainAuto'] == 'On':
            self.chkbox_gain_auto.setChecked(True)
        else:
            self.chkbox_gain_auto.setChecked(False)
        self.spin_gain.setValue(int(self.cameraCfg['Camera']['Gain']))
        if self.cameraCfg['Camera']['BalanceWhiteAuto'] == 'On':
            self.chkbox_balance_white_auto.setChecked(True)
        else:
            self.chkbox_balance_white_auto.setChecked(False)
        self.spin_balance_ratio_red.setValue(int(self.cameraCfg['Camera']['BalanceRatioRed']))
        self.spin_balance_ratio_blue.setValue(int(self.cameraCfg['Camera']['BalanceRatioBlue']))

        self.combo_fps.setCurrentText(self.cameraCfg['Camera']['fps'])
        self.fps_changed = False

        # convert to tuple first, prevent from format errors
        record_resolution = ast.literal_eval(self.cameraCfg['Camera']['RecordResolution'])
        self.combo_record_resolution.setCurrentText(str(record_resolution))

    def getLayoutValue(self):
        self.cameraCfg['Camera']['Brightness'] = str(self.spin_brightness.value())
        if self.chkbox_exposure_auto.isChecked():
            self.cameraCfg['Camera']['ExposureAuto'] = 'On'
        else:
            self.cameraCfg['Camera']['ExposureAuto'] = 'Off'
        self.cameraCfg['Camera']['ExposureTimeAbs'] = str(self.spin_exposure_time_abs.value())
        if self.chkbox_gain_auto.isChecked():
            self.cameraCfg['Camera']['GainAuto'] = 'On'
        else:
            self.cameraCfg['Camera']['GainAuto'] = 'Off'
        self.cameraCfg['Camera']['Gain'] = str(self.spin_gain.value())
        if self.chkbox_balance_white_auto.isChecked():
            self.cameraCfg['Camera']['BalanceWhiteAuto'] = 'On'
        else:
            self.cameraCfg['Camera']['BalanceWhiteAuto'] = 'Off'
        self.cameraCfg['Camera']['BalanceRatioRed'] = str(self.spin_balance_ratio_red.value())
        self.cameraCfg['Camera']['BalanceRatioBlue'] = str(self.spin_balance_ratio_blue.value())

        fps_now = self.combo_fps.currentText()
        if fps_now != self.cameraCfg['Camera']['fps']:
            self.fps_changed = True
        self.cameraCfg['Camera']['fps'] = fps_now

        self.cameraCfg['Camera']['RecordResolution'] = self.combo_record_resolution.currentText()

    def onComboBoxChanged(self):
        if self.init_combo_flag:
            self.init_combo_flag = False
            return
        cur_camera = int(self.camera_cb.currentText())
        self.cameraCfg = loadCameraSetting(self.cameras[cur_camera])
        self.setLayoutValue()

    def onExposureAutoClick(self):
        if self.chkbox_exposure_auto.isChecked():
            self.spin_exposure_time_abs.setEnabled(False)
        else:
            self.spin_exposure_time_abs.setEnabled(True)

    def onGainAutoClick(self):
        if self.chkbox_gain_auto.isChecked():
            self.spin_gain.setEnabled(False)
        else:
            self.spin_gain.setEnabled(True)

    def onBalanceWhiteAutoClick(self):
        if self.chkbox_balance_white_auto.isChecked():
            self.spin_balance_ratio_red.setEnabled(False)
            self.spin_balance_ratio_blue.setEnabled(False)
        else:
            self.spin_balance_ratio_red.setEnabled(True)
            self.spin_balance_ratio_blue.setEnabled(True)

    def applySetting(self):
        self.getLayoutValue()

        # send changes to cameras
        cur_camera = int(self.camera_cb.currentText())
        msg = MsgContract(MsgContract.ID.CAMERA_SETTING)
        msg.value = self.cameras[cur_camera]
        msg.data = dict(self.cameraCfg['Camera'])
        msg.data['Reinit'] = self.fps_changed
        self.myService.sendMessage(msg)

        # if fps_changed ask all other cameraReader to reinitialize
        for i in range(len(self.cameras)):
            if i == cur_camera:
                continue
            msg = MsgContract(MsgContract.ID.CAMERA_SETTING)
            msg.value = self.cameras[i]
            msg.data = dict()
            msg.data['Reinit'] = self.fps_changed
            self.myService.sendMessage(msg)

        # save changes to file
        saveCameraSetting(self.cameras[cur_camera], self.cameraCfg)

        # some time to wait for cameras ready
        time.sleep(1)

    def applyAllResolutionFPS(self):
        self.getLayoutValue()

        cur_fps = self.cameraCfg['Camera']['fps']
        cur_resolution = self.cameraCfg['Camera']['RecordResolution']

        p = mp.get_context("spawn").Pool(self.selected_num_cameras)
        res = []
        for i in range(self.selected_num_cameras):
            cam = self.cameras[i]
            res.append(p.apply_async(applyOneResolutionFPS, (cam.brand, cam.hw_id, cur_fps, cur_resolution)))

        for i, r in enumerate(res):
            try:
                ret_v = r.get()
                if ret_v == 0:
                    logging.debug(f'Apply camera[{i}] ok')
                elif ret_v == -2:
                    logging.debug(f'Apply camera[{i}] warning (< 4 pictures)')
                else:
                    logging.debug(f'Apply camera[{i}] error')
            except Exception as e:
                logging.debug(e)
                logging.error('Multiprocessing error..')

        p.close()
        p.join()

        # tell all cameras to reinit
        for i in range(self.selected_num_cameras):
            msg = MsgContract(MsgContract.ID.CAMERA_SETTING)
            msg.value = self.cameras[i]
            msg.data = dict({'Reinit': True, 'RecordResolution': cur_resolution})
            self.myService.sendMessage(msg)

        # some time to wait for cameras ready
        time.sleep(1)

    def resetSetting(self):
        self.setLayoutValue()

    def backhome(self):
        msg = MsgContract(MsgContract.ID.PAGE_CHANGE, value='CameraSystem')
        self.myService.sendMessage(msg)