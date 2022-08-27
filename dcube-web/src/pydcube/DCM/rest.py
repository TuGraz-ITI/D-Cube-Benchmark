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


