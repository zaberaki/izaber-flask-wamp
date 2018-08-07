from .app import *

class IZaberFlaskLocalWAMP(object):
    """ Allows the creation and sending of calls and functions
    """
    def __init__(self,sockets,app):
        self.sockets = sockets
        self.app = app

        self.on_connect = []
        self.on_disconnect = []


    def register(self,uri,options=None):
        """ A method to use a decorator to register a callback
        """
        def actual_register_decorator(f):
            self.app.register_local(uri, f, options)
            return f
        return actual_register_decorator

    def subscribe(self,uri,options=None):
        """ A method to use a decorator to subscribe a callback
        """
        def actual_subscribe_decorator(f):
            self.app.subscribe_local(uri, f, options)
            return f
        return actual_subscribe_decorator

    def publish(self,topic,options=None,args=None,kwargs=None):
        self.app.publish(PUBLISH(
            options=options or {},
            topic=topic,
            args=args or [],
            kwargs=kwargs or {}
        ))

    def wamp_connect(self):
        """ A decorator to attach to when someone connects
        """
        return lambda f: self.on_connect.append(f)

    def wamp_disconnect(self):
        """ A decorator to attach to when someone disconnects
        """
        return lambda f: self.on_disconnect.append(f)

    def do_wamp_connect(self,client):
        """ A decorator to attach to when someone connects
        """
        for f in self.on_connect:
            f(client)

    def do_wamp_disconnect(self,client):
        """ A decorator to attach to when someone disconnects
        """
        for f in self.on_disconnect:
            f(client)

