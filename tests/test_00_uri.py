#!/usr/bin/python3

from izaber_flask_wamp.uri import *

def test_matching():

    match_list = WAMPURIList()

    # Test context exact matches
    assert WAMPURI('a').match('a')
    assert WAMPURI('a').match('b') == False
    assert WAMPURI('a').match('a.b') == False
    assert WAMPURI('a.b').match('a') == False

    # Test context prefix matches
    uri = WAMPURI('a*')
    match_list.append(uri)
    assert uri.match('a')
    assert uri.match('a.b')
    assert uri.match('b') == False

    # Test context wildcard suffix matches
    uri = WAMPURI('a**')
    match_list.append(uri)
    assert uri.match('a')
    assert uri.match('a.b')
    assert uri.match('b') == False

    # Test explicit exact matches
    uri = WAMPURI('a.*.b',options={'match':'exact'})
    match_list.append(uri)
    assert uri.match('a.*.b')
    assert uri.match('a.*.d') == False

    # Test explicit prefix matches
    uri = WAMPURI('a.b',options={'match':'wildcard'})
    match_list.append(uri)
    assert uri.match('a.b')
    assert uri.match('a.d.b') == False

    # Test explicit wildcard matches
    uri = WAMPURI('a..b',options={'match':'wildcard'})
    match_list.append(uri)
    assert uri.match('a.c.b')
    assert uri.match('a.c.d.b')
    assert uri.match('a.c.d') == False

    # Check that WAMPURI parameters work
    uri = WAMPURI('foo',{'a':'b'})
    assert uri['a'] == 'b'
    assert uri.get('b') == None
    uri['b'] = 'c'
    assert uri['b'] == 'c'
    assert uri.get('b') == 'c'

    # Now create a test URI setup
    assert len(match_list.match('a')) == 2
    assert len(match_list.match('a.b')) == 3

