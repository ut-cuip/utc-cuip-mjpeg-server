"""A process for hosting video feeds via Quart"""
import asyncio
import json
import time

import cv2
from quart import Quart, Response, make_response, redirect, render_template, request


class QuartServer:
    def __init__(self, port, config, queues, target_res=(1920, 1080)):
        self.app = Quart("{}-{}".format(__name__, port))
        self.app.clients = {x["camera_id"]: set() for x in config}
        self.app.frames = {}
        self.port = port
        self.config = config
        self.res = target_res
        self.queues = queues
        self.app.cameras = {
            x["camera_id"]: self.queues[x["camera_id"]] for x in self.config
        }

    def update_frames_from_queue(self, cam_id):
        """Updates the frames using the shared queue"""
        if (
            self.app.cameras[cam_id].qsize() > 0
            and not self.app.cameras[cam_id].empty()
        ):
            cam_id, frame = self.app.cameras[cam_id].get(block=True)
            _, frame = cv2.imencode(
                ".jpg",
                cv2.resize(frame, self.res),
                params=(cv2.IMWRITE_JPEG_QUALITY, 70),
            )
            self.app.frames[cam_id] = frame.tobytes()
            del cam_id, frame

    def stop(self):
        raise KeyboardInterrupt

    def start(self):
        """Kicks off the Quart server"""
        routes = {
            x["camera_id"]: "/video_feed/{}".format(x["camera_id"]) for x in self.config
        }

        @self.app.before_serving
        async def update_frame():
            """Done before providing a page"""
            start_time = time.time()
            loop = asyncio.get_event_loop()
            # Iterate through every client, make sure it's updating frames
            for cam_id in self.app.cameras:
                await loop.run_in_executor(None, self.update_frames_from_queue, cam_id)
                for queue in self.app.clients[cam_id]:
                    await queue.put(1)
            await asyncio.sleep(1 / 30 - (time.time() - start_time))
            asyncio.get_event_loop().create_task(update_frame())

        @self.app.route("/")
        async def default_route():

            return await render_template("index.html", routes=json.dumps(routes))

        @self.app.route("/video_feed/<name>/")
        async def video_feed(name):
            """Endpoint for anonymous video feeds"""
            if name not in self.app.frames:
                return "<center>This stream doesn't exist [yet?]</center>"
            queue = asyncio.Queue(10)
            queue.put(1)
            self.app.clients[name].add(queue)

            async def send_frame():
                while True:
                    try:
                        _ = await queue.get()
                        yield b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + self.app.frames[
                            name
                        ] + b"\r\n\r\n"
                    except:
                        try:
                            self.app.clients[name].remove(queue)
                        except KeyError:
                            pass

            response = await make_response(send_frame())
            response.timeout = None
            return (
                response,
                {"Content-Type": "multipart/x-mixed-replace; boundary=frame"},
            )

        self.app.run(host="0.0.0.0", port=self.port)

    def __getstate__(self):
        """An override for loading this object's state from pickle"""
        ret = {
            "port": self.port,
            "config": self.config,
            "res": self.res,
            "queues": self.queues,
        }
        return ret

    def __setstate__(self, dict_in):
        """An override for pickling this object's state"""
        self.app = Quart("{}-{}".format(__name__, dict_in["port"]))
        self.app.clients = {x["camera_id"]: set() for x in dict_in["config"]}
        self.config = dict_in["config"]
        self.app.frames = {}
        self.port = dict_in["port"]
        self.res = dict_in["res"]
        self.queues = dict_in["queues"]
        self.app.cameras = {
            x["camera_id"]: self.queues[x["camera_id"]] for x in self.config
        }
