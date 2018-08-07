from .common import *
from .uri import *

class WAMPAuthorizer(WAMPURI):
    def authorize(self, session, uri, action, options=None):
        """ Returns a hash describing how to handle this request to the URI
            action can be one of: publish, subscribe, register, or call

            Session should be something like:

            session = {
                'realm': 'izaber',
                'authprovider': 'dynamic', # Seems like static vs dynmiac
                'authrole': 'test',
                'authmethod': 'anonymous',
                'session': 1234
            }
        """
        return {'allow': False, 'disclose': False, 'cache': False }

class WAMPAuthorizeEverything(WAMPAuthorizer):
    """ Authorize everything for any user accessing the system.
        Becareful! This is means you have no protection at all!
    """
    def authorize(self, session, uri, action, options=None):
        return {'allow': True, 'disclose': True, 'cache': True }

class WAMPAuthorizeUsersEverything(WAMPAuthorizer):
    """ Authorize everything for logged in users. Anonymous users
        get nothing.
    """
    def authorize(self, session, uri, action, options=None):
        if session.get('authrole','anonymous') == 'anonymous':
            return {'allow': False, 'disclose': False, 'cache': False }
        return {'allow': True, 'disclose': True, 'cache': True }

class WAMPAuthorizers(WAMPURIList):
    def authorize(self, session, uri, action, options=None):
        """ Finds the most appropriate authorizer then asks it to return
            what the client's permissions should be.

            Returns a hash describing how to handle this request to the URI
            action can be one of: publish, subscribe, register, or call

            Session should be something like:

            session = {
                'realm': 'izaber',
                'authprovider': 'dynamic', # Seems like static vs dynmiac
                'authrole': 'test',
                'authmethod': 'anonymous',
                'session': 1234
            }
        """
        if action not in['publish','subscribe','register','call']:
            raise Exception('Unknown Action!')
        matches = self.match(uri)
        if matches:
            return matches[0].authorize(session,uri,action,options)
        return {'allow': False, 'disclose': False, 'cache': False }

