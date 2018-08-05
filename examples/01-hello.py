#!/usr/bin/python

from izaber import initialize
from izaber.paths import paths
from izaber.flask.wamp import IZaberFlask, wamp

app = IZaberFlask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'

@wamp.register('echo')
def echo(data):
    return data+" RESPONSE!"

@wamp.subscribe('hellos')
def hellos(data):
    print("Received subscribed message:", data.dump())

if __name__ == '__main__':
    initialize('example',environment='debug')
    print("Running")
    app.run()


