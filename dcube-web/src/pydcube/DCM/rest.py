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
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import logging

class RESTClient:

    def requests_retry_session(self,retries=5,backoff_factor=0.3, status_forcelist=(500, 502, 504), session=None):
        session = session or requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session


    def __init__(self,url):
        self.INTERNAL_API_ENDPOINT="/internal/api/"
        self.JOB_ENDPOINT="job/"
        self.FIRMWARE_ENDPOINT="firmware/"
        self.LAYOUT_ENDPOINT="layout/"
        self.JAMMING_ENDPOINT="jamming/"
        self.BORDER_ROUTERS_ENDPOINT="border_routers/"
        self.PATCH_ENDPOINT="patch/"
        self.CUSTOM_PATCH_ENDPOINT="patch/custom/"
        self.TEMPLAB_ENDPOINT="templab/"

        self.logger=logging.getLogger("REST Client")
        self.url=url

    def get_job(self,job_id):
        r=self.requests_retry_session().get("%s%s%s%d"%(self.url,self.INTERNAL_API_ENDPOINT,self.JOB_ENDPOINT,job_id))
        self.logger.debug(r)
        r.raise_for_status()
        j=r.json()
        self.logger.debug(j)
        return j

    def get_firmware(self,job_id):
        r=self.requests_retry_session().get("%s%s%s%d"%(self.url,self.INTERNAL_API_ENDPOINT,self.FIRMWARE_ENDPOINT,job_id))
        self.logger.debug(r)
        r.raise_for_status()
        c=r.content
        return c

    def get_jamming(self,job_id,host_id):
        d={}
        for ep in ["options","csv"]:
            r=self.requests_retry_session().get("%s%s%s%d/%s/%s"%(self.url,self.INTERNAL_API_ENDPOINT,self.JAMMING_ENDPOINT,job_id,ep,host_id))
            self.logger.debug(r)
            r.raise_for_status()
            d[ep]=r.content
        return d

    def get_blinker(self,job_id,host_id):
        d={}
        for ep in ["cmd"]:
            r=self.requests_retry_session().get("%s%s%s%d/%s/%s"%(self.url,self.INTERNAL_API_ENDPOINT,self.LAYOUT_ENDPOINT,job_id,ep,host_id))
            self.logger.debug(r)
            r.raise_for_status()
            d[ep]=r.content
        return d

    def get_border_routers(self,job_id):
        r=self.requests_retry_session().get("%s%s%s%d"%(self.url,self.INTERNAL_API_ENDPOINT,self.BORDER_ROUTERS_ENDPOINT,job_id))
        self.logger.debug(r)
        r.raise_for_status()
        j=r.json()
        self.logger.debug(j)
        return j

    def get_patch(self,job_id,host_id):
        d={}
        for ep in ["json","xml"]:
            r=self.requests_retry_session().get("%s%s%s%d/%s/%s"%(self.url,self.INTERNAL_API_ENDPOINT,self.PATCH_ENDPOINT,job_id,ep,host_id))
            self.logger.debug(r)
            r.raise_for_status()
            if ep=="json":
                d[ep]=r.json()
            else:
                d[ep]=r.content
        return d

    def get_custom_patch(self,job_id,host_id):
        d={}
        for ep in ["json","xml"]:
            r=self.requests_retry_session().get("%s%s%s%d/%s/%s"%(self.url,self.INTERNAL_API_ENDPOINT,self.CUSTOM_PATCH_ENDPOINT,job_id,ep,host_id))
            self.logger.debug(r)
            r.raise_for_status()
            if ep=="json":
                d[ep]=r.json()
            else:
                d[ep]=r.content
        return d

    def get_temp_profile(self,job_id):
        d={}
        for ep in ["csv"]:
            r=self.requests_retry_session().get("%s%s%s%d/%s"%(self.url,self.INTERNAL_API_ENDPOINT,self.TEMPLAB_ENDPOINT,job_id,ep))
            self.logger.debug(r)
            r.raise_for_status()
            d[ep]=r.content
        return d


