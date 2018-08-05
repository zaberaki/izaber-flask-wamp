from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler

from izaber import config

import izaber.flask

from .registrations import *

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
                                                 u'pattern_based_subscription': True,
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
                                                 u'pattern_based_registration': True,
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

    def register_local(self,uri,callback,options=None):
        """ Takes a local function and registers it in the callbacks table
        """
        return self.registrations.register_local(uri,callback,options)

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


