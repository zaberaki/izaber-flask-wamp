#!/usr/bin/python3

from swampyer.messages import *

from izaber_flask_wamp.authenticators import *

class MockClient(object):
    pass

def test_connect():

    mock_client = MockClient()

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

    # Ensure we get a challenge from the authen object
    challenge_msg = ticket_auth.create_challenge(mock_client,hello_msg)
    assert challenge_msg  == WAMP_CHALLENGE

    # And ensure we can authenciate via the base object
    authenticate_msg = AUTHENTICATE(
                            signature = 'password'
                        )
    authorized = ticket_auth.authenticate_challenge_response(
                                    mock_client,
                                    hello_msg,
                                    challenge_msg,
                                    authenticate_msg
                                )
    assert authorized.role == 'backend'

    # How about a bad password?
    bad_authenticate_msg = AUTHENTICATE(
                            signature = 'rumplestiltskin'
                        )
    authorized = ticket_auth.authenticate_challenge_response(
                                    mock_client,
                                    hello_msg,
                                    challenge_msg,
                                    bad_authenticate_msg
                                )
    assert authorized == None


