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
from .server import Server
from .command import CommandState,CommandReturn

import subprocess
import os
import stat
import shutil
import base64

from zipfile import ZipFile

class Linux(Server):

################################################################################
# Select node using the mux
################################################################################

    def cmd_select_node(self,request,response):
        ret=CommandReturn.FAILED
        response["message"]="Linux nodes do not have motes!"
        return ret
    
################################################################################
# Command to control node power
################################################################################

    def cmd_power(self,request,response):
        ret=CommandReturn.FAILED
        response["message"]="Linux nodes do not support changing power!"
        return ret

################################################################################
# Command to control node reset
################################################################################

    def cmd_reset(self,request,response):
        ret=CommandReturn.FAILED
        response["message"]="Linux nodes do not support reset!"
        return ret

################################################################################
# Command to program the node
################################################################################

    def cmd_program(self,request,response):
        self.logger.debug("Programming node...")
        tempfile=os.path.join(self.tempdir,"temp.zip")
        if "zipfile" in request:
            zipfile=base64.b64decode(request["zipfile"])
            with open(tempfile,"wb") as f:
                f.write(zipfile)
        elif not self.experiment==None:
            job_id=self.experiment.get_job_id()
            job=self.rest.get_job(job_id)
            if job==None:
                response["message"]="Job does not exist"
                return CommandReturn.FAILED

            zipfile=self.rest.get_firmware(job_id)
            with open(tempfile,"wb") as f:
                f.write(zipfile)

            if ("patch" in job and job["patch"]) or \
                ("cpatch" in job and job["cpatch"]):
                response["message"]="Patching not supported yet!"
                self.logger.error(response["message"])
                return CommandReturn.FAILED

        workdir=os.path.join(self.tempdir,"work")
        if os.path.exists(workdir):
            shutil.rmtree(workdir)
        os.mkdir(workdir)

        try:
            with ZipFile(tempfile) as zf:
                zf.extractall(path=workdir)
        except ValueError:
            response["message"]="Not a zipfile!"
            return CommandReturn.FORMAT

        entrypoint=os.path.join(workdir,"entrypoint.sh")
        if os.path.exists(entrypoint):
            st=os.stat(entrypoint)
            os.chmod(entrypoint,st.st_mode | stat.S_IEXEC )
        else:
            response["message"]="No entrypoint found!"
            return CommandReturn.FORMAT

        cmd = [entrypoint,]

        try:
            p=subprocess.Popen(cmd,cwd=workdir,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        except FileNotFoundError as e:
           response["message"]="File does not exist!"
           self.logger.error(response["message"])
           return CommandReturn.FAILED

        self.experiment.processes[p.pid]=p
        return CommandReturn.SUCCESS

################################################################################
# Collecting output from scripts
################################################################################

    def collect_traces(self):
        workdir=os.path.join(self.tempdir,"work")
        outdir=os.path.join(workdir,"output")
        outfile=os.path.join(self.tempdir,"output.zip")

        if os.path.exists(outfile):
            os.remove(outfile)

        if os.path.exists(outdir):
            shutil.make_archive(os.path.splitext(outfile)[0],os.path.splitext(outfile)[1][1:],outdir)
        else:
            with ZipFile(outfile,"w") as zf:
                pass

        with open(outfile,"rb") as f:
            enc=base64.b64encode(f.read())
            return enc.decode()


    def cmd_trace(self,request,response):
        ret=CommandReturn.SUCCESS
        if "state" in  request:
            if request["state"]==CommandState.ON:
                self.logger.debug("Starting trace collection...")
            if request["state"]==CommandState.OFF:
                self.logger.debug("Stopping trace collection...")
                response["logs"]=self.collect_traces()
                response["ext"]="zip"
        else:
            self.logger.error("No state given for trace collection!")
            ret=CommandReturn.FAILED
        return ret


################################################################################
# Commands for the measurement service
################################################################################

    def cmd_measurement(self,request,response):
        if "state" in request:
            if request["state"]==CommandState.ON:
                self.measurement_started=True
            elif request["state"]==CommandState.OFF:
                self.measurement_started=False

        response["message"]=self.get_measurement()
        return CommandReturn.SUCCESS

    def get_measurement(self):
        if self.measurement_started:
            return CommandReturn.STOPPED
        else:
            return CommandReturn.RUNNING

################################################################################
# Command list currnt nodes
################################################################################

    def motelist(self):
        motes=[]
        return motes

################################################################################
# Command to indicate the server to reboot
################################################################################

    def cmd_reboot(self,request,response):
        ret=CommandReturn.FAILED
        response["message"]="Linux nodes cannot be rebooted!"
        return ret

################################################################################
# Command dispatcher
################################################################################

    def __init__(self, host, hostname, user_name, user_pass, nodes=[], tempdir="/tmp", resturl="http://dcube-web"):
        super().__init__(host, hostname, user_name, user_pass, nodes, tempdir)
        self.measurement_started=False

        #change default values
        self.JAMMING_PWD="/tmp"
        self.JAMMING_CMD="true"

 
