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
from ..command import CommandReturn
import subprocess

class Sky(SerialNode):

    def __init__(self,name,mayor,minor,vendor_id=0x0403,product_id=0x6001,tempdir="/tmp"):
        self.BSL_OPTION_COMPORT="-c"
        self.BSL_OPTION_MASSERASE="-e"
        self.BSL_OPTION_IHEX="-I"
        self.BSL_OPTION_PROGRAM="-p"
        self.BSL_OPTION_RESET="-r"
        self.BSL_OPTION_NODE="--telosb"
        self.BSL_COMMAND="./msp430-bsl-linux"
        self.BSL_FOLDER="/home/pi/contiki_ewsn/tools/sky/"
        super().__init__(name,mayor,minor,vendor_id,product_id,tempdir)

    def program(self,hexfile,connection):
        workdir=self.BSL_FOLDER
        cmd=["/usr/bin/python2",self.BSL_COMMAND, self.BSL_OPTION_NODE, self.BSL_OPTION_COMPORT, self.get_port(), 
                self.BSL_OPTION_MASSERASE, self.BSL_OPTION_IHEX, self.BSL_OPTION_PROGRAM, hexfile]
        self.logger.debug("Command: %s"%cmd)
        process=subprocess.Popen(cmd,cwd=workdir,stdout=subprocess.PIPE,stderr=subprocess.PIPE,close_fds=True)
        while process.poll() is None:
            connection.sleep(1)
        outs, errs = process.communicate()
        self.logger.debug(outs)
        self.logger.debug(errs)
        if "bytes programmed." in errs.decode():
            return CommandReturn.SUCCESS
        elif "File Format Error" in errs.decode():
            return CommandReturn.FORMAT
        elif "Unknown header" in errs.decode():
            return CommandReturn.FORMAT
        else:
            return CommandReturn.FAILED
