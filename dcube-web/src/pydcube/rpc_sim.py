#!/usr/bin/env python
#
# MIT License
#
# Copyright (c) 2023 Graz University of Technology
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
import DCM
from DCM.sim import Simulation

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

parser=argparse.ArgumentParser(description="D-Cube RPC simulation server.")
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
 
simly=Simulation("rabbitmq",args.hostname,user_name,user_pass,nodes,resturl="http://dcube-web")
simly.run()
