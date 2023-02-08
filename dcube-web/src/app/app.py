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
from flask import Flask,redirect
from flask_bootstrap import Bootstrap4
from flask_security import Security, current_user, uia_username_mapper 
from flask_migrate import Migrate
from flask_mailman import Mail

from frontend.frontend import frontend
from frontend.rest_api import rest_api
from frontend.internal_api import internal_api
from frontend.nordic import nordic
from frontend.sky import sky
from frontend.linux import linux
from frontend.admin import admin
from frontend.leaderboard import leaderboard

from models.config import Config
from models.benchmark_suite import BenchmarkSuite

from backend.database import db
from backend.security import user_datastore, ExtendedLoginForm

from frontend.helpers import check_scheduler_time, check_jamming_time

from dotenv import load_dotenv
import os

import logging
import sys
level=logging.DEBUG
FORMAT = "[%(name)16s - %(funcName)12s() ] %(message)s"
logging.basicConfig(stream=sys.stdout,level=level,format=FORMAT)

def create_app(configfile=None):
    app = Flask("dcube")

    # Select a configuration from object
    #app.config.from_object('backend.configmodule.DockerConfig')
    load_dotenv()
    config = os.getenv('DCUBE_CONFIG')
    if config==None:
        backendconfig="backend.configmodule.DockerConfig"
    else:
        backendconfig="backend.configmodule.%s"%config
    app.config.from_object(backendconfig)

    # Register app with database backend
    db.init_app(app)

    # Install our Bootstrap extension
    Bootstrap4(app)

    # Our application uses blueprints as well; these go well with the
    # application factory. We already imported the blueprint, now we just need
    # to register it:
    app.register_blueprint(frontend)
    app.register_blueprint(admin, url_prefix='/admin')
    app.register_blueprint(nordic, url_prefix='/nordic')
    app.register_blueprint(sky, url_prefix='/sky')
    app.register_blueprint(linux, url_prefix='/linux')
    app.register_blueprint(rest_api, url_prefix='/api')
    app.register_blueprint(internal_api, url_prefix='/internal/api')
    app.register_blueprint(leaderboard, url_prefix='/leaderboard')

    # Allow registration with email, but login only with username
    app.config["SECURITY_USER_IDENTITY_ATTRIBUTES"] = [
        {"username": {"mapper": uia_username_mapper}}
    ]

    # Configure mail context
    mail = Mail(app)

    # We initialize the security context
    Security(app, user_datastore, login_form=ExtendedLoginForm)

    migrate=Migrate(app,db)

    # Create a user to test with
    @app.before_first_request
    def create_content():
        db.create_all()

    # Used to differentiate between the details pages of indivudual modules
    def jobdetails(job):
        if job.protocol and "Nordic" in job.protocol.benchmark_suite.node.name:
            return "nordic.show_details"
        if job.protocol and "Sky" in job.protocol.benchmark_suite.node.name:
            return "sky.show_details"
        if job.protocol and "Linux" in job.protocol.benchmark_suite.node.name:
            return "linux.show_details"
        return None

    app.jinja_env.globals.update(jobdetails=jobdetails)

    # Used to differentiate between the details pages of indivudual modules
    def protocolqueue(protocol):
        if "Nordic" in protocol.benchmark_suite.node.name:
            return "nordic.show_queue"
        if "Sky" in protocol.benchmark_suite.node.name:
            return "sky.show_queue"
        if "Linux" in protocol.benchmark_suite.node.name:
            return "linux.show_queue"
        return None

    app.jinja_env.globals.update(protocolqueue=protocolqueue)


    import math
    app.jinja_env.filters['isnan'] = math.isnan


    # Convert time to the given format
    import pytz

    def datetimefilter(value, format="%d.%m.%y %H:%M"):

        tz = pytz.timezone('Europe/Vienna')
        utc = pytz.timezone('UTC')
        value = utc.localize(value, is_dst=None).astimezone(pytz.utc)
        local_dt = value.astimezone(tz)
        return local_dt.strftime(format)

    app.jinja_env.filters['datetimefilter'] = datetimefilter

    # Used to get grafana useable timestamps
    import calendar

    def timestampfilter(value):
        timestamp = calendar.timegm(value.utctimetuple())
        return timestamp*1000

    app.jinja_env.filters['timestampfilter'] = timestampfilter

    # Draw a checkbox for a boolean value
    def checkboxify(value):
        if value:
            return '<span class="far fa-check-square" \
                    aria-hidden="true"></span>'
        else:
            return '<span class="far fa-square \
                    aria-hidden="true"></span>'

    app.jinja_env.filters['checkboxify'] = checkboxify

    # TODO: use helper version
    def check_maintenance_mode():
        if current_user.is_authenticated and current_user.has_role("admins"):
            return Config.get_bool("maintenance", True)
        return False

    app.add_template_global(check_maintenance_mode,
                            name='check_maintenance_mode')


    def check_scheduler_running():
        return check_scheduler_time()
    
    app.add_template_global(check_scheduler_running,
                            name='check_scheduler_running')


    def check_jamming_running():
        return  check_jamming_time()

    app.add_template_global(check_jamming_running,
                            name='check_jamming_running')


    def get_config(key,default="?"):
        return  Config.get_string(key)

    app.add_template_global(get_config,
                            name='get_config')

    def get_config_bool(key,default=False):
        return  Config.get_bool(key)

    app.add_template_global(get_config_bool,
                            name='get_config_bool')


    def get_benchmark_suites():
        return BenchmarkSuite.query.all()

    app.add_template_global(get_benchmark_suites,
                            name='get_benchmark_suites')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=False, host="0.0.0.0", port=8888)
