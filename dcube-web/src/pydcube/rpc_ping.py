#!/usr/bin/env python
import DCM

#cli arguments
import argparse

#helper
from itertools import chain
import json
import logging

#List of all servers
SERVERS=["rpi%d"%x for x in range(80,82)]

#CLI arguments
parser=argparse.ArgumentParser(description="D-Cube RPC Client.")
parser.add_argument("--debug",action="store_true",help="Enable debug")

args=parser.parse_args()

level=logging.INFO
if args.debug:
    level=logging.DEBUG
    FORMAT = "[%(name)16s - %(funcName)12s() ] %(message)s"
else:
    FORMAT = "%(message)s"

logger=logging.getLogger(__name__)

logging.basicConfig(level=level,format=FORMAT)
logging.getLogger("pika").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

#clients
dcube=DCM.Client("broker","master","dcube","GWcq43x2",servers=SERVERS)

#ping all servers
logger.info("Checking if all %d Raspberry Pi nodes are pingable..."%len(SERVERS))
try:
    dcube.ping(timeout=5)
    logger.info("[OK] All nodes could be pinged correctly!")
except DCM.ServersUnresponseException as e:
    logger.error("[ERROR] Following nodes are not pingable:")
    for s in e.servers:
        logger.error("\t%s"%s)
    exit(-1)

