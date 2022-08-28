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
from flask import current_app

import traceback

from models.job import Job
from models.layout_pi import LayoutPi
from models.layout_composition import LayoutComposition

from influxdb import InfluxDBClient
from collections import namedtuple
import influxdb
import math
import time
from datetime import datetime, timedelta
import calendar
import pytz
import os
import pickle
import json

import pandas as pd
import numpy as np
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_pdf import PdfPages

Evaluation=namedtuple("Evaluation","count_source count_destination source_source source_destination source_destination_late destination_source destination_destination no_idea last_event deltas stack")

class StatsFactory:
    def __init__(self):
        self.registry={}
        self.register("EWSN2019",Stats)
        self.register("EWSN2020",EWSN2020Stats)

    def register(self,name,obj):
        self.registry[name]=obj

    def create(self,name,*args):
        if name in self.registry:
            return self.registry[name](*args)
        return None

class Stats:

    def median(self,lst):
        sortedLst = sorted(lst)
        lstLen = len(lst)
        index = (lstLen - 1) // 2
    
        if (lstLen % 2):
            return sortedLst[index]
        else:
            return (sortedLst[index] + sortedLst[index + 1])/2.0
    
    
    def plotevaluation(self,df_source,df_destination,ev,title):
        if self.no_plot:
            return
        try:
            if not self.energy_plotted:
                edf=pd.DataFrame(self.energy_summary,columns=["mote","total","setup"])
                edf=edf.set_index("mote",drop=True)
                edf["metric"]=edf["total"]-edf["setup"]
                ax=edf.plot.bar(y=["setup","metric"],stacked=True,figsize=self.FIGSIZE,legend=True)
                ax.set_ylabel("Total Energy [J]")
                ax.set_xlabel("Node ID")
                ax.legend(["Energy during setup time","Energy considered for metrics"])
                plt.tight_layout()
                self.pdf.savefig()
                plt.close()
                self.energy_plotted=True
    
    
            df=pd.DataFrame(ev.stack)
    
            bc=0
            boxy = "<h3>Quick view</h3>"
            boxy +='<table class="boxy" id="boxy">'
            for i,r in df.iterrows():
                if(bc==0):
                    boxy+='<tr>'
                elif (bc==self.BOXY_LIM) or (i ==len(df)):
                    boxy+='</tr>'
    
                bc+=1
                if(bc==self.BOXY_LIM):
                    bc=0
                c=r['class']
                color="#FFFFFF"
                txt=" "
                if(c=="correct"):
                    color="#88CC88"
                    txt="C"
                elif(c=="missed"):
                    if r['msg'].rstrip()=="Bus error":
                        color="#FF0000"
                        txt="B"
                    else:
                        color="#CC8888"
                        txt="M"
                elif(c=="late"):
                    color="#CC8888"
                    txt="L"
                elif(c=="superflous"):
                    if r['msg'].rstrip()=="Bus error":
                        color="#FF0000"
                        txt="B"
                    else:
                        color="#CCCC88"
                        txt="S"
                elif(c=="superflous"):
                    color="#CC88CC"
                    txt="A"
                elif(c=="multiple"):
                    color="#88CCCC"
                    txt="U"
                else:
                    color="#FF0000"
                    txt="X"
    
                boxy+='<td style="background-color:' + color + '";>'+txt+'</td>'
            boxy+='</table>'
    
            from weasyprint import HTML
            df_rep=df.loc[:,["time_sent","time_rec","delta","src","dst","msg","class"]]
            df_rep.columns=["Timestamp Sent","Timestamp Recieved","Timedelta[ms]", "Src.", "Dst.", "Message", "Class"]
            df_rep["Timestamp Sent"]=df_rep["Timestamp Sent"].dt.tz_localize(None)
            df_rep["Timestamp Recieved"]=df_rep["Timestamp Recieved"].dt.tz_localize(None)
            pd.set_option('display.max_colwidth', -1)
            code=df_rep.to_html(index=True,formatters={'Timedelta[ms]':lambda x:str(x/np.timedelta64(1,'ms')),"Message":lambda x:x[0:23]+u"\u2026" if len(x)>24 else x}) #ellipsis wont work for some reason...
            css = """<style>
            @media print{@page {size: portrait; ;max-height:100%; max-width:100%}}
            table:not(.boxy) tr th:first-child { background-color: #eeeeee; color: #333; font-weight: bold; }
            table:not(.boxy) thead th { background-color: #eee; color: #000; text-align:center; }
            table:not(.boxy) { border-collapse: collapse; table-layout: fixed; width: 100%; white-space: nowrap; }
            table:not(.boxy) th, td { border: 1px solid #ccc;font-size: 8px; }
            table:not(.boxy) thead th:nth-child(1) { width: 20px; }
            table:not(.boxy) thead th:nth-child(2) { width: 130px; }
            table:not(.boxy) thead th:nth-child(3) { width: 130px; }
            table:not(.boxy) thead th:nth-child(4) { width: 70px; }
            table:not(.boxy) thead th:nth-child(5) { width: 30px; }
            table:not(.boxy) thead th:nth-child(6) { width: 30px; }
            table:not(.boxy) thead th:nth-child(7) { width: 130px; }
            table:not(.boxy) thead th:nth-child(8) { width: 50px; }
            table:not(.boxy) tbody td:nth-child(7) { font-family: monospace, monospace; overflow: hidden; white-space: nowrap; }
            .boxy { table-layout: fixed; border: 1px solid #000000; border-collapse: collapse; background-color:#000000; }
            .boxy td { padding: 0px; border: none; font-family: monospace; font-size: 12px; }
            </style>
            """
            headder = "<h2>"+title+"</h2>"
            listing = "<h3>Messages</h3>"
            code=css+headder+boxy+listing+code
            n=self.pdfbasename+"_"+str(self.ev_cnt)+"_stack.pdf" 
            HTML(file_obj=code).write_pdf(n)
            self.ev_list.append(n)
            self.ev_cnt+=1
        except KeyError as e:
            traceback.print_exc()
            pass
        except Exception as e:
            traceback.print_exc()
            pass
    

    def printeventstack(self,stack):
        s=pd.DataFrame(stack)
        self.print_dbg(s)

    
    def printevaluation(self,ev,mode,total=-1,setup_total=-1):
        self.print_dbg("----------------------------------------------")
        self.print_txt("RELIABILITY")
        self.print_txt("----------------------------------------------")
    
        self.print_csv(ev.count_source)
        self.print_csv(ev.count_destination)
        self.print_csv(ev.source_destination)
        self.print_csv(ev.source_source)
        self.print_csv(ev.destination_destination)
        self.print_csv(ev.destination_source)
        self.print_csv(ev.no_idea)
        self.print_csv(ev.last_event)
    
        if not len(ev.deltas) == 0:
            self.print_csv(str(sum(ev.deltas)))
            self.print_csv(str(max(ev.deltas)))
            self.print_csv(str(min(ev.deltas)))
            self.print_csv(str(sum(ev.deltas)/len(ev.deltas)))
            self.print_csv(str(self.median(ev.deltas)))
        else:
            self.print_csv(None)
            self.print_csv(None)
            self.print_csv(None)
            self.print_csv(None)
            self.print_csv(None)
    
        self.print_csv(total)
        self.print_csv(setup_total)
        if(ev.count_source==0 or ev.count_source==None):
            self.print_csv(False)
        else:
            self.print_csv(mode)
    
        if not len(ev.deltas) == 0:
            self.print_txt("Sent: " +str(ev.count_source))
            self.print_txt("Received: " +str(ev.count_destination))
            self.print_txt("Glitched changes (Destination-destination): " +str(ev.destination_destination))
            self.print_txt("Missed changes (Source-Source): " +str(ev.source_source))
            self.print_txt("Causality BROKEN (Destination-Source): " +str(ev.destination_source))
            self.print_txt("Causality OK (Source-Destination): " +str(ev.source_destination))
            self.print_txt("Causality OK but LATE (Source-Destination): " +str(ev.source_destination_late))
            self.print_txt("Error(No idea): " +str(ev.no_idea))
            self.print_txt("Missing in action (Single): " +str(ev.last_event))
        else:
            self.print_txt("Nothing was received")
    
        self.print_txt("----------------------------------------------")
        self.print_txt("LATENCY")
        self.print_txt("----------------------------------------------")
    
        if not len(ev.deltas) == 0:
            self.print_txt("Sum: " + str(sum(ev.deltas)) + " us")
            self.print_txt("Max: " + str(max(ev.deltas)) + " us")
            self.print_txt("Min: " + str(min(ev.deltas)) + " us")
            self.print_txt("Average: " +str(sum(ev.deltas)/len(ev.deltas)) +" us")
            self.print_txt("Median: " +str(self.median(ev.deltas)) +" us")
            self.print_txt("90 Percentile: " +str(np.percentile(ev.deltas,90)) +" us")
            self.print_txt("95 Percentile: " +str(np.percentile(ev.deltas,95)) +" us")
            self.print_txt("99 Percentile: " +str(np.percentile(ev.deltas,99)) +" us")
        else:
            self.print_txt("Nothing was received")
        
        if self.csv==True:
            self.newline_print=True
            print("")
    
    
    def evaluate(self,df,destinations=1,sources=1,compute_reliability=True):
        first_destination=0
        first_source=0
        last_result=None
        last_time=-1
        count_source=0
        count_destination=0
    
        last_ts=None
        last_event=None
        source_source=0
        source_destination=0
        source_destination_late=0
        destination_destination=0
        destination_source=0
        no_idea=0
        us=0
    
        deltas=[]
    
        event_stack=[]
        
        self.print_dbg(df)
    
        dst_ids=df.loc[df["from"]=="destination"].node.unique()
    
        last_value=None
        for index,value in df.iterrows():
    
            lvl=int(value['evt_lvl'])
            if lvl == 1:
                continue
    
            ts=value['time']
            msg=value['msg']
            us=int(ts.strftime("%s%f"))
            s=value['from']
    
            if(s == "source"):
                if(self.msg):
                    self.print_dbg("Sent: " + str(value['time']) + " is " + '"'+ str(msg).rstrip() +'"')
                else:
                    self.print_dbg("Sent: " + str(value['time']))
                count_source+=1
                last_blink=value['time']
    
                fsr=0
                for nid in dst_ids:
                    rec=df.loc[(df["from"]=="destination") & (df["msg"]==msg) & (df['evt_lvl']==0) & (df['node']==nid)]
                    try:
                        if(len(rec)>0):
                            for i,r in rec.iterrows():
                                if(fsr<destinations):
                                    if(self.msg):
                                        self.print_dbg("Received: (" + str(fsr+1) +"/" +str(destinations) + ") " + str(r['time']) + " is " + '"'+ str(r['msg']).rstrip() +'"')
                                    else:
                                        self.print_dbg("Received: (" + str(fsr+1) +"/" +str(destinations) + ") " + str(r['time']))
                                    dus=int(r["time"].strftime("%s%f"))
                                    if(dus>us): 
                                        event_stack.append({"time_sent":value["time"],"time_rec":r["time"],"delta":r["time"]-value["time"],"msg":str(r['msg']).rstrip(),"class":"correct","src":value['node'],"dst":r['node']})
                                        source_destination+=1
                                        dus=int(r["time"].strftime("%s%f"))
                                        deltas.append(dus-us)
                                        fsr+=1
                                    else:
                                        event_stack.append({"time_sent":value["time"],"time_rec":r["time"],"delta":r["time"]-value["time"],"msg":str(r['msg']).rstrip(),"class":"causality","src":value['node'],"dst":r['node']})
                                        destination_source+=1
                                        fsr+=1
                                else:
                                    if(self.msg):
                                        self.print_dbg("Received duplicate: " + str(r['time']) + " is " + '"'+ str(r['msg']).rstrip() +'"')
                                    else:
                                        self.print_dbg("Received duplicate: " + str(r['time']))
                                    event_stack.append({"time_sent":value["time"],"time_rec":r["time"],"delta":r["time"]-value["time"],"msg":str(r['msg']).rstrip(),"class":"multiple","src":value['node'],"dst":r['node']})
                                    destination_destination+=1
    
                        else:
                            event_stack.append({"time_sent":value["time"],"time_rec":None,"delta":None,"msg":str(value['msg']).rstrip(),"class":"missed","src":value['node'],"dst":nid})
                            self.print_dbg("Missed!")
                            source_source+=1
                    except Exception as e :
                        traceback.print_exc()
                        pass
            elif(s == "destination"):
                count_destination+=1
                sent=df.loc[(df["from"]=="source") & (df["msg"]==msg) & (df["evt_lvl"]==0)]
                if(len(sent)==0):
                    self.print_dbg("Received unknown: " + str(value['time']) + " is " + '"'+ str(value['msg']).rstrip() +'"')
                    event_stack.append({"time_sent":None,"time_rec":value["time"],"delta":None,"msg":str(value['msg']).rstrip(),"class":"superflous","src":None,"dst":value['node']})
                    destination_destination+=1
    
    
        #todo find a better way
        count_source*=destinations
    
        #mercy
        for x in range(0,max(destinations,sources)):
            if(len(event_stack)>1 and event_stack[-1]["class"]=="missed"):
                self.print_dbg("showing mercy for the " + str(x+1) + "time")
                event_stack=event_stack[:-1]
                count_source-=1
                source_source-=1

        if compute_reliability==False:
            count_source=None
            count_destination=None
            source_source=None
            source_destination=None
            source_destination_late=None
            destination_source=None
            destination_destination=None
            no_idea=None
            last_event=None
    
        ev=Evaluation(count_source, count_destination, source_source, source_destination, source_destination_late, destination_source,
                destination_destination,no_idea, last_event, deltas, event_stack)
        return ev
    

    def print_dbg(self, line):
        if self.debug:
            self.print_txt(line)

    
    def print_txt(self, line):
        if self.txt and not self.csv:
            print(line)
    

    def print_csv(self, line):
        if self.csv:
            if self.newline_print==False:
                if self.first_print==False:
                    print(",", end='')
                else:
                    if(self.privacy==True):
                        print("Source node ID,Sink node ID,Event GPIO,Messages sent to source node,Messages received on sink node,Correct messages,Missed messages,Superflous messages,Messages with causality error,_Bad messages,_Missed at the end,_Latency sum [us],_Latency max [us],_Latency min [us],Latency mean [us],Latency median [us],Total Energy [J],Energy during setup time [J],_Evaluate")
                    else:
                        print("Source node ID,Sink node ID,Event GPIO,Messages sent to source node,Messages received on sink node,Correct messages,Missed messages,Superflous messages,Messages with causality error,Bad messages,Missed at the end,Latency sum [us],Latency max [us],Latency min [us],Latency mean [us],Latency median [us],Total Energy [J],Energy during setup time [J],_Evaluate")
                    self.first_print=False
            else:
                self.newline_print=False
            print(str(line), end='')


    def totimestamp(self, dt, epoch=datetime(1970,1,1)):
        td = dt - epoch
        return (td.microseconds + (td.seconds + td.days * 86400) * 10**6)


    def build_config_dict(self,job):
        composition=LayoutComposition.query.filter_by(id=job.layout_composition_id).first()
    
        self.print_dbg("building overrides")
        patterns=LayoutPi.query.with_entities(LayoutPi.composition_id,LayoutPi.group).filter_by(composition_id=composition.id).distinct()
        config=[]
        counter=0
        for p in patterns:
            if p.group=="None":
                continue
    
            pair={}
            tp=0
            if(p.group.startswith("p2p")):
                    tp=1
            if(p.group.startswith("p2mp")):
                    tp=2
            if(p.group.startswith("mp2p")):
                    tp=3
            if(p.group.startswith("mp2mp")):
                    tp=4
    
            pair["label"]="{0}".format(composition.benchmark_suite.name)
    
            #todo: use for sanity checking!
    
            sources=LayoutPi.query.filter_by(composition_id=composition.id,group=p.group,role="source").all()
            s_a=[]
            for s in sources:
                s_a.append(str(s.rpi))
            pair["source"]=s_a
    
            destinations=LayoutPi.query.filter_by(composition_id=composition.id,group=p.group,role="sink").all()
            d_a=[]
            for d in destinations:
                d_a.append(str(d.rpi))
            pair["destination"]=d_a
            pair["pin"]=24
    
            config.append(pair)
    
        self.print_dbg("new config is")
        self.print_dbg(config)
        return config

    
    def __init__(self, HOST, PORT, USER, PASSWORD, DBNAME):
        #TODO bind to do_evaluation instead
        self.energy_plotted=False
        self.energy_summary = []
        self.ev_cnt=0
        self.ev_list=[]
        self.first_print=True
        self.newline_print=False

        self.csv=False
        self.debug=False
        self.txt=False
        self.msg=False

        self.no_energy=False
        self.privacy=True
        self.temp_pdf=False

        self.split_mp2p=False
        self.no_plot=False

        self.report_dir=current_app.config['EVALUATION_FOLDER']
        #self.report_dir="/storage/evaluations"
        self.FIGSIZE= (8.25,4) 
        self.BOXY_LIM=50

        self.HOST=HOST
        self.PORT=PORT
        self.USER=USER
        self.PASSWORD=PASSWORD
        self.DBNAME=DBNAME

        self.client = InfluxDBClient(HOST, PORT, USER, PASSWORD, DBNAME)
        self.client.switch_database(DBNAME)

        #TODO read from topology
        south=range(150,154)
        south=[]
        north_anchor=range(100,116)
        north=range(116,120)
        first_floor=range(200,220)
        ground_floor=range(220,228)
        ids = list(north_anchor) + list(north) + list(south) + list(first_floor) + list(ground_floor)

        self.motes = [str(i) for i in ids]
        self.evaluations=[]


    def do_evaluate(self, job_id):
        first_reset=None

        job=Job.query.filter_by(id=job_id).first()
        if(not job.finished and not job.result):
            self.print_dbg("Not finished yet")
            return

        job_start=calendar.timegm(job.result.begin.utctimetuple())
        job_stop=calendar.timegm(job.result.end.utctimetuple())

        return self.do_evaluate_internal(job_id,job_start,job_stop)

    def do_evaluate_internal(self, job_id,job_start,job_stop):
        first_reset=None
        job=Job.query.filter_by(id=job_id).first()

        if (self.temp_pdf):
            self.pdfbasename='/tmp/last_evaluation'
        else:
            if not os.path.exists(self.report_dir):
                os.makedirs(self.report_dir)
            self.pdfbasename=self.report_dir+"/report_%s"%(job.id)
        self.pdf=PdfPages(self.pdfbasename+"_fig.pdf")
        
        job_start="%ss"%(job_start)
        job_stop="%ss"%(job_stop)
       
        if self.no_energy:
            total=-1
            setup_total=-1
        else:
            self.energy_summary = []
            self.print_txt("==============================================")
            self.print_txt("ENERGY")
            self.print_txt("==============================================")
            
            for mote in self.motes:
                reset_query = 'SELECT * FROM "%s_evt" where time > %s and time < %s and evt_pin=\'20\'' % (mote,job_start,job_stop)
                results = self.client.query(reset_query, database=self.DBNAME)
                r=[]
                last_state=0
                for result in results:
                    for value in reversed(result):
                        if value['evt_pin'] == "20":
                            if not value['evt_lvl'] == last_state:
                                if len(r)<2:
                                    r.append(value['time'])
                            last_state=value['evt_lvl']
            
            
                fmt="%Y-%m-%dT%H:%M:%S.%fZ"
                sfmt="%Y-%m-%dT%H:%M:%SZ"
            
                try:
                    start=datetime.strptime(r[1],fmt)
                except ValueError:
                    start=datetime.strptime(r[1],sfmt)
            
                try:
                    stop=datetime.strptime(r[0],fmt)
                except ValueError:
                    stop=datetime.strptime(r[0],sfmt)
            
            
                startint = self.totimestamp(start)
                stopint = self.totimestamp(stop)

                #startint_energy=startint
                #if stopint-startint > 300000000:
                #    startint_energy=stopint-300000000;
                #    self.print_dbg("taking a shortcut")
            
                self.print_dbg("last meassurement was from " + str(start) + " to " + str(stop) + " and took " + str(stop-start))
            
                #energy_query = 'SELECT MAX(int_energy) FROM "%s" where time > %dms and time < %dms'%(mote,startint_energy/1000,(stopint+100)/1000)
                energy_query = 'SELECT MAX(int_energy) FROM "' + mote + '" where time > '+str(startint)+'u and time < ' +str(stopint+100)+'u'
                results = self.client.query(energy_query, database=self.DBNAME)
            
                max_energy=0
            
                for result in results:
                    for value in result:
                        max_energy=value['max']

                #self.print_dbg("checking setup energy")
                #grace_energy_query = 'SELECT MAX(int_energy) FROM "%s" where time > %dms and time < %dms'%(mote,(startint+55000000)/1000,(startint+60000000)/1000)

                setup_phase_duration=60000000
                if (job.protocol):
                    cfgs=job.protocol.benchmark_suite.configs
                    for cfg in cfgs:
                        if cfg.key=="start":
                            setup_phase_duration = int(cfg.value)*1000000

                try:
                    co=json.loads(job.config_overrides)
                    if "start" in co:
                        setup_phase_duration = int(co["start"])*1000000
                except Exception:
                    pass

                grace_energy_query = 'SELECT MAX(int_energy) FROM "' + mote + '" where time > '+str(startint)+'u and time < ' +str(startint+setup_phase_duration)+'u'
                results = self.client.query(grace_energy_query, database=self.DBNAME)
        
                grace_energy=0
        
                for result in results:
                    for value in result:
                        grace_energy=value['max']
            
                self.print_txt("Mote " + mote + " consumed " + str(max_energy) + " J, setup was " + str(grace_energy) + " J")
                self.energy_summary.append((mote,max_energy,grace_energy))
            
            
            total=0
            setup_total=0
            for e in self.energy_summary:
                total=total+e[1]
                setup_total=setup_total+e[2]
            self.print_txt("Sum: " + str(total) + " J")
            self.print_txt("Setup: " + str(setup_total) + " J")
            
        pairs=self.build_config_dict(job)
                
        self.print_dbg(pairs)
        
        self.print_txt("==============================================")
        self.print_txt("Checking for reset")
        self.print_txt("==============================================")
        
        fmt="%Y-%m-%dT%H:%M:%S.%fZ"
        sfmt="%Y-%m-%dT%H:%M:%SZ"
        
        for mote in self.motes:
            reset_query = 'SELECT * FROM "'+ mote +'_evt" where time > %s and time < %s and evt_pin=\'20\'' % (job_start,job_stop)
            results = self.client.query(reset_query, database=self.DBNAME)
            mote_reset=None
            for result in results:
                for value in reversed(result):
                    if value['evt_pin'] == "20":
                        if value['evt_lvl'] == 0:
                            try:
                                mote_reset=datetime.strptime(value['time'],fmt)
                            except ValueError:
                                mote_reset=datetime.strptime(value['time'],sfmt)
                            break
                if(not mote_reset==None):
                    break
            self.print_dbg("Mote " + str(mote) + " went off at " + str(mote_reset))
        
            if(first_reset==None or first_reset>mote_reset):
                first_reset=mote_reset
        
        self.print_txt("First reset occured at " + str(first_reset))
        
        for pair in pairs:
            df_sources=None
            df_ee_sources=None
            df_destinations=None
            df_ee_destinations=None
            for destination in pair['destination']:
                for source in pair['source']:
        
                    if(len(pair["source"])==1 or self.split_mp2p):
                        self.print_csv(source)
                        self.print_csv(destination)
                        self.print_csv(pair['pin'])
        
                        self.print_txt("==============================================")
                        self.print_txt("Evaluating " +source +" to "+destination)
                        self.print_txt("==============================================")
            
                    reset_query = 'SELECT * FROM "'+ source +'_evt" where time > %s and time < %s and evt_pin=\'20\'' % (job_start,job_stop)
                    results = self.client.query(reset_query, database=self.DBNAME)
                    r=[]
                    last_state=0
                    for result in results:
                        for value in reversed(result):
                            if value['evt_pin'] == "20":
                                if not value['evt_lvl'] == last_state:
                                    if len(r)<2:
                                        r.append(value['time'])
                                last_state=value['evt_lvl']
            
                    self.print_dbg(r)
                    reset_query = 'SELECT * FROM "'+ destination +'_evt" where time > %s and time < %s and evt_pin=\'20\'' % (job_start,job_stop)
                    results = self.client.query(reset_query, database=self.DBNAME)
                    fix=[]
                    last_state=0
                    for result in results:
                        for value in reversed(result):
                            if value['evt_pin'] == "20":
                                if not value['evt_lvl'] == last_state:
                                    if len(fix)<2:
                                        fix.append(value['time'])
                                last_state=value['evt_lvl']
                    self.print_dbg(fix)
            
                    fmt="%Y-%m-%dT%H:%M:%S.%fZ"
                    sfmt="%Y-%m-%dT%H:%M:%SZ"
            
                    try:
                        start=datetime.strptime(r[1],fmt)
                    except ValueError:
                        start=datetime.strptime(r[1],sfmt)
            
                    try:
                        stop=datetime.strptime(r[0],fmt)
                    except ValueError:
                        stop=datetime.strptime(r[0],sfmt)
        
                    self.print_dbg("start " + str(start))
                    self.print_dbg("stop " + str(stop))
            
                    try:
                        start_fix=datetime.strptime(fix[1],fmt)
                    except ValueError:
                        start_fix=datetime.strptime(fix[1],sfmt)
        
                    self.print_dbg("start_fix " + str(start_fix))
            
                    try:
                        stop_fix=datetime.strptime(fix[0],fmt)
                    except ValueError:
                        stop_fix=datetime.strptime(fix[0],sfmt)
        
                    self.print_dbg("stop_fix " + str(stop_fix))
            
                    def totimestamp(dt, epoch=datetime(1970,1,1)):
                        td = dt - epoch
                        return (td.microseconds + (td.seconds + td.days * 86400) * 10**6)
        
                    grace = timedelta(seconds=2)
                    start = start + grace
                    start_fix = start_fix + grace
            
                    stop=stop#first_reset
                    stop=stop-grace
            
                    if(start_fix>start):
                        start=start_fix
            
                    startint = totimestamp(start)
                    stopint = totimestamp(stop)
            
                    self.print_dbg("last meassurement was from " + str(start) + " to " + str(stop) + " and took " + str(stop-start))
            
                    gps_query = 'SELECT * FROM "'+ source +'_evt","'+ destination +'_evt" where time > '+str(startint)+'u and time < ' +str(stopint)+'u and evt_gpio = ' + str(pair['pin'])
                    results = self.client.query(gps_query, database=self.DBNAME)
           
                    last_blink=-1
                    result=results[source+"_evt"]
                    for value in result:
                        try:
                            ts=datetime.strptime(value['time'],fmt)
                        except ValueError:
                            ts=datetime.strptime(value['time'],sfmt)
            
                        us=int(ts.strftime("%s%f"))
                        lvl=int(value['evt_lvl'])
                        if lvl == 1:
                            last_blink=value['time']
            
                    try:
                        if(last_blink==-1):
                            df_source=pd.DataFrame()
                            df_ee_source=pd.DataFrame()
                            df_destination=pd.DataFrame()
                            df_ee_destination=pd.DataFrame()
                            raise Exception()
                        stop_experiment=stop
                        if(len(pair["source"])==1): 
                            try:
                                stop=datetime.strptime(last_blink,fmt)
                            except ValueError:
                                stop=datetime.strptime(last_blink,sfmt)
            
                            self.print_dbg("stop before last event: " + str(stop))
                            stopint = totimestamp(stop)
                        else:
                            try:
                                stop=datetime.strptime(last_blink,fmt)
                            except ValueError:
                                stop=datetime.strptime(last_blink,sfmt)
            
                            self.print_dbg("using mptp stop condition: " + str(stop))
            
                        gps_query = 'SELECT * FROM "'+source+'_evt","'+ destination +'_evt" where time > '+str(startint)+'u and time < ' +str(stopint)+'u and evt_gpio = ' + str(pair['pin'])
                        results = self.client.query(gps_query, database=self.DBNAME)
        
                        eeprom_query = 'SELECT * FROM "'+ source +'_eeprom","'+ destination +'_eeprom" where time > '+str(startint)+'u and time < ' +str(stopint)+'u'
                        eeprom_results = self.client.query(eeprom_query, database=self.DBNAME)
         
           
                        try:
                            df_source= pd.DataFrame(results[source+"_evt"])
                            df_source['time']=pd.to_datetime(df_source['time'])
                            df_source['from']='source'
                            df_source['node']=source
        
                            df_ee_source= pd.DataFrame(eeprom_results[source+"_eeprom"])
                            df_ee_source['time']=pd.to_datetime(df_ee_source['time'])
                            df_ee_source['from']='source'
                            df_ee_source['node']=source
        
                            df_source=df_source.drop( df_source.loc[df_source['evt_lvl']==1].index )
                            df_source=df_source.reset_index(drop=True)
                            df_ee_source=df_ee_source.reset_index(drop=True)
        
                            self.print_dbg("Source Lengths")
                            self.print_dbg("eeprom " + str(len(df_ee_source)))
                            self.print_dbg("evt " + str(len(df_source)))
                            if not len(df_ee_source)==len(df_source):
                                self.print_dbg("!!! Fallback mode enabled on source !!!")
                                for idx,e in df_ee_source.iterrows():
                                    ee_upper=e['time']+timedelta(milliseconds=50)
                                    ee_lower=e['time']-timedelta(milliseconds=50)
                                    ee_s=e['node']
                                    r=df_source.loc[ (df_source['time'] > ee_lower) & (df_source['time'] < ee_upper) & (df_source['node']==ee_s ) & (df_source['evt_lvl']==0) ]
                                    df_source.loc[r.index,'msg']=e['msg']
                                
                            else:
                                for i,e in df_ee_source.iterrows():
                                    df_source.loc[i,'msg']=e['msg']
        
                            if(not isinstance(df_sources,pd.DataFrame)):
                                df_sources=df_source
                            else:
                                df_sources=df_sources.append(df_source)
                                df_sources=df_sources.sort_values(by='time')
        
                        except Exception as e:
                            self.print_dbg("df_source failed")
                            traceback.print_exc()
                            pass
                            
                        df_sd=df_source['time'].diff().shift(-1)
                        df_sdd=(df_sd-df_sd.mean()).dt.total_seconds()
                        self.print_dbg("Event Drift: " + str(df_sdd.mean()))
        
                        try:
                            df_destination=pd.DataFrame(results[destination+"_evt"])
                            df_destination['time']=pd.to_datetime(df_destination['time'])
                            df_destination['from']='destination'
                            df_destination['node']=destination
        
                            df_ee_destination=pd.DataFrame(eeprom_results[destination+"_eeprom"])
                            df_ee_destination['time']=pd.to_datetime(df_ee_destination['time'])
                            df_ee_destination['from']='destination'
                            df_ee_destination['node']=destination
                            
                            df_destination=df_destination.drop( df_destination.loc[df_destination['evt_lvl']==1].index )
                            df_destination=df_destination.reset_index(drop=True)
                            df_ee_destination=df_ee_destination.reset_index(drop=True)
        
                            self.print_dbg("Destination Lengths")
                            self.print_dbg("eeprom " + str(len(df_ee_destination)))
                            self.print_dbg("evt " + str(len(df_destination)))
        
                            if not len(df_ee_destination)==len(df_destination):
                                self.print_dbg("!!! Fallback mode enabled destination!!!")
                                #fallback captive mode
                                for idx,e in df_ee_destination.iterrows():
                                    ee_upper=e['time']+timedelta(milliseconds=150)
                                    ee_lower=e['time']-timedelta(milliseconds=10)
                                    ee_s=e['node']
                                    r=df_destination.loc[ (df_destination['time'] > ee_lower) & (df_destination['time'] < ee_upper) & (df_destination['node']==ee_s ) & (df_destination['evt_lvl']==0) ]
                                    df_destination.loc[r.index,'msg']=e['msg']
        
                            else:
                                for i,e in df_ee_destination.iterrows():
                                    df_destination.loc[i,'msg']=e['msg']
                                
                            if(not isinstance(df_destinations,pd.DataFrame)):
                                df_destinations=df_destination
                            else:
                                df_destinations=df_destinations.append(df_destination)
                                df_destinations=df_destinations.sort_values(by='time')
        
                        except Exception as e:
                            traceback.print_exc()
                            self.print_dbg("df_destination failed")
                            pass
        
                        merge=[df_source, df_destination]
                        df=pd.concat(merge)
                        df=df.sort_values(by='time')
                        
                        df=df.reset_index(drop=True)
        
                        if(len(pair["source"])==1 or self.split_mp2p):
                            if(self.split_mp2p and len(pair["source"])>1):
                                ev=self.evaluate(df,compute_reliability=False)
                            else:
                                ev=self.evaluate(df)
                            if(len(pair["destination"])==1):
                                self.printevaluation(ev,True,total,setup_total)
                                self.evaluations.append({"pair":{"source":source,"destination":destination,"pin":pair["pin"],"label":pair["label"]},"evaluation":ev,"energy_total":total,"energy_setup":setup_total})
                            else:
                                self.printevaluation(ev,False,total,setup_total)
                                self.evaluations.append({"pair":{"source":source,"destination":destination,"pin":pair["pin"],"label":pair["label"]},"evaluation":ev,"energy_total":total,"energy_setup":setup_total})
                            if(self.split_mp2p and len(pair["source"])>1):
                                pass
                            else:
                                self.plotevaluation(df_source,df_destination,ev,"Point to point: " + source + " to " + destination)
        
                    except Exception as e:
                        if(len(pair["source"])==1 or self.split_mp2p):
                            ev=Evaluation(0,0,0,0,0,0,0,0,None,[],[])
                            self.printevaluation(ev,False,total,setup_total)
                            self.evaluations.append({"pair":{"source":source,"destination":destination,"pin":pair["pin"],"label":pair["label"]},"evaluation":ev,"energy_total":total,"energy_setup":setup_total})
                        traceback.print_exc()
                        self.print_dbg(e)
                        pass
        
                if (source==pair['source'][-1] and len(pair['source'])>1 and len(pair['destination'])==1 ):
                    self.print_txt("==============================================")
                    self.print_txt("Evaluating "+str(pair["source"])+" to "+destination)
                    self.print_txt("==============================================")
                    self.print_csv(str(pair['source']).replace(", ","+").replace("'",""))
                    self.print_csv(destination)
                    self.print_csv(pair['pin'])
        
                    mptp=[]
                    last_n={}
                    last_lvl={}
                    for n in pair['source']:
                        last_n[n]=-1  
                        last_lvl[n]=-1
                    counter=0
                    update0=True #TODO check if always correct
                    update1=True #TODO check if always correct
        
                    if (isinstance(df_sources,pd.DataFrame)):
                        for index,value in df_sources.iterrows():
                                mptp.append(value)
        
                    df_mptp=pd.DataFrame(mptp)
                    try:
                        df_mptp.set_index("time")
                    except KeyError:
                        traceback.print_exc()
                        pass
                    try:
                        df_destination.set_index("time")
                    except KeyError:
                        traceback.print_exc()
                        pass
        
                    merge=[df_mptp,df_destination]
                    df=pd.concat(merge)
                    try:
                        df=df.sort_values(by='time')
                    except KeyError:
                        traceback.print_exc()
                        pass
        
                    ev=self.evaluate(df,sources=len(pair["source"]))
                    self.printevaluation(ev,True,total,setup_total)
                    self.evaluations.append({"pair":pair,"evaluation":ev,"energy_total":total,"energy_setup":setup_total})
                    self.plotevaluation(df_mptp,df_destination,ev,"Multipoint to point: "+str(pair["source"])+" to " + str(destination))
                   
                if (destination==pair['destination'][-1] and len(pair['source'])==1 and len(pair['destination'])>1 ):
                    self.print_txt("==============================================")
                    self.print_txt("Evaluating "+source+" to "+str(pair['destination']))
                    self.print_txt("==============================================")
            
                    self.print_csv(source)
                    self.print_csv(str(pair['destination']).replace(", ","*").replace("'",""))
                    self.print_csv(pair['pin'])
            
                    ptmp=[]
                    last_n=-1
                    last_lvl=-1
                    counter=0
                    try:
                        if(df_source.iloc[0]["evt_lvl"]==0):
                            update=True #TODO check if always correct
                        else:
                            update=False
                    except IndexError:
                        #empty df
                        pass
        
                    if (isinstance(df_destinations,pd.DataFrame)):
                        for index,value in df_destinations.iterrows():
                                ptmp.append(value)
        
                    df_ptmp=pd.DataFrame(ptmp)
                    try:
                        df_ptmp.set_index("time")
                    except KeyError:
                        pass
                    try:
                        df_source.set_index("time")
                    except KeyError:
                        pass
        
                    merge=[df_source, df_ptmp]
                    df=pd.concat(merge)
                    try:
                        df=df.sort_values(by='time')
                    except KeyError:
                        #empty df
                        pass
        
                    ev=self.evaluate(df,destinations=len(pair["destination"]))
                    self.printevaluation(ev,True,total,setup_total)
                    self.evaluations.append({"pair":pair,"evaluation":ev,"energy_total":total,"energy_setup":setup_total})
                    self.plotevaluation(df_source,df_ptmp,ev,"Point to multipoint: "+str(source)+" to " + str(pair["destination"]))
        
        self.pdf.close()
        
        from PyPDF2 import PdfFileMerger, PdfFileReader
        merger = PdfFileMerger()
        with open(self.pdfbasename+"_fig.pdf",'rb') as f:
            merger.append(PdfFileReader(f))
        for n in self.ev_list:
            with open(n,'rb') as f:
                merger.append(PdfFileReader(f))
        merger.write(self.pdfbasename+".pdf")

        return self.evaluations
    
class EWSN2020Stats(Stats):
    def __init__(self, HOST, PORT, USER, PASSWORD, DBNAME):
        super().__init__(HOST, PORT, USER, PASSWORD, DBNAME)
        self.delta = timedelta(seconds=3)

    def evaluate(self,df,destinations=1,sources=1,compute_reliability=True):
        self.print_dbg("Running EWSN2020 mode")
        first_destination=0
        first_source=0
        last_result=None
        last_time=-1
        count_source=0
        count_destination=0
    
        last_ts=None
        last_event=None
        source_source=0
        source_destination=0
        source_destination_late=0
        destination_destination=0
        destination_source=0
        no_idea=0
        us=0
    
        deltas=[]
    
        event_stack=[]
        
        self.print_dbg(df)
    
        dst_ids=df.loc[df["from"]=="destination"].node.unique()
    
        last_value=None
        for index,value in df.iterrows():
    
            lvl=int(value['evt_lvl'])
            if lvl == 1:
                continue
    
            ts=value['time']
            msg=value['msg']
            us=int(ts.strftime("%s%f"))
            s=value['from']
    
            if(s == "source"):
                if(self.msg):
                    self.print_dbg("Sent: " + str(value['time']) + " is " + '"'+ str(msg).rstrip() +'"')
                else:
                    self.print_dbg("Sent: " + str(value['time']))
                count_source+=1
                last_blink=value['time']
    
                fsr=0
                acked=[]
                for nid in dst_ids:
                    rec=df.loc[(df["from"]=="destination") & (df["msg"]==msg) & (df['evt_lvl']==0) & (df['node']==nid)]
                    try:
                        if(len(rec)>0):
                            for i,r in rec.iterrows():
                                if(fsr<destinations and not (nid in acked) ):
                                    acked.append(nid)
                                    if(self.msg):
                                        self.print_dbg("Received: (" + str(fsr+1) +"/" +str(destinations) + ") " + str(r['time']) + " is " + '"'+ str(r['msg']).rstrip() +'"')
                                    else:
                                        self.print_dbg("Received: (" + str(fsr+1) +"/" +str(destinations) + ") " + str(r['time']))
                                    dus=int(r["time"].strftime("%s%f"))
                                    if(dus>us): 
                                        #RECEIVED CORRECT
                                        if r["time"]-value["time"]>self.delta:
                                            event_stack.append({"time_sent":value["time"],"time_rec":r["time"],"delta":r["time"]-value["time"],"msg":str(r['msg']).rstrip(),"class":"late","src":value['node'],"dst":r['node']})
                                            source_destination_late+=1
                                            dus=int(r["time"].strftime("%s%f"))
                                            deltas.append(dus-us)
                                            fsr+=1
                                        else:
                                            event_stack.append({"time_sent":value["time"],"time_rec":r["time"],"delta":r["time"]-value["time"],"msg":str(r['msg']).rstrip(),"class":"correct","src":value['node'],"dst":r['node']})
                                            source_destination+=1
                                            dus=int(r["time"].strftime("%s%f"))
                                            deltas.append(dus-us)
                                            fsr+=1
                                    else:
                                        #CAUSALITY!!!
                                        event_stack.append({"time_sent":value["time"],"time_rec":r["time"],"delta":r["time"]-value["time"],"msg":str(r['msg']).rstrip(),"class":"causality","src":value['node'],"dst":r['node']})
                                        destination_source+=1
                                        fsr+=1
                                else:
                                    if(self.msg):
                                        self.print_dbg("Received duplicate: " + str(r['time']) + " is " + '"'+ str(r['msg']).rstrip() +'"')
                                    else:
                                        self.print_dbg("Received duplicate: " + str(r['time']))
                                    event_stack.append({"time_sent":value["time"],"time_rec":r["time"],"delta":r["time"]-value["time"],"msg":str(r['msg']).rstrip(),"class":"multiple","src":value['node'],"dst":r['node']})
                                    destination_destination+=1
    
                        else:
                            event_stack.append({"time_sent":value["time"],"time_rec":None,"delta":None,"msg":str(value['msg']).rstrip(),"class":"missed","src":value['node'],"dst":nid})
                            self.print_dbg("Missed!")
                            source_source+=1
                    except Exception as e :
                        traceback.print_exc()
                        pass
            elif(s == "destination"):
                count_destination+=1
                sent=df.loc[(df["from"]=="source") & (df["msg"]==msg) & (df["evt_lvl"]==0)]
                if(len(sent)==0):
                    self.print_dbg("Received unknown: " + str(value['time']) + " is " + '"'+ str(value['msg']).rstrip() +'"')
                    event_stack.append({"time_sent":None,"time_rec":value["time"],"delta":None,"msg":str(value['msg']).rstrip(),"class":"superflous","src":None,"dst":value['node']})
                    destination_destination+=1
    
    
        #todo find a better way
        count_source*=destinations
    
        #mercy
        for x in range(0,max(destinations,sources)):
            if(len(event_stack)>1 and event_stack[-1]["class"]=="missed"):
                self.print_dbg("showing mercy for the " + str(x+1) + "time")
                event_stack=event_stack[:-1]
                count_source-=1
                source_source-=1
    
        if compute_reliability==False:
            count_source=None
            count_destination=None
            source_source=None
            source_destination=None
            source_destination_late=None
            destination_source=None
            destination_destination=None
            no_idea=None
            last_event=None
    
        ev=Evaluation(count_source, count_destination, source_source, source_destination, source_destination_late, destination_source,
                destination_destination,no_idea, last_event, deltas, event_stack)
        return ev

