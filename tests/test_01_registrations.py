#!/usr/bin/python3

import time

from swampyer.messages import *

from izaber_flask_wamp.uri import *
from izaber_flask_wamp.registrations import *

class MockClient(object):
    def __init__(self,return_message=None):
        self.return_message = return_message
        self.received_message = None

        self.session_id = None
        self.auth = {
                    'authid': 'test',
                    'role': 'role'
                }

    def closed(self):
        return False

    def send_and_await_response(self,send_message,on_yield):
        self.return_message.request_id = send_message.request_id
        on_yield(self.return_message)

    def send_message(self,message):
        self.received_message = message

def test_register():

    regs = WAMPRegistrations()

    assert regs != None

    ##########################################
    # Test registrations
    ##########################################

    #------------
    # Local
    #------------

    # Normal calls
    def test_call(*args,**kwargs):
        return "TEST"

    registration_id = regs.register_local('arf',test_call)
    assert registration_id != None

    call_message = CALL(
                      options={},
                      procedure='arf',
                      args=[1],
                      kwargs={'a':'2'}
                    )

    client = MockClient()
    data_capture = {}
    def on_yield(result):
        data_capture['result'] = result
    invoke_result = regs.invoke(client,call_message,on_yield)
    time.sleep(0.2)

    assert data_capture['result'].args[0] == 'TEST'
    assert data_capture['result']['details']['procedure'] == 'arf'

    # Can we unregister?
    unregister_id = regs.unregister(registration_id)
    assert unregister_id == registration_id

    # Check that we really did unregister
    try:
        invoke_result = regs.invoke(client,call_message,on_yield)
        time.sleep(0.2)
    except Exception as ex:
        assert str(ex) == 'uri does not exist'

    # What happens when there's an exception?
    def exception_call(*args,**kwargs):
        raise Exception("Whoops")
    registration_id = regs.register_local('arf',exception_call)
    invoke_result = regs.invoke(client,call_message,on_yield)
    time.sleep(0.2)

    assert data_capture['result'] == WAMP_ERROR

    unregister_id = regs.unregister(registration_id)
    assert unregister_id == registration_id

    #------------
    # Remote
    #------------

    client = MockClient(YIELD(
                    request_id=None,
                    options={},
                    args=['WORKING'],
                    kwargs={}
                ))
    registration_id = regs.register_remote('bloop',client)
    assert registration_id != None

    call_message = CALL(
                      options={},
                      procedure='bloop',
                      args=[1],
                      kwargs={'a':'2'}
                    )
    data_capture = {}
    def on_yield(result):
        data_capture['result'] = result
    invoke_result = regs.invoke(client, call_message,on_yield)

    assert data_capture['result'].args[0] == 'WORKING'

    # Can we unregister?
    unregister_id = regs.unregister(registration_id)
    assert unregister_id == registration_id

    # Check that we really did unregister
    try:
        invoke_result = regs.invoke(client, call_message,on_yield)
    except Exception as ex:
        assert str(ex) == 'uri does not exist'

    # What happens when there's an exception?
    client = MockClient(ERROR(
                    request_id=None,
                    options={},
                    args=['EXPLODED'],
                    kwargs={}
                ))
    registration_id = regs.register_remote('bloop',client)
    assert registration_id != None

    invoke_result = regs.invoke(client, call_message,on_yield)
    assert data_capture['result'] == WAMP_ERROR

    # Ensure we can reap
    assert len(regs.registered) == 1
    regs.reap_client(client)
    assert len(regs.registered) == 0


def test_subscriptions():

    regs = WAMPRegistrations()

    assert regs != None

    ##########################################
    # Test subscriptions
    ##########################################

    #------------
    # Local
    #------------

    # Normal subscriptions
    data_capture = {}
    def on_event(result):
        data_capture['result'] = result
    subscription_id = regs.subscribe_local('woof',on_event)
    assert subscription_id != None

    # Publish something
    result = regs.publish(PUBLISH(
                            options={},
                            topic='woof',
                            args=['BARK'],
                            kwargs={}
                        ))
    assert data_capture['result'] == WAMP_EVENT
    assert data_capture['result'].args[0] == 'BARK'

    # Unsubscribe
    data_capture = {}
    regs.unsubscribe(subscription_id)

    # And make sure we can't hear anymore
    result = regs.publish(PUBLISH(
                            options={},
                            topic='woof',
                            args=['BARK'],
                            kwargs={}
                        ))
    assert data_capture.get('result') == None

    #------------
    # Remote
    #------------

    client = MockClient()
    subscription_id = regs.subscribe_remote('woof',client)
    assert subscription_id != None

    # Publish something
    result = regs.publish(PUBLISH(
                            options={},
                            topic='woof',
                            args=['BARK'],
                            kwargs={}
                        ))
    assert client.received_message == WAMP_EVENT
    assert client.received_message.args[0] == 'BARK'


    # Unsubscribe
    regs.unsubscribe(subscription_id)
    client.received_message = None

    result = regs.publish(PUBLISH(
                            options={},
                            topic='woof',
                            args=['BARK'],
                            kwargs={}
                        ))

    assert client.received_message == None

    # Ensure we can reap
    subscription_id = regs.subscribe_remote('woof',client)
    assert subscription_id != None
    assert len(regs.subscribed) == 1
    regs.reap_client(client)
    assert len(regs.subscribed) == 0

if __name__ == '__main__':
    test_register()
    test_subscriptions()
