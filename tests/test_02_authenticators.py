#!/usr/bin/python3

from swampyer.messages import *

from izaber_flask_wamp.authenticators import *

def test_connect():

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
    challenge_msg = ticket_auth.create_challenge(hello_msg)
    assert challenge_msg  == WAMP_CHALLENGE

    # And ensure we can authenciate via the base object
    authenticate_msg = AUTHENTICATE(
                            signature = 'password'
                        )
    role = ticket_auth.authenticate_challenge_response(
                                    hello_msg,
                                    challenge_msg,
                                    authenticate_msg
                                )
    assert role == 'backend'

    # How about a bad password?
    bad_authenticate_msg = AUTHENTICATE(
                            signature = 'rumplestiltskin'
                        )
    role = ticket_auth.authenticate_challenge_response(
                                    hello_msg,
                                    challenge_msg,
                                    bad_authenticate_msg
                                )
    assert role == None


