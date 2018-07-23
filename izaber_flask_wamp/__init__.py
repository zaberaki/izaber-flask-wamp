import os
import importlib
import threading
import random
import sys

import izaber
from izaber import config, app_config, autoloader
from izaber.startup import request_initialize, initializer
from izaber.log import log
from izaber.paths import paths
import izaber.flask

from flask_sockets import Sockets, SocketMiddleware
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler

from swampyer.messages import *

rng = random.SystemRandom()
def secure_rand():
    return rng.randint(0,sys.maxsize)

autoloader.add_prefix('izaber.flask.wamp')

CONFIG_BASE = """
default:
    debug: true
    flask:
        wamp:
            realm: izaber
            uri_base: com.izaber.wamp
"""

sockets = Sockets(izaber.flask.app)

class WAMPRegistrations(object):
    def __init__(self):
        self.registered = {}

    def add_remote(self,uri):
        pass

    def add_local(self,uri,callback):
        self.registered[uri] = {
            'type': 'local',
            'callback': callback
        }

    def unregister(self,uri):
        pass

    def invoke(self,uri,args,kwargs):
        if uri not in self.registered:
            raise Exception('uri does not exist')
        handler = self.registered[uri]
        if handler['type'] == 'local':
            return handler['callback'](*args,**kwargs)
        else:
            pass # what to do here?

class FlaskAppWrapper(object):
    def __init__(self,app,users=None):
        self.__dict__.update(dict(
            _app = app,
            users = users or [],
        ))
        app.allowed_protocol = 'wamp.2.json'

        self.clients = []
        self.registrations = WAMPRegistrations()
        self.subscriptions = {}

    def client_add(self,client):
        self.clients.append(client)

    def run(self, host=None, port=None, debug=None, **options):
        if host is None:
            host = config.flask.host
        if port is None:
            port = config.flask.port
        if debug is None:
            debug = config.debug

        server = pywsgi.WSGIServer(
                        (host, port),
                        self._app,
                        handler_class=WebSocketHandler
                    )
        server.serve_forever()

    def auth_details(self,ws,authid,authrole):
        return {
            u'authid': authid,
            u'authmethod': u'ticket',
            u'authprovider': u'dynamic',
            u'authrole': u'anonymous',
            u'realm': self.realm,
            u'roles': {u'broker': {u'features': {
                                                 u'event_retention': False,
                                                 u'pattern_based_subscription': False,
                                                 u'payload_encryption_cryptobox': False,
                                                 u'payload_transparency': False,
                                                 u'publisher_exclusion': False,
                                                 u'publisher_identification': False,
                                                 u'session_meta_api': False,
                                                 u'subscriber_blackwhite_listing': False,
                                                 u'subscription_meta_api': False,
                                                 u'subscription_revocation': False
                                                 }},
                       u'dealer': {u'features': {
                                                 u'call_canceling': False,
                                                 u'caller_identification': False,
                                                 u'pattern_based_registration': False,
                                                 u'payload_encryption_cryptobox': False,
                                                 u'payload_transparency': False,
                                                 u'progressive_call_results': False,
                                                 u'registration_meta_api': False,
                                                 u'registration_revocation': False,
                                                 u'session_meta_api': False,
                                                 u'shared_registration': False,
                                                 u'testament_meta_api': False
                                                 }}},
            u'x_cb_node_id': None
        }

    def generate_request_id(self):
        """ We cheat, we just use the millisecond timestamp for the request
        """
        return int(round(time.time() * 1000))

    def auth_method_prepare(self,client,message):
        """ Returns the auth method the client should use for
            authentication
        """
        if not self.users:
            return

        if 'ticket' not in message.details.get('authmethods',[]):
            return ERROR(
                        request_code = WAMP_HELLO,
                        request_id = None,
                        details = {},
                        error = 'Unable to authenticate',
                        args = [],
                    )

        client.auth_method = 'ticket'
        client.authid = message.details['authid']
        return CHALLENGE(
                        auth_method='ticket',
                        extra={}
                    )

    def auth_method_authenticate(self,client,response):
        """ Does the actual work of authenticating the user
        """
        if client.auth_method != 'ticket':
            return ERROR(
                request_code = WAMP_AUTHENTICATE,
                request_id = None,
                details = {},
                error = 'Non ticket based authentication not supported',
                args = [],
            )

        authid = client.authid
        generic_auth_error = ERROR(
                                request_code = WAMP_AUTHENTICATE,
                                request_id = None,
                                details = {},
                                error = 'Unable to authenticate',
                                args = [],
                            )
        if authid not in self.users:
            return generic_auth_error

        user_data = self.users[authid]
        password = user_data.get('password',None)
        if not password:
            return generic_auth_error

        if response.signature != password:
            return generic_auth_error

        # Okay the person is why they say they are.
        client.user_data = user_data
        details = self.auth_details(
                        self.client,
                        authid,
                        authid
                    )

        return WELCOME(
            session_id=client.session_id,
            details=details
        )

    def register(self,uri):
        """ Registers a callback URI
        """
        print "REGISTRED:", uri
        pass

    def register_local(self,uri,callback):
        """ Takes a local function and registers it in the callbacks table
        """
        self.registrations.add_local(uri,callback)

    def call(self,request):
        """ Take the request and pass it along to the appropriate
            handler whereever on the bus it might be
        """
        uri = request.procedure
        try:
            result = self.registrations.invoke(uri,request.args,request.kwargs)
        except Exception as ex:
            return ERROR(
                        request_code = WAMP_CALL,
                        request_id = request.request_id,
                        details = {},
                        error = 'URI does not exist',
                        args = [],
                    )

        return RESULT(
            request_id = request.request_id,
            details = {},
            args = [ result ],
            kwargs = {}
        )
        print request.dump()
        print "HERE I AM!"
        pass

    def unregister(self,uri):
        pass

    def publish(self):
        pass

    def subscribe(self,uri):
        pass

    def unsubscribe(self,uri):
        pass

    def __getattr__(self,k):
        return getattr(self._app,k)

    def __setattr__(self,k,v):
        return setattr(self._app,k,v)

app = FlaskAppWrapper(izaber.flask.app)

class IZaberFlaskWAMP(object):
    """ Allows the creation and sending of calls and functions
    """
    def __init__(self,sockets,app):
        self.sockets = sockets
        self.app = app

    def register(self,uri):
        """ A method to use a decorator to register a callback
        """
        def actual_register_decorator(f):
            app.register_local(uri, f)
            return f
        return actual_register_decorator

wamp = IZaberFlaskWAMP(sockets,app)

STATE_DISCONNECTED = 0
STATE_CONNECTING = 1
STATE_WEBSOCKET_CONNECTED = 3
STATE_AUTHENTICATING = 4
STATE_CONNECTED = 2

class WAMPServiceClient(object):
    def __init__(self,app,ws):
        self.ws = ws
        self.state = STATE_CONNECTING
        self.app = app
        self.session_id = secure_rand()

    def dispatch_to_awaiting(self,result):
        """ Send data ato the appropriate queues
        """
        try:
            self.send_message(result)
        except Exception as ex:
            print ex
            raise

#    def send_and_await_response(self,request):
#        """ Used by most things. Sends out a request then awaits a response
#            keyed by the request_id
#        """
#        if self._state == STATE_DISCONNECTED:
#            raise Exception("WAMP is currently disconnected!")
#        wait_queue = queue.Queue()
#        request_id = request.request_id
#        self._requests_pending[request_id] = wait_queue;
#        self.send_message(request)
#        try:
#            return wait_queue.get(block=True,timeout=self.timeout)
#        except Exception as ex:
#            raise Exception("Did not receive a response!")
#
#    def dispatch_to_awaiting(self,result):
#        """ Send dat ato the appropriate queues
#        """
#
#        # If we are awaiting to login, then we might also get
#        # an abort message. Handle that here....
#        if self._state == STATE_AUTHENTICATING:
#            # If the authentication message is something unexpected,
#            # we'll just ignore it for now
#            if result == WAMP_ABORT \
#               or result == WAMP_WELCOME \
#               or result == WAMP_GOODBYE:
#                self._welcome_queue.put(result)
#            return
#
#        try:
#            request_id = result.request_id
#            if request_id in self._requests_pending:
#                self._requests_pending[request_id].put(result)
#                del self._requests_pending[request_id]
#        except:
#            raise Exception("Response does not have a request id. Do not know who to send data to. Data: {} ".format(result.dump()))
#

    def handle_hello(self, hello):
        """ A new customer!
        """
        self.app.clients.append(self)

        # We only trigger authentications if the app has users
        # setup.
        if self.app.users and hello.details['authmethods']:
            self.state = STATE_AUTHENTICATING
            challenge = self.app.auth_method_prepare(self,hello)
            if not challenge:
                return ERROR(
                        request_code = WAMP_HELLO,
                        request_id = None,
                        details = {},
                        error = 'None of the authmethods are support. We only support ticket ',
                        args = [],
                    )
            return self.dispatch_to_awaiting(challenge)

        self.state = STATE_CONNECTED
        details = self.app.auth_details(self,'anonymous','anonymous')

        self.dispatch_to_awaiting(WELCOME(
                    session_id=self.session_id,
                    details=details
                ))

    def handle_call(self, request):
        """ When a client requests that a particular function
            be invoked.
        """
        result = self.app.call(request)
        self.dispatch_to_awaiting(result)

    def handle_authenticate(self, response):
        """ When a client responds to a challenge request
        """
        result = self.server.auth_method_authenticate(self,response)
        if result:
            self.state = STATE_CONNECTED
        self.dispatch_to_awaiting(result)

    def handle_error(self, error):
        """ OOops! An error occurred
        """
        self.dispatch_to_awaiting(error)

    def handle_unknown(self, message):
        """ We don't know what to do with this. So we'll send it
            into the queue just in case someone wants to do something
            with it but we'll just blackhole it.
        """
        print "Unknown message:", message.dump()
        self.dispatch_to_awaiting(message)

    def send_message(self,message):
        """ Send awamp message to the server. We don't wait
            for a response here. Just fire out a message
        """
        if self.state == STATE_DISCONNECTED:
            raise Exception("WAMP is currently disconnected!")
        message = message.as_str()
        log.debug("SND>: {}".format(message))
        self.ws.send(message)

    def run(self):
        while not self.ws.closed:
            data = self.ws.receive()
            print "GOT:", self.ws, data
            if not data:
                continue
            try:
                log.debug("<RCV: {}".format(data))
                message = WampMessage.loads(data)
                log.debug("<RCV: {}".format(message.dump()))
                try:
                    code_name = message.code_name.lower()
                    handler_name = "handle_"+code_name
                    handler_function = getattr(self,handler_name)
                    handler_function(message)
                except AttributeError as ex:
                    print "Error trying to handle request:", ex
                    import traceback
                    traceback.print_exc()
                    self.handle_unknown(message)
            except Exception as ex:
                # FIXME: Needs more granular exception handling
                raise

            # self.ws.send(message)


@sockets.route('/ws')
def echo_socket(ws):
    client = WAMPServiceClient(app,ws)
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
    app.realm = config.flask.wamp.realm or 'izaber'

