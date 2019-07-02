import os
import time
import multiprocessing

import cv2
import yaml
from capture_server import CaptureProcessor
from flask_server import FlaskServer


def main(config):
    multiprocessing.set_start_method("spawn", force=True)

    # Create a dict of queues: key = cam_id, val = queue
    queues = {x["camera_id"]: multiprocessing.Queue(1) for x in config["cameras"]}
    # Create the server to run on port 3030
    flask_server = FlaskServer(3030, queues, config)
    # Generate cap processor for each of the entries in config.yaml
    cap_processors = [
        CaptureProcessor(x["url"], x["camera_id"], queues[x["camera_id"]])
        for x in config["cameras"]
    ]
    # Append each cap process's start method to the processes list
    processes = []
    for processor in cap_processors:
        processes.append(multiprocessing.Process(target=processor.start))

    flask_server.start()

    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join()
    except KeyboardInterrupt:
        for process in processes:
            process.terminate()


if __name__ == "__main__":
    if os.path.exists("config.yaml"):
        with open("config.yaml", "r") as file:
            config = yaml.load(file, Loader=yaml.Loader)
            main(config)
    else:
        print("No config.yaml found; exiting")
        exit()
