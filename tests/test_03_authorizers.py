#!/usr/bin/python3

from swampyer.messages import *

from izaber_flask_wamp.authorizers import *

def test_authorizer():

    # Anyone allowed to do whatever
    auth1 = WAMPAuthorizeEverything('*')

    session = {
        'realm': 'izaber',
        'authprovider': None,
        'authrole': 'test',
        'authmethod': 'anonymous',
        'session': 1234
    }
    result = auth1.authorize(session,'a.b.c','publish')
    assert result['allow']

    # By default this allows nothing!
    authlist = WAMPAuthorizers()
    result = authlist.authorize(session,'a.b.c','call')
    assert result['allow'] == False

    # But we'll allow it to authorize anything in a.b*
    auth2 = WAMPAuthorizeEverything('a.b*')
    authlist.append(auth2)
    result = authlist.authorize(session,'a.b.c','call')
    assert result['allow']

    # This shouldn't be allowed
    result = authlist.authorize(session,'a.c','call')
    assert result['allow'] == False


test_authorizer()
