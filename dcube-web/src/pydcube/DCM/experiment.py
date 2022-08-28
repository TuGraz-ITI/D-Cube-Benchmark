#
# MIT License
#
# Copyright (c) 2022 Graz University of Technology
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
import logging
import threading
import subprocess
import signal

def terminate_process(process):
    p=process
    #p.terminate()
    p.send_signal(signal.SIGINT)
    try: 
        outs,errs=p.communicate(timeout=15)
        return True
    except subprocess.TimeoutExpired:
        return False
    except ValueError:
        return False

class Experiment:

    def __init__(self,job_id,connection):
        self.logger=logging.getLogger("Experiment")
        self.connection=connection
        self.job_id=job_id
        self.processes={}

    def stop(self,request,response):
        dump={}
        for k in self.processes.keys():
            p=self.processes[k]
            self.logger.debug("Terminating process %d"%p.pid)
            if p.poll()==None:
                t=threading.Thread(target=terminate_process,args=(p,))
                t.start()
                while(t.isAlive()):
                    self.connection.sleep(1)
                if not t.join():
                    #give up on gracefull 
                    self.logger.debug("\tProcess did not respond in time, killing")
                    p.kill()
                    try:
                        outs,errs=p.communicate()
                    except ValueError:
                        outs=b''
                        errs=b''
            else:
                outs,errs=p.communicate()
            self.logger.debug("Ended process %d with return code %d"%(p.pid,p.returncode))
            self.logger.debug("STDOUT:")
            self.logger.debug(outs)
            self.logger.debug("STDERR:")
            self.logger.debug(errs)
            dump[p.pid]={"stdout":outs.decode(),"stderr":errs.decode()}
        response["output"]=dump
        self.processes=None

    def get_job_id(self):
        return self.job_id
