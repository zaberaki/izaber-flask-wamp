import os
import importlib
import threading
import random
import sys
import traceback
import flask
import re

import izaber
from izaber import config, app_config, autoloader
from izaber.startup import request_initialize, initializer
from izaber.log import log
from izaber.paths import paths
import izaber.flask

from .common import *
from .uri import *
from .registrations import *
from .authorizers import *
from .app import *
from .wamp import *
from .client import *

from flask_sockets import Sockets, SocketMiddleware


autoloader.add_prefix('izaber.flask.wamp')

CONFIG_BASE = """
default:
    debug: true
    flask:
        wamp:
            realm: izaber
"""


"""

Class Hierarchy:

- flask.Flask
  - IZaberFlask

- flask.Blueprint
  - IZaberFlask

base_app = IZaberFlask() - The subclassed flask.Flask

socktes = Sockets(app)
wamp = IZaberFlaskWAMP(sockets,base_app)

myapp = IZaberFlask(__name__)

"""

app = FlaskAppWrapper(izaber.flask.app)
sockets = Sockets(izaber.flask.app)
wamp = IZaberFlaskLocalWAMP(sockets,app)

izaber_flask = None
class IZaberFlask(flask.Blueprint):
    def __init__(self, import_name, static_folder='static',
                    static_url_path='static', template_folder='templates',
                    url_prefix='', subdomain=None, url_defaults=None,
                    root_path=None):
        global izaber_flask
        name = import_name
        super(IZaberFlask,self).__init__(name, import_name, static_folder,
                    static_url_path, template_folder,
                    url_prefix, subdomain, url_defaults,
                    root_path)
        izaber_flask = self

    def route(self,url,*args,**kwargs):
        if re.search('^/', url):
            url = url[1:]
        return super(IZaberFlask,self).route(url,*args,**kwargs)

    def run(self,*args,**kwargs):
        app.run(*args,**kwargs)

class IZaberFlaskPermissive(IZaberFlask):
    def __init__(self,*args,**kwargs):
        super(IZaberFlaskPermissive,self).__init__(*args,**kwargs)
        app.authorizers.append(WAMPAuthorizeEverything('*'))

@sockets.route('/ws')
def echo_socket(ws):
    client = WAMPServiceClient(app,ws,wamp,flask.request.cookies)
    client.run()

@initializer('flask_wamp')
def load_config(**kwargs):
    request_initialize('config',**kwargs)
    request_initialize('logging',**kwargs)
    request_initialize('flask',**kwargs)
    config.config_amend_(CONFIG_BASE)

    # We add the realm when we finally have access
    # to the config (after load). Due to how the flask
    # 'app' variable works, we would need access to config
    # before config loads causing a bit of an annoyance
    app.finalize_wamp_setup(
            realm=config.flask.wamp.realm,
        )

    # Register any app we've created as well
    if izaber_flask:
        app.register_blueprint(izaber_flask, url_prefix=r'/')
