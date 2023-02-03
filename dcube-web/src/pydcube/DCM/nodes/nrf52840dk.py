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
from .serialnode import SerialNode
from .node import Node
from ..command import CommandReturn
import subprocess
import os

class NRFJLink(SerialNode):

    def __init__(self,name,mayor,minor,vendor_id=0x1366,product_id=0x0105,tempdir="/tmp"):

        self.JLINK_FOLDER="/home/pi/jlink/JLink_Linux_V644b_arm"
        self.JLINK_COMMAND="./JLinkExe"
        self.JLINK_OPTION_DEVICE="-device"
        self.JLINK_DEVICE="nRF52840_xxAA"
        self.JLINK_OPTION_INTERFACE="-if"
        self.JLINK_INTERFACE="swd"
        self.JLINK_OPTIONS_AUTOCONNECT="-autoconnect"
        self.JLINK_AUTOCONNECT="1"
        self.JLINK_OPTION_SPEED="-speed"
        self.JLINK_SPEED="12000"
        self.JLINK_OPTION_COMMANDSCRIPT="-CommanderScript"
        self.JLINK_CMDFILE="jlink.cmd"
        super().__init__(name,mayor,minor,vendor_id,product_id,tempdir)

    def program(self,hexfile,connection):
        workdir=self.JLINK_FOLDER
        cmdfile=os.path.join(self.tempdir,self.JLINK_CMDFILE)
        script="connect\nw4 4001e504 2\nw4 4001e50c 1\nsleep 1000\nw4 4001e514 1\nsleep 1000\nerase\nloadfile %s\nw4 0x10001200 0x12\nw4 0x10001204 0x12\nexit" % hexfile
        with open(cmdfile,"w") as f:
            f.write(script)
        cmd=[self.JLINK_COMMAND, self.JLINK_OPTION_DEVICE, self.JLINK_DEVICE,self.JLINK_OPTION_INTERFACE,
                self.JLINK_INTERFACE, self.JLINK_OPTIONS_AUTOCONNECT, self.JLINK_AUTOCONNECT,
                self.JLINK_OPTION_SPEED, self.JLINK_SPEED, self.JLINK_OPTION_COMMANDSCRIPT, cmdfile]
        self.logger.debug("Command: %s"%cmd)
        self.logger.debug("Script: %s"%script)
        process=subprocess.Popen(cmd,cwd=workdir,stdout=subprocess.PIPE,stderr=subprocess.PIPE,close_fds=True)
        while process.poll() is None:
            connection.sleep(1)
        outs, errs = process.communicate()
        self.logger.debug(outs)
        self.logger.debug(errs)
        if "O.K." in outs.decode():
            return CommandReturn.SUCCESS
        elif "File is of unknown / unsupported format." in outs.decode():
            return CommandReturn.FORMAT
        else:
            return CommandReturn.FAILED

class NRFNative(Node):
    pass
