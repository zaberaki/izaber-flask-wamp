#!/usr/bin/python

from izaber import initialize
from izaber.paths import paths
from izaber.flask.wamp import app, wamp

@app.route('/')
def hello_world():
    return 'Hello, World!'

@wamp.register('com.izaber.wamp.echo')
def echo(data):
    return data+" RESPONSE!"

if __name__ == '__main__':
    initialize('example',environment='debug')
    print "Running"
    app.run()


