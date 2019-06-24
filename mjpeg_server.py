import os
import time
import multiprocessing

import cv2
import yaml
from capture_server import CaptureProcessor
from quart_server import QuartServer


def main(config):
    multiprocessing.set_start_method("spawn", force=True)

    # Create a dict of queues: key = cam_id, val = queue
    queues = {x["camera_id"]: multiprocessing.Queue(10) for x in config["cameras"]}
    # Create the quart server to run on port 3030
    quart_server = QuartServer(3030, config["cameras"], queues)
    # Generate cap processor for each of the entries in config.yaml
    cap_processors = [
        CaptureProcessor(x["url"], x["camera_id"], queues[x["camera_id"]])
        for x in config["cameras"]
    ]
    # Append each cap process's start method to the processes list
    processes = []
    for processor in cap_processors:
        processes.append(multiprocessing.Process(target=processor.start))
    processes.append(multiprocessing.Process(target=quart_server.start))

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
