#!/usr/bin/python

from setuptools import setup

setup(name='izaber_flask_wamp',
      version='1.0',
      description='Base load point for iZaber WAMP services through Flask',
      url = 'https://github.com/zabertech/izaber-flask-wamp',
      download_url = 'https://github.com/zabertech/izaber-flask-wamp/archive/1.0.tar.gz',
      author='Aki Mimoto',
      author_email='aki+izaber@zaber.com',
      license='MIT',
      packages=['izaber_flask_wamp'],
      scripts=[],
      install_requires=[
          'izaber_flask',
          'Flask-Sockets',
          'swampyer',
      ],
      dependency_links=[],
      zip_safe=False)

