import traceback

from swampyer.messages import *

from izaber.log import log

from .common import *

class WAMPServiceClient(object):

    def __init__(self,app,ws,wamp,cookies):
        self.ws = ws
        self.state = STATE_CONNECTING
        self.app = app
        self.session_id = secure_rand()
        self._requests_pending = {}
        self.timeout = 1
        self.wamp = wamp
        self.cookies = cookies
        self.auth = DictObject()
        self.serializer = load_serializer('json')

    def closed(self):
        """ Returns true if closed
        """
        return self.ws.closed

    def dispatch_to_awaiting(self,result):
        """ Send data to the appropriate queues. We use the request_id to key
            back to a dict of waiting queue objects.
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
        if hello.details.get('authmethods'):
            self.state = STATE_AUTHENTICATING

            # Is there some way we can immediately authenticate?
            authenticated = self.app.authenticators.authenticate_on_hello(self,hello)

            # Awesome, we can authenticate. Let's finish the authentication
            # off. FIXME: Duplicated code with handle_authorization
            if authenticated:
                self.state = STATE_CONNECTED
                self.auth = authenticated

                details = self.app.auth_details( self.app, authenticated.authid, authenticated.role)
                message = WELCOME(
                            session_id=self.session_id,
                            details=details
                        )

                self.wamp.do_wamp_authenticated(self)
                self.app.authenticators.on_successful_authenticate(self,authenticated)
                return self.dispatch_to_awaiting(message)

            # Okay, so we didn't manage to authenticate, let's hand over
            # the request to the challenge response system.
            self.auth_hello = hello

            try:
                challenge = self.app.authenticators.create_challenge(self,hello)
                if not challenge :
                    raise Exception('No Authenticator Found')
                self.auth_challenge = challenge
            except Exception as ex:
                print("OOPS:", ex)
                return ERROR(
                        request_code = WAMP_HELLO,
                        request_id = None,
                        details = {},
                        error = 'No authentication scheme found',
                        args = [],
                    )
            return self.dispatch_to_awaiting(challenge)

        self.state = STATE_CONNECTED
        details = self.app.auth_details(self,'anonymous','anonymous')
        self.auth = DictObject()

        self.dispatch_to_awaiting(WELCOME(
                    session_id=self.session_id,
                    details=details
                ))

    def handle_authenticate(self, response):
        """ When a client responds to a challenge request
        """
        try:
            authenticated = self.app.authenticators.authenticate_challenge_response(
                        self,
                        self.auth_hello,
                        self.auth_challenge,
                        response
                    )
            if not authenticated:
                raise Exception('Invalid authentication')

            self.state = STATE_CONNECTED
            self.auth = authenticated
            details = self.app.auth_details( self.app, authenticated.authid, authenticated.role)
            message = WELCOME(
                        session_id=self.session_id,
                        details=details
                    )

            self.wamp.do_wamp_authenticated(self)
            self.app.authenticators.on_successful_authenticate(self,authenticated)
            return self.dispatch_to_awaiting(message)

        except Exception as ex:
            self.dispatch_to_awaiting(ERROR(
                    request_code = WAMP_AUTHENTICATE,
                    request_id = None,
                    details = {},
                    error = 'Authentication failed',
                    args = [],
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
        self.app.call_remote( self, request, on_yield )

    def handle_subscribe(self, request):
        """ Hey! I want to hear about information on this URI
        """
        request_id = request.request_id
        try:
            subscription_id = self.app.subscribe_remote(request.topic,self)
            self.send_message(SUBSCRIBED(
                request_id = request_id,
                subscription_id=subscription_id
            ))
        except Exception as ex:
            traceback.print_exc()
            self.send_message(ERROR(
                        request_code = WAMP_SUBSCRIBE,
                        request_id = request_id,
                        details = {},
                        error = 'Not Subscribed',
                        args = [],
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
        message = self.serializer.dumps(message.package())
        log.debug("SND>: {}".format(message))
        self.ws.send(message)

    def receive_message(self,message):
        log.debug("<RCV: {}".format(message.dump()))
        try:
            code_name = message.code_name.lower()
            handler_name = "handle_"+code_name
            handler_function = getattr(self,handler_name)
            handler_function(message)
        except AttributeError as ex:
            traceback.print_exc()
            self.handle_unknown(message)

    def run(self):
        self.wamp.do_wamp_connect(self)
        while not self.ws.closed:
            data = self.ws.receive()
            if not data:
                continue
            try:
                log.debug("<RCV: {}".format(data))
                message = WampMessage.load(self.serializer.loads(data))
                self.receive_message(message)
            except Exception as ex:
                # FIXME: Needs more granular exception handling
                self.wamp.do_wamp_disconnect(self)
                raise
        self.wamp.do_wamp_disconnect(self)


