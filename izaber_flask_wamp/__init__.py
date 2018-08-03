import os
import importlib
import threading
import random
import sys
import six
from six.moves import queue
import traceback
import flask
import re

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
        self.subscribed = {}

    def reap_client(self,client):
        """ Removes a client from all registrations and subcriptions
            Usually used when a client disconnects
        """
        for uri, handler in self.registered.items():
            if handler['type'] == 'local':
                continue
            if handler['client'] == client:
                del self.registered[uri]

    def set_uri_base(self,uri_base):
        """ Sets up the base URI that the system will default to
            when locally making registrations/calls/etc.
        """
        if uri_base:
            self.uri_base = uri_base + '.'
        else:
            self.uri_base = ''

    def register_remote(self,uri,client):
        """ Adds a client that's offering to support a particular
            callback on a uri
        """
        if self.uri_base and uri.startswith(self.uri_base):
            uri = uri.replace(self.uri_base,'',1)
        callback_id = secure_rand()
        self.registered[uri] = {
            'type': 'remote',
            'client': client,
            'callback_id': callback_id,
        }
        return callback_id

    def register_local(self,uri,callback):
        """ Registers a local function for handling requests.
            This is the end function of using the @wamp.register
            decorator on a function
        """
        callback_id = secure_rand()
        self.registered[uri] = {
            'type': 'local',
            'callback': callback,
            'callback_id': callback_id,
        }
        return callback_id

    def unregister(self,uri):
        """ Removes a URI as a callback target
        """
        if uri in self.registered:
            del self.registered[uri]

    def invoke(self,request,callback):
        """ Runs the RPC code associated with the URI
        """
        uri = request.procedure
        args = request.args
        kwargs = request.kwargs

        uri_normalized = uri
        if self.uri_base and uri.startswith(self.uri_base):
            uri_normalized = uri.replace(self.uri_base,'',1)
        if uri_normalized not in self.registered:
            raise Exception('uri does not exist')
        handler = self.registered[uri_normalized]

        if handler['type'] == 'local':
            def thread_run():
                result = handler['callback'](*args,**kwargs)
                callback(RESULT(
                    request_id = request.request_id,
                    details = {},
                    args = [ result ],
                    kwargs = {}
                ))
            thread_process = threading.Thread(target=thread_run)
            thread_process.daemon = True
            thread_process.start()
        elif handler['type'] == 'remote':
            def on_yield(result):
                callback(RESULT(
                    request_id = request.request_id,
                    details = {},
                    args = result.args,
                    kwargs = result.kwargs
                ))

            callback_id = handler['callback_id']
            client = handler['client']
            if client.closed():
                self.reap_client(client)
                raise Exception('uri does not exist')
            client.send_and_await_response(
                INVOCATION(
                    request_id=request.request_id,
                    registration_id=callback_id,
                    details={}
                ),
                on_yield
            )
        else:
            raise Exception('Unknown handler type')

    def subscribe_local(self,uri,callback):
        """ Registers a local function to be invoked when the URI
            matches a particular pattern
        """
        subscription_id = secure_rand()
        self.subscribed.setdefault(uri,[])\
            .append({
                'subscription_id': subscription_id,
                'type': 'local',
                'callback': callback,
            })
        return subscription_id

    def subscribe_remote(self,uri,client):
        """ Registers a remote function to be invoked when the URI
            matches a particular pattern
        """
        if self.uri_base and uri.startswith(self.uri_base):
            uri = uri.replace(self.uri_base,'',1)
        subscription_id = secure_rand()
        self.subscribed.setdefault(uri,[])\
            .append({
                'subscription_id': subscription_id,
                'type': 'remote',
                'client': client,
            })
        return subscription_id

    def publish(self,request):
        """ Send the publication to all subscribers
            (If there are any...)
        """
        uri = request.topic

        uri_normalized = uri
        if self.uri_base and uri.startswith(self.uri_base):
            uri_normalized = uri.replace(self.uri_base,'',1)
        if uri_normalized not in self.subscribed:
            return

        publish_id = secure_rand()
        listeners = self.subscribed.get(uri_normalized,[])
        for listener in listeners:
            publish_event = EVENT(
                subscription_id = listener['subscription_id'],
                publish_id = publish_id,
                args = request.args,
                kwargs = request.kwargs,
            )
            if listener['type'] == 'local':
                listener['callback'](publish_event)
            elif listener['type'] == 'remote':
                client = listener['client']
                if client.closed():
                    self.reap_client(client)
                    continue
                client.send_message(publish_event)

        return publish_id

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

    def run(self, host=None, port=None, debug=None, uri_base=None, **options):
        if host is None:
            host = config.flask.host
        if port is None:
            port = config.flask.port
        if debug is None:
            debug = config.debug
        if uri_base is None:
            uri_base = config.flask.wamp.uri_base
        self.uri_base = uri_base

        server = pywsgi.WSGIServer(
                        (host, port),
                        self._app,
                        handler_class=WebSocketHandler
                    )
        server.serve_forever()

    def finalize_wamp_setup(self,realm='izaber',uri_base=''):
        self.realm = realm
        self.registrations.set_uri_base(uri_base)

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

    def register_remote(self,uri,client):
        """ Registers a callback URI
        """
        return self.registrations.register_remote(uri,client)

    def register_local(self,uri,callback):
        """ Takes a local function and registers it in the callbacks table
        """
        return self.registrations.register_local(uri,callback)

    def call(self,request,callback):
        """ Take the request and pass it along to the appropriate
            handler whereever on the bus it might be
        """
        uri = request.procedure
        try:
            self.registrations.invoke(request,callback)
        except Exception as ex:
            traceback.print_exc()
            callback(ERROR(
                        request_code = WAMP_CALL,
                        request_id = request.request_id,
                        details = {},
                        error = 'URI does not exist',
                        args = [],
                    ))


    def unregister(self,uri):
        """ Remove the uri from the call pool
        """
        return self.registrations.unregister(uri)

    def subscribe_remote(self,uri,client):
        """ Registers a callback URI
        """
        return self.registrations.subscribe_remote(uri,client)

    def subscribe_local(self,uri,callback):
        """ Takes a local function and subscribes it in the callbacks table
        """
        return self.registrations.subscribe_local(uri,callback)

    def unsubscribe(self,uri):
        pass

    def publish(self,request):
        self.registrations.publish(request)

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

    def subscribe(self,uri):
        """ A method to use a decorator to subscribe a callback
        """
        def actual_subscribe_decorator(f):
            app.subscribe_local(uri, f)
            return f
        return actual_subscribe_decorator

    def publish(self,topic,options=None,args=None,kwargs=None):
        app.publish(PUBLISH(
            options=options or {},
            topic=topic,
            args=args or [],
            kwargs=kwargs or {}
        ))

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
        self._requests_pending = {}
        self.timeout = 1

    def closed(self):
        """ Returns true if closed
        """
        return self.ws.closed

    def dispatch_to_awaiting(self,result):
        """ Send data ato the appropriate queues
        """
        try:
            try:
                request_id = result.request_id
                if request_id in self._requests_pending:
                    self._requests_pending[request_id]['callback'](result)
                    del self._requests_pending[request_id]
                else:
                    self.send_message(result)
            except AttributeError:
                self.send_message(result)

        except Exception as ex:
            traceback.print_exc()
            raise

    def send_and_await_response(self,request,callback):
        """ Sends out a request then awaits a response
            keyed by the request_id
        """
        if self.state == STATE_DISCONNECTED:
            raise Exception("WAMP is currently disconnected!")

        # Need to setup the callback
        request_id = request.request_id
        self._requests_pending[request_id] = {
                                        'callback': callback,
                                        'timeout': self.timeout, # TODO reap time
                                    }
        self.send_message(request)

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

    def handle_register(self, register):
        """ When a client would like to a register a RPC
            function to a URI
        """
        callback_id = self.app.register_remote(
                            uri=register.procedure,
                            client=self
                        )
        self.dispatch_to_awaiting(REGISTERED(
                    request_id=register.request_id,
                    registration_id=callback_id
                ))

    def handle_call(self, request):
        """ When a client requests that a particular function
            be invoked.
        """
        def on_yield(result):
            self.dispatch_to_awaiting(result)
        self.app.call( request, on_yield )

    def handle_authenticate(self, response):
        """ When a client responds to a challenge request
        """
        result = self.server.auth_method_authenticate(self,response)
        if result:
            self.state = STATE_CONNECTED
        self.dispatch_to_awaiting(result)

    def handle_subscribe(self, request):
        """ Hey! I want to hear about information on this URI
        """
        request_id = request.request_id
        subscription_id = self.app.subscribe_remote(request.topic,self)
        self.send_message(SUBSCRIBED(
            request_id = request_id,
            subscription_id=subscription_id
        ))

    def handle_publish(self, request):
        """ Hey! I have information that someone may want to hear
            about on this particlar URI
        """
        publish_id = self.app.publish(request)
        if request.options.get('acknowledge'):
            self.dispatch_to_awaiting(PUBLISHED(
                                request_id=request.request_id,
                                publication_id=publish_id
                            ))

    def handle_yield(self, result):
        """ A invocation request has returned!
        """
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
                    traceback.print_exc()
                    self.handle_unknown(message)
            except Exception as ex:
                # FIXME: Needs more granular exception handling
                raise

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
    app.finalize_wamp_setup(
            realm=config.flask.wamp.realm,
            uri_base=config.flask.wamp.uri_base,
        )

    # Register any app we've created as well
    if izaber_flask:
        app.register_blueprint(izaber_flask, url_prefix=r'/')
