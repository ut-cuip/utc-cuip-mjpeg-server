import time
from threading import Thread

import cv2
from flask import Flask, Response, abort, request


class FlaskServer:
    def __init__(self, port, queues, config):
        self.port = port
        self.flask = Flask("MJPEG Server")
        self.queues = queues
        self.frames = {}
        self.thread = None
        self.workers = {}
        self.config = config

    def start(self):
        gen_function = self.gen

        @self.flask.route("/<endpoint>")
        def video_feed(endpoint):
            """Route which renders solely the video"""
            if endpoint in self.frames:
                return Response(
                    gen_function(endpoint),
                    mimetype="multipart/x-mixed-replace; boundary=jpgboundary",
                )
            else:
                return abort(404)

        self.thread = Thread(
            daemon=True,
            target=self.flask.run,
            kwargs={
                "host": "0.0.0.0",
                "port": self.port,
                "debug": False,
                "threaded": True,
            },
        )
        for x in self.config["cameras"]:
            self.workers[x["camera_id"]] = Thread(
                daemon=True, target=self.update_frames, args=(x["camera_id"],)
            )
        for cam_id in self.workers:
            self.workers[cam_id].start()
        self.thread.start()

    def update_frames(self, cam_id):
        while True:
            frame = self.queues[cam_id].get(block=True)
            self.frames[cam_id] = frame
            # We don't sleep here because we rely on sleeping on the capture end

    def get_frame(self, frame):
        """Encodes the OpenCV image to a 1920x1080 image"""
        _, jpeg = cv2.imencode(
            ".jpg",
            cv2.resize(frame, (1920, 1080)),
            params=(cv2.IMWRITE_JPEG_QUALITY, 70),
        )
        return jpeg.tobytes()

    def gen(self, endpoint):
        """A generator for the image."""
        header = "--jpgboundary\r\nContent-Type: image/jpeg\r\n"
        prefix = ""
        while True:
            start_time = time.time()
            msg = (
                prefix
                + header
                + "Content-Length: {}\r\n\r\n".format(
                    len(self.get_frame(self.frames[endpoint]))
                )
            )

            yield (msg.encode("utf-8") + self.get_frame(self.frames[endpoint]))
            prefix = "\r\n"
            time.sleep(max(0, (1 / 30) - (time.time() - start_time)))

    def __getstate__(self):
        """An override for loading this object's state from pickle"""
        ret = {"port": self.port, "queues": self.queues, "config": self.config}
        return ret

    def __setstate__(self, dict_in):
        """An override for pickling this object's state"""
        self.port = dict_in["port"]
        self.flask = Flask("MJPEG Server")
        self.queues = dict_in["queues"]
        self.frames = {}
        self.thread = None
        self.workers = {}
        self.config = dict_in["config"]
