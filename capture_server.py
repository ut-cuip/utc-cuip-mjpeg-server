"""Manages the stream of some URL-based camera"""
import time
import traceback

import cv2


class CaptureProcessor:
    """A class which fetches video from a prescribed location
    Args:
        capture_url (str): The url to open with OpenCV to fetch the stream from
        cam_id (str): The ID of the camera - should be unique, used for identification later
        anonymous (bool): Whether or not the video feed should be anonymized
        queue (multiprocessing.Queue, torch.multiprocessing.Queue): Used for message passing
    """

    def __init__(self, capture_url, cam_id, queue):
        self.cap_url = capture_url
        self.camera_id = cam_id
        self.queue = queue

    def start(self):
        """The main loop of the Stream processor"""
        while True:
            last_fps = time.time()
            frames = 0
            cap = cv2.VideoCapture()
            cap.open(self.cap_url)
            while True:
                start = time.time()
                ret, frame = cap.read()
                # Return if we can't retreive the frame
                if not ret:
                    cap.release()
                    del cap
                    break
                frames += 1
                if (time.time() - last_fps) >= 1:
                    print("{} is getting {}FPS".format(self.camera_id, frames))
                    frames = 0
                    last_fps = time.time()
                self.queue.put((self.camera_id, frame), block=True)
                del frame
                time.sleep(max((1 / 30) - (time.time() - start), 0))
            time.sleep(10)
