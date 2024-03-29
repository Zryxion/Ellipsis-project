import base64
import logging
import os
import pickle
import queue
import threading
import json
import gi
import cv2
import paho.mqtt.client as mqtt
import prctl
from turbojpeg import TurboJPEG, TJPF_BGRX
gi.require_version("Tcam", "0.1")
gi.require_version("Gst", "1.0")
from gi.repository import Gst

DIRNAME = os.path.dirname(os.path.abspath(__file__))
ROOTDIR = os.path.dirname(os.path.dirname(DIRNAME))

from camera import convert_sample_to_numpy

class RawImgPublisher(threading.Thread):
    def __init__(self, broker, output_topic, queue_size=120):
        threading.Thread.__init__(self)
        self.waitEvent = threading.Event()

        self.frame_queue = queue.Queue(maxsize=queue_size)

        # max FPS: camera FPS
        self.interval = 0
        self.isResize = True
        self.width = 800
        self.height = 600
        self.last_send_t = 0

        # feature: screenshot
        self.oneShot = False
        self.oneShotPath = f"{ROOTDIR}/replay/screenshot.jpg"

        self.broker = broker
        self.output_topic = output_topic
        logging.info(f"output topic: {output_topic}")

        self.jpeg = TurboJPEG('/usr/lib/x86_64-linux-gnu/libturbojpeg.so.0')

    def stop(self):
        self.alive = False
        self.waitEvent.set()

    def screenshot(self, saved_path):
        self.oneShotPath = saved_path
        self.oneShot = True
        self.waitEvent.set()

    def try_put_frame(self, fid, sample, timestamp_base):
        try:
            timestamp_frame, image = convert_sample_to_numpy(sample)
            timestamp = timestamp_base + timestamp_frame
            if self.isResize:
                image = cv2.resize(image, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
            self.frame_queue.put_nowait((fid, image, timestamp))
            self.waitEvent.set()
        except queue.Full:
            self.frame_queue.queue.clear()
            logging.warning(f"publisher[{self.output_topic}] frame queue is full.")
            pass

    def setResize(self, flag, width=800, height=600):
        self.isResize = flag
        self.width = width
        self.height = height

    def run(self):
        self.alive = True
        prctl.set_name("publisher")
        # setup MQTT client
        client = mqtt.Client()
        client.connect(self.broker)
        logging.info("Raw Image Publisher is ready.")
        while self.alive:
            if self.frame_queue.qsize() > 2:
                fid, image, timestamp = self.frame_queue.get()
                # screen shot origin picture
                if self.oneShot:
                    cv2.imwrite(self.oneShotPath, image)
                    self.oneShot = False
                    continue

                if (timestamp - self.last_send_t) > self.interval:
                    # publish raw image
                    buf = self.jpeg.encode(image, pixel_format=TJPF_BGRX)
                    imdata = pickle.dumps(buf)
                    payload = { 'id': fid, 'timestamp': timestamp, 'raw_data': base64.b64encode(imdata).decode('ascii')}
                    client.publish(self.output_topic, json.dumps(payload))

                    self.last_send_t = timestamp
            else:
                self.waitEvent.wait()
                self.waitEvent.clear()
        logging.info("Raw Image Publisher terminated.")
