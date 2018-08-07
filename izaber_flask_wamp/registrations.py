import threading

from .uri import *

class WAMPRegistrations(object):
    def __init__(self):
        self.registered = WAMPURIList()
        self.subscribed = WAMPURIList()

    def register_local(self,uri,callback,options=None):
        """ Registers a local function for handling requests.
            This is the end function of using the @wamp.register
            decorator on a function
        """
        registration_id = secure_rand()
        reg_uri = WAMPURI(uri,{
                        'type': 'local',
                        'callback': callback,
                        'registration_id': registration_id,
                    },options)
        self.registered.append(reg_uri)
        return registration_id

    def register_remote(self,uri,client,options=None):
        """ Adds a client that's offering to support a particular
            callback on a uri
        """
        registration_id = secure_rand()
        self.registered.append(
            WAMPURI(uri,{
                'type': 'remote',
                'client': client,
                'registration_id': registration_id,
            },options)
        )
        return registration_id

    def unregister(self,registration_id):
        """ Removes a URI as a callback target
        """
        self.registered.remove(lambda r: r['registration_id'] == registration_id)
        return registration_id

    def invoke(self,request,callback):
        """ Runs the RPC code associated with the URI
        """
        uri = request.procedure
        args = request.args
        kwargs = request.kwargs

        handlers = self.registered.match(uri)
        if not handlers:
            raise Exception('uri does not exist')

        # Use the first matched handler
        handler = handlers[0]

        details = {
            'procedure': uri,
        }

        if handler['type'] == 'local':
            def thread_run():
                try:
                    result = handler['callback'](*args,**kwargs)
                    callback(RESULT(
                        request_id = request.request_id,
                        details = details,
                        args = [ result ],
                        kwargs = {}
                    ))
                except Exception as ex:
                    callback(ERROR(
                        request_code = WAMP_INVOCATION,
                        request_id = request.request_id,
                        details = details,
                        error = uri,
                        args = [u'Call failed: {}'.format(ex)],
                    ))

            thread_process = threading.Thread(target=thread_run)
            thread_process.daemon = True
            thread_process.start()
        elif handler['type'] == 'remote':
            def on_yield(result):
                if result == WAMP_YIELD:
                    callback(RESULT(
                        request_id = request.request_id,
                        details = details,
                        args = result.args,
                        kwargs = result.kwargs
                    ))
                else:
                    callback(result)

            registration_id = handler['registration_id']
            client = handler['client']
            if client.closed():
                self.reap_client(client)
                raise Exception('uri does not exist')
            client.send_and_await_response(
                INVOCATION(
                    request_id=request.request_id,
                    registration_id=registration_id,
                    details=details
                ),
                on_yield
            )
        else:
            raise Exception('Unknown handler type')

    def subscribe_local(self,uri,callback,options=None):
        """ Registers a local function to be invoked when the URI
            matches a particular pattern
        """
        subscription_id = secure_rand()
        sub_uri = WAMPURI(uri,{
                'subscription_id': subscription_id,
                'type': 'local',
                'callback': callback,
            },options)
        self.subscribed.append(sub_uri)
        return subscription_id

    def subscribe_remote(self,uri,client,options=None):
        """ Registers a remote function to be invoked when the URI
            matches a particular pattern
        """
        subscription_id = secure_rand()
        sub_uri = WAMPURI(uri,{
                        'subscription_id': subscription_id,
                        'type': 'remote',
                        'client': client,
                    },options)
        self.subscribed.append(sub_uri)
        return subscription_id

    def unsubscribe(self,subscription_id):
        """ Removes a URI as a subscriber target
        """
        self.subscribed.remove(lambda r: r['subscription_id'] == subscription_id)
        return subscription_id

    def publish(self,request):
        """ Send the publication to all subscribers
            (If there are any...)
        """
        uri = request.topic
        publish_id = secure_rand()

        details = {
            'topic': uri
        }

        subscribers = self.subscribed.match(uri)
        for subscriber in subscribers:
            publish_event = EVENT(
                subscription_id = subscriber['subscription_id'],
                publish_id = publish_id,
                args = request.args,
                kwargs = request.kwargs,
                details = details,
            )
            if subscriber['type'] == 'local':
                subscriber['callback'](publish_event)
            elif subscriber['type'] == 'remote':
                client = subscriber['client']
                if client.closed():
                    self.reap_client(client)
                    continue
                client.send_message(publish_event)

        return publish_id

    def reap_client(self,client):
        """ Removes a client from all registrations and subcriptions
            Usually used when a client disconnects
        """
        self.registered.remove(lambda r: r.get('client') == client)
        self.subscribed.remove(lambda r: r.get('client') == client)

