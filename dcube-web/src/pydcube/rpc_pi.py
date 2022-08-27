#!/usr/bin/env python
import DCM
from DCM.raspi import Raspberry

import logging
import json
import argparse
import signal
import socket

logger=logging.getLogger(__name__)

def get_hostname():
    return socket.gethostname()

def signal_handler(signum,frame):
    logger.info("Signal to shutdown received")
    exit(0)
    
signal.signal(signal.SIGINT, signal_handler)

parser=argparse.ArgumentParser(description="D-Cube RPC server.")
parser.add_argument("--credentials",type=str,help="Credential JSON file")
parser.add_argument("--nodes",type=str,help="Node configuration file")
parser.add_argument("--hostname",type=str,default=get_hostname(),help="Override hostname")
parser.add_argument("--debug",action="store_true",help="Enable debug")

args=parser.parse_args()

level=logging.INFO
if args.debug:
    level=logging.DEBUG

FORMAT = "[%(name)16s - %(funcName)12s() ] %(message)s"
logging.basicConfig(level=level,format=FORMAT)
logging.getLogger("pika").setLevel(logging.WARNING)

if args.credentials==None:
    user_name="guest"
    user_pass="guest"
else:
    try:
        with open(args.credentials,'r') as f:
            try:
                j=json.load(f)
                user_name=j["username"]
                user_pass=j["password"]
            except ValueError as e:
                logger.error("Invalid credentials JSON file: %s!",e)
                exit(-1)
    except IOError:
        logger.error("Credential JSON file does not exist or cannot be opened!")
        exit(-1)
 
if args.nodes==None:
    nodes=[]
else:
    try:
        with open(args.nodes,'r') as f:
            try:
                j=json.load(f)
            except ValueError as e:
                logger.error("Invalid node JSON file: %s!",e)
                exit(-1)
            nodes=j
    except IOError:
        logger.error("Node JSON file does not exist or cannot be opened!")
        exit(-1)
 
dcube=Raspberry("192.168.100.19",args.hostname,user_name,user_pass,nodes)
dcube.run()
