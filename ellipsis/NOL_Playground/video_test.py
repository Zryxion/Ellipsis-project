import logging
import os
from lib.common import setIntrinsicMtxfromVideo
from lib.Calibration import Calibration

logging.getLogger().setLevel(logging.DEBUG)
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s")

def test(name):

    config_path = f"Reader/Image_Source/config/{name}.cfg"
    folder_path = f"Reader/Image_Source/intrinsic_data/{name}/"
    res = "(1440, 1080)"

    #c = Calibration((1440, 1080), folder_path, 7, 14)
    #c.readVideo()
    #rms_err, avg_err, mtx, dist, rvecs, tvecs = c.calibrateCamera()
    #print(f"name:{name}, rms_err:{rms_err:.3f}, avg_err:{avg_err:.3f}")

    setIntrinsicMtxfromVideo(config_path, folder_path, res)

test('test_45220220')
test('test_40224283')