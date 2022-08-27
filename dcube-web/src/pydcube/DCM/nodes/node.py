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
