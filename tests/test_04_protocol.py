#!/usr/bin/python3

from swampyer.messages import *

from izaber_flask_wamp.uri import *
from izaber_flask_wamp.registrations import *
from izaber_flask_wamp.app import *
from izaber_flask_wamp.client import *
from izaber_flask_wamp.authenticators import *

class MockApp(object):
    realm = 'izaber'

class MockWebsocket(object):
    def __init__(self):
        self.last_sent = None

    def send(self,data):
        self.last_sent = data

class MockWamp(object):
    def do_wamp_authenticated(self,*args):
        pass


def test_connect():

    mock_app = MockApp()
    app = FlaskAppWrapper(mock_app)
    ws = MockWebsocket()
    wamp = MockWamp()
    client = WAMPServiceClient(app,ws,wamp,{})

    # Setup the ticket authenticators
    ticket_auth = SimpleTicketAuthenticator([
                        {
                            'login': 'test',
                            'password': 'password',
                            'role': 'backend'
                        }
                    ])
    hello_noauth_msg = HELLO(
                        realm='izaber',
                        details={}
                    )
    hello_msg = HELLO(
                        realm='izaber',
                        details={
                            'authid': 'test',
                            'authmethods': ['ticket']
                        }
                    )
    authenticate_msg = AUTHENTICATE(
                            signature = 'password'
                        )
    bad_authenticate_msg = AUTHENTICATE(
                            signature = 'rumplestiltskin'
                        )

    # Okay now through the codebase. This should simply
    # be a hello as we haven't established any authenticators yet
    client.receive_message(hello_noauth_msg)
    message = WampMessage.loads(ws.last_sent)
    assert message == WAMP_WELCOME

    # Now, after the authenticator has been added, we should get a
    # challenge
    ws.last_sent = None
    app.authenticators.append(ticket_auth)
    client.receive_message(hello_msg)
    message = WampMessage.loads(ws.last_sent)
    assert message == WAMP_CHALLENGE

    # Cool, let's submit our response and get our welcome message
    ws.last_sent = None
    client.receive_message(authenticate_msg)
    message = WampMessage.loads(ws.last_sent)
    assert message == WAMP_WELCOME

    # How about a bad login
    ws.last_sent = None
    client.receive_message(bad_authenticate_msg)
    message = WampMessage.loads(ws.last_sent)
    assert message == WAMP_ERROR


