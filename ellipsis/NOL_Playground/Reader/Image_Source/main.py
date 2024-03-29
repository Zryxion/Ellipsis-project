import argparse
import json
import os
import shutil
import sys
import threading
import logging
from typing import Optional
import paho.mqtt.client as mqtt
import prctl
import time
import ast

DIRNAME = os.path.dirname(os.path.abspath(__file__))
ROOTDIR = os.path.dirname(os.path.dirname(DIRNAME))
sys.path.append(f"{ROOTDIR}/lib")
from common import loadConfig, loadNodeConfig
from inspector import sendNodeStateMsg, sendPerformance
from camera import CameraReader
from publisher import RawImgPublisher
#from recorder import Recorder
from recorder import CameraRecorder

def parse_args() -> Optional[str]:
    # Args
    parser = argparse.ArgumentParser(description = 'CameraReader')
    parser.add_argument('--nodename', type=str, default = 'CameraReaderL', help = 'mqtt node name (default: CameraReader)')
    args = parser.parse_args()

    return args

killswitch = threading.Event()
client = None
cmds = {}

def main():
    # Parse arguments
    global args
    args = parse_args()
    prctl.set_name(args.nodename)
    # Load main_configs
    main_config_file = f"{ROOTDIR}/config"
    global main_configs
    main_configs = loadNodeConfig(main_config_file, args.nodename)

    # load camera config
    cfg_file = f"{DIRNAME}/config/{main_configs['hw_id']}.cfg"
    cfg = loadConfig(cfg_file)

    # tuple type
    record_resolution = ast.literal_eval(cfg['Camera']['RecordResolution'])

    # camera driver
    cameraReader = CameraReader(main_configs)

    # Main
    ## setup MQTT client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(main_configs['mqtt_broker'])

    try:
        client.loop_start()
        logging.info("{} is ready.".format(args.nodename))
        sendNodeStateMsg(client, args.nodename, "ready")
        rawImgPublisher = None
        recorder = None
        while True:
            killswitch.wait()
            logging.info(f"{args.nodename} received msg: {cmds}")
            if 'stop' in cmds:
                break
            elif 'streaming' in cmds:
                if cmds['streaming'] == True:
                    ## Publisher
                    rawImgPublisher = RawImgPublisher(main_configs['mqtt_broker'], main_configs['output_topic'])
                    rawImgPublisher.setResize(True, record_resolution[0], record_resolution[1])
                    rawImgPublisher.start()
                    cameraReader.setConsumer(rawImgPublisher)
                    cameraReader.startStreaming(cmds['start_timestamp'])
                else:
                    cameraReader.stopStreaming()
                    if rawImgPublisher is not None:
                        rawImgPublisher.stop()
            elif 'recording' in cmds:
                if cmds['recording'] == True:
                    logging.info("start recording...")
                    if 'path' in cmds:
                        video_path = cmds['path']
                        # create directory if not exists
                        os.makedirs(f"{video_path}", exist_ok=True)
                        # copy nodes config
                        destination = f"{video_path}/config"
                        shutil.copyfile(main_config_file, destination)
                        # copy device config
                        cfg_file = f"{DIRNAME}/config/{main_configs['hw_id']}.cfg"
                        destination = f"{video_path}/{main_configs['hw_id']}.cfg"
                        shutil.copyfile(cfg_file, destination)
                        # start to record
                        #recorder = Recorder(args.nodename, video_path, main_configs)
                        #recorder.start()
                        recorder = CameraRecorder(args.nodename, video_path, main_configs)
                        recorder.start()
                        cameraReader.setConsumer(recorder)
                        cameraReader.startStreaming()
                    else:
                        logging.warning("please set video path in cmds('path') or camera is in recording")
                else:
                    cameraReader.stopStreaming()
                    if recorder != None:
                        time.sleep(2)
                        recorder.stop()
                        recorder = None
            elif 'screenshot' in cmds:
                if 'path' in cmds:
                    rawImgPublisher.screenshot(cmds['path'])
                else:
                    logging.warning("please set video path in cmds('save_path') or camera is in streaming")

            if 'ExposureAuto' in cmds:
                cameraReader.setProperties('ExposureAuto', cmds['ExposureAuto'])
            if 'Gain' in cmds:
                cameraReader.setProperties('Gain', cmds['Gain'])
            if 'GainAuto' in cmds:
                cameraReader.setProperties('GainAuto', cmds['GainAuto'])
            if 'Brightness' in cmds:
                cameraReader.setProperties('Brightness', cmds['Brightness'])
            if 'BalanceWhiteAuto' in cmds:
                cameraReader.setProperties('BalanceWhiteAuto', cmds['BalanceWhiteAuto'])
            if 'ExposureTimeAbs' in cmds:
                cameraReader.setProperties('ExposureTimeAbs', cmds['ExposureTimeAbs'])
            if 'BalanceRatioRed' in cmds:
                cameraReader.setProperties('BalanceRatioRed', cmds['BalanceRatioRed'])
            if 'BalanceRatioBlue' in cmds:
                cameraReader.setProperties('BalanceRatioBlue', cmds['BalanceRatioBlue'])

            # fps_changed needs to restart camera
            if 'Reinit' in cmds and cmds['Reinit']:
                cameraReader.reInitial()

            if 'RecordResolution' in cmds:
                record_resolution = ast.literal_eval(cmds['RecordResolution'])
                if rawImgPublisher is not None:
                    rawImgPublisher.setResize(True, width=record_resolution[0], height=record_resolution[1])

            killswitch.clear()
    finally:
        cameraReader.close()
        if rawImgPublisher is not None:
            rawImgPublisher.stop()
        if recorder is not None:
            recorder.stop()
        sendNodeStateMsg(client, args.nodename, "terminated")
        client.loop_stop()

def on_connect(client, userdata, flag, rc):
    logging.info(f"{args.nodename} Connected with result code: {rc}")
    client.subscribe(args.nodename)
    client.subscribe(main_configs['general_topic'])

def on_message(client, userdata, msg):
    global cmds
    cmds = json.loads(msg.payload)
    killswitch.set()

if __name__ == '__main__':
    main()

# python3 Reader/Image_Source/main.py --nodename CameraReaderL
# mosquitto_pub -h localhost -t CameraReaderL -m "{\"recording\": true, \"path\": \".\/replay\/test\/\"}"
# mosquitto_pub -h localhost -t CameraReaderL -m "{\"recording\": false}"