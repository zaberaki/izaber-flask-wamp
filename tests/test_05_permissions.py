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
    pass

def test_auth():
    mock_app = MockApp()
    app = FlaskAppWrapper(mock_app)
    ws = MockWebsocket()
    wamp = MockWamp()
    client = WAMPServiceClient(app,ws,wamp,{})
    serializer = load_serializer('json')

    # Currently use anonymous authentication and we want
    # the client to login
    hello_noauth_msg = HELLO(
                        realm='izaber',
                        details={}
                    )
    # Okay now through the codebase. This should simply
    # be a hello as we haven't put down any authmethods
    # without any authmethod it'll just default to anonymous
    client.receive_message(hello_noauth_msg)
    data = serializer.loads(ws.last_sent)
    message = WampMessage.load(data)
    assert message == WAMP_WELCOME

    # Now we'll try and get the client to subscribe
    subscribe_msg = SUBSCRIBE(
                        options={},
                        topic='a.b.c',
                    )
    client.receive_message(subscribe_msg)
    data = serializer.loads(ws.last_sent)
    message = WampMessage.load(data)
    assert message == WAMP_ERROR

    # Okay, then let's add the authorizer
    auth1 = WAMPAuthorizeEverything('a.b*')
    app.authorizers.append(auth1)

    # And try again
    client.receive_message(subscribe_msg)
    data = serializer.loads(ws.last_sent)
    message = WampMessage.load(data)
    assert message == WAMP_SUBSCRIBED

    # Note that this shouldn't let 'a.d' through
    subscribe_msg = SUBSCRIBE(
                        options={},
                        topic='a.d',
                    )
    client.receive_message(subscribe_msg)
    serializer = load_serializer('json')
    data = serializer.loads(ws.last_sent)
    message = WampMessage.load(data)
    assert message == WAMP_ERROR



test_auth()
