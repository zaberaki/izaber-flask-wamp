from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler

from izaber import config

import izaber.flask

from .registrations import *
from .authenticators import *
from .authorizers import *

class FlaskAppWrapper(object):
    def __init__(self,app,users=None):
        self.__dict__.update(dict(
            _app = app,
        ))

        # Used by WS to ensure we allow the wamp protocol to connect
        app.allowed_protocol = 'wamp.2.json'

        # Used to verify users. Used by Challenge
        self.authenticators = WAMPAuthenticators()

        # The current list of clients connected, should be a list
        # of WAMPServiceClient instances
        self.clients = []

        # To track subscriptions and registrations
        self.registrations = WAMPRegistrations()

        # Used to verify who can access what resources
        self.authorizers = WAMPAuthorizers()

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

    def finalize_wamp_setup(self,realm='izaber'):
        self.realm = realm

    def auth_details(self,ws,authid,authrole='anonymous'):

        return {
            u'authid': authid,
            u'authmethod': u'ticket',
            u'authprovider': u'dynamic',
            u'authrole': authrole,
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

    def authorize(self,client,uri,action,options=None):
        """ Checks to see if the client is authorized to access
            this particular URI
        """
        session = {
            'realm': client.auth.realm,
            'authprovider': 'dynamic',
            'authrole': client.auth.authrole,
            'authmethod': client.auth.authmethod,
            'session': client.session_id,
        }
        return self.authorizers.authorize(session,uri,action,options)

    def generate_request_id(self):
        """ We cheat, we just use the millisecond timestamp for the request
        """
        return int(round(time.time() * 1000))

    def register_remote(self,uri,client):
        """ Registers a callback URI
        """
        perms = self.authorizers.authorize(client,uri,'register')
        if not perms['allow']:
            raise Exception("Not Allowed")
        return self.registrations.register_remote(uri,client)

    def register_local(self,uri,callback,options=None):
        """ Takes a local function and registers it in the callbacks table
            Note that we don't test local for registration. We just allow it
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

    def subscribe_remote(self,uri,client,options=None):
        """ Registers a callback URI
        """
        session = {
            'realm': client.auth.realm,
            'authprovider': 'dynamic',
            'authrole': client.auth.authrole,
            'authmethod': client.auth.authmethod,
            'session': client.session_id,
        }
        perms = self.authorizers.authorize(session,uri,'subscribe')
        if not perms['allow']:
            raise Exception("Not Allowed")
        return self.registrations.subscribe_remote(uri,client,options)

    def subscribe_local(self,uri,callback,options=None):
        """ Takes a local function and subscribes it in the callbacks table
        """
        return self.registrations.subscribe_local(uri,callback,options)

    def unsubscribe(self,uri):
        pass

    def publish(self,request):
        self.registrations.publish(request)

    def __getattr__(self,k):
        return getattr(self._app,k)

    def __setattr__(self,k,v):
        return setattr(self._app,k,v)


