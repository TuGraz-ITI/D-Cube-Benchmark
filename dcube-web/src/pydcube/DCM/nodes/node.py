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
import json
import logging

class Node:
    def __init__(self, name, mayor, minor, vendor_id=None, product_id=None, tempdir="/tmp"):
        self.logger=logging.getLogger("D-Cube Node")
        self.name=name
        self.vendor_id=vendor_id
        self.product_id=product_id
        self.mayor=mayor
        self.minor=minor
        self.tracer=None
        self.tempdir=tempdir

    def start_traces(self):
        return CommandReturn.FAILED

    def stop_traces(self):
        return CommandReturn.FAILED

    def collect_traces(self):
        return CommandReturn.FAILED

    def program(self,hexfile,connection):
        return CommandReturn.FAILED

    def erase(self):
        return CommandReturn.FAILED

    def __repr__(self):
        return "%s"%self.name

    def toJSON(self):
        d={}
        d['name']=self.name
        return json.dumps(d)


class NodeFactory:
    nodes=None
    def __init__(self):
        if not NodeFactory.nodes:
            NodeFactory.nodes={}

    def register_node(self, name, function):
        NodeFactory.nodes[name]=function
    
    def create_node(self, name, mayor, minor, tempdir="/tmp"):
        if name in NodeFactory.nodes:
            return NodeFactory.nodes[name](name=name,mayor=mayor,minor=minor,tempdir=tempdir)
        else:
            return None
