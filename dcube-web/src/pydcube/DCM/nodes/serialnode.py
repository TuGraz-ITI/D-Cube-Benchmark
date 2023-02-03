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
from ..command import CommandReturn
from .node import Node

import usb.core
import pyudev
import subprocess
import os
import json
import base64
import time

class SerialNode(Node):

    def __init__(self, name, mayor, minor, vendor_id=None, product_id=None, tempdir="/tmp"):
        self.SERIALDUMP="./serialdump-new"
        self.SERIALDUMP_FOLDER="/home/pi"
        self.SERIALDUMP_OPTION_TIMESTAMP="-t"
        self.SERIALDUMP_OPTION_BAUDRATE="-b115200"
        #self.SERIALDUMP_OPTION_FORMAT=" -T#Y-%m-%d %H:%M:%S.%6N"
        super().__init__(name,mayor,minor,vendor_id,product_id,tempdir)

    def get_serial(self):
        dev=usb.core.find(idVendor=self.vendor_id,idProduct=self.product_id)
        if not dev==None:
            return dev.serial_number
        return None

    def get_product(self):
        dev=usb.core.find(idVendor=self.vendor_id,idProduct=self.product_id)
        if not dev==None:
            return dev.product
        return None

    def get_port(self):
        serial=self.get_serial()
        if serial==None:
            return None
        context = pyudev.Context()
        for device in context.list_devices(subsystem="tty"):
            if device.get("ID_SERIAL_SHORT", "") == serial:
                return device.device_node
        return None

    def start_traces(self):
        if self.tracer==None:
            self.stdout=open(os.path.join(self.tempdir,"stdout.log"),"w")
            self.stderr=open(os.path.join(self.tempdir,"stderr.log"),"w")
            workdir=self.SERIALDUMP_FOLDER
            cmd=[self.SERIALDUMP,self.SERIALDUMP_OPTION_BAUDRATE,self.SERIALDUMP_OPTION_TIMESTAMP,self.get_port()]
            self.logger.debug("Command: %s"%cmd)
            self.tracer=subprocess.Popen(cmd,cwd=workdir,stdout=self.stdout,stderr=self.stderr, close_fds=True)
            return CommandReturn.SUCCESS
        else:
            return CommandReturn.FAILED

    def stop_traces(self):
        if self.tracer==None:
            return CommandReturn.FAILED
        else:
            self.tracer.terminate()
            self.tracer.kill()
            self.tracer.communicate()
            self.tracer.wait()
            self.tracer.communicate()
            self.stdout.flush()
            self.stdout.close()
            self.stderr.flush()
            self.stderr.close()
            self.tracer=None
        return CommandReturn.SUCCESS

    def collect_traces(self):
        with open(os.path.join(self.tempdir,"stdout.log"),"rb") as f:
            enc=base64.b64encode(f.read())
            string=enc.decode()
        return string

    def __repr__(self):
        return "%s: %s - %s"%(self.name,self.get_serial(),self.get_port())

    def toJSON(self):
        d={}
        d['name']=self.name
        d['serial']=self.get_serial()
        d['port']=self.get_port()
        d['product']=self.get_product()
        return json.dumps(d)
