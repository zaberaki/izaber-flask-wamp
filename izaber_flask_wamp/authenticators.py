import os
import json

from izaber.paths import paths
from izaber.templates import parsestr

from .common import *

# TODO: Make this fit better with Crossbar's actual authentication
# scheme for dynamic authorizers

class Authenticator(object):

    authmethod = None

    # Order of the authentication scheme: the lower
    # the number, the more likely it will be chosen for
    # the challenge method
    order = 0

    def __init__(self):
        pass

    def create_challenge(self,client,hello):
        """ Return the CHALLENGE object to be sent to the
            user. This module doesn't do any challenges
            so we return None
        """
        return

    def authenticate_on_hello(self,client,hello):
        return

    def authenticate_challenge_response(self,client,hello,challenge,authenticate):
        return

    def on_successful_authenticate(self,client,authorized):
        """ This should be called when a successful authentication
            takes place
        """
        return

class TicketAuthenticator(Authenticator):
    authmethod = 'ticket'

    def create_challenge(self,client,hello):
        """ Return the CHALLENGE object to be sent to the
            user. This module does ticket based challenges so we'll
            return that to the user
        """
        return CHALLENGE(
                        auth_method='ticket',
                        extra={}
                    )


    def ticket_authenticate(self,username,password):
        """ Return the role if the user authenticates successfully.
            Return None if unable to authenticate

            hello is the original request
            challenge is the server's challenge request
            authenticate is the response to the challenge
        """
        return None

    def authenticate_challenge_response(self,client,hello,challenge,authenticate):
        return self.ticket_authenticate(
                    hello.realm,
                    hello.details['authid'],
                    authenticate.signature
                )

class SimpleTicketAuthenticator(TicketAuthenticator):
    def __init__(self,users):
        """ This takes a list of users in the format:
            users = [
                {
                    login: 'USERNAME1',
                    password: 'PASSWORD1',
                    role: 'ROLENAME1'
                },
                ...
                {
                    login: 'USERNAMEn',
                    password: 'PASSWORDn',
                    role: 'ROLENAMEn'
                },
            ]

            This can also handle hash entries as well of
            the form:

            users = {
                'USERNAME1': {
                    'password': 'PASSWORD1',
                    'role': 'ROLENAME1',
                },
                ...
                'USERNAMEn': {
                    'password': 'PASSWORDn',
                    'role': 'ROLENAMEn',
                },
            }
        """
        if isinstance(users,list):
            self.users = users
            self.users_lookup = {}
            for user in users:
                self.users_lookup[user['login']] = user
        else:
            self.users = []
            self.users_lookup = {}
            for login, data in users.items():
                user_rec = dict(data)
                user_rec['login'] = login
                self.users.append(user_rec)
                self.users_lookup[login] = user_rec

    def ticket_authenticate(self,realm,username,password):
        """ Return the authenticated object if the user authenticates successfully.
            Return None if unable to authenticate

            challenge is the server's challenge request
            authenticate is the response to the challenge
        """
        user = self.users_lookup.get(username)
        if not user: return

        if user['password'] == password:
            return DictObject(
                authid=username,
                authprovider='dynamic',
                authmethod=self.authmethod,
                role=user['role'],
                realm=realm,
            )

        return

class CookieAuthenticator(Authenticator):
    """ Takes cookies and stores them away for future recall.

        Note that we operate under the expectation that ALL unique
        connections get a unique cookie.

    """
    authmethod = 'cookie'

    def __init__(self,cookie_path=None,cookie_name=None):
        if cookie_path == None:
            cookie_path = config.paths.cookies
        self.cookie_path = paths.full_fpath(cookie_path)
        if not os.path.exists(self.cookie_path):
            os.makedirs(self.cookie_path)
        self.cookie_name = cookie_name

    def session_fpath(self,cookie_value):
        fname = parsestr(config.flask.wamp.cookie_fname,cookie_value=cookie_value)
        fpath = os.path.join(self.cookie_path,fname)
        return fpath

    def session_load(self, cookie_value):
        fpath = self.session_fpath(cookie)
        if not os.path.exists(fpath):
            return
        try:
            with open(fpath) as f:
                auth = DictObject(json.load(f))
                return auth
        except:
            return

    def session_save(self, cookie_value, auth):
        fpath = self.session_fpath(cookie_value)
        try:
            with open(fpath,'w') as f:
                json.dump(f,dict(auth))
        except:
            return

    def authenticate_on_hello(self,client,hello):
        auth = client.auth
        cookie_name = self.cookie_name or client.app.cookie_name
        cookie_value = client.cookies.get(cookie_name)
        auth = self.session_load(cookie_value)
        if auth:
            client.auth = auth
            return client.auth
        except:
            return

    def on_successful_authenticate(self,client,authorized):
        auth = client.auth
        cookie_value = client.cookies.get(self.cookie_name or client.app.cookie_name)
        self.session_save(cookie_value,auth)

class WAMPAuthenticators(Listable):
    def select(self,hello):
        """ Select an authenticator to handle the hello request's
            auth
        """
        authmethods = hello.details['authmethods']
        if not authmethods:
            return

        self.sort(key=lambda a:a.order)

        matched = list(self.filter(lambda a:a.authmethod in authmethods))
        if not matched:
            return

        return matched[0]

    def create_challenge(self,client,hello):
        """ Find the first appropriate challenge handler and create
            a challenge response
        """
        authmethods = hello.details['authmethods']
        if not authmethods:
            return

        self.sort(key=lambda a:a.order)

        matched = self.filter(lambda a:a.authmethod in authmethods)
        for authenticator in matched:
            challenge = authenticator.create_challenge(client,hello)
            if challenge:
                return challenge

    def authenticate_challenge_response(self,client,hello,challenge,authenticate):
        authmethods = hello.details['authmethods']
        if not authmethods:
            return

        self.sort(key=lambda a:a.order)

        matched = self.filter(lambda a:a.authmethod in authmethods)
        for authenticator in matched:
            authenticated = authenticator.authenticate_challenge_response(
                                                        client,
                                                        hello,
                                                        challenge,
                                                        authenticate)
            if authenticated:
                return authenticated


    def authenticate_on_hello(self,client,hello):
        """ Attempt to authenticate based upon the request provided
        """
        authmethods = hello.details['authmethods']
        if not authmethods:
            return

        self.sort(key=lambda a:a.order)

        matched = self.filter(lambda a:a.authmethod in authmethods)
        for authenticator in matched:
            print("TESTING WITH:", authenticator)
            import traceback; traceback.print_stack()
            authenticated = authenticator.authenticate_on_hello(client,hello)
            print("AUTHENTICATED WITH:", authenticated)
            if authenticated:
                return authenticated
        return

    def on_successful_authenticate(self,client,authorized):
        """ This should be called when a successful authentication
            takes place. We iterate over all the authorizers just in
            case they want to do something.
        """
        print("CALLED: on_success_authenticate")
        for authenticator in self:
            print("UPDATING SUCCESS:",authenticator)
            authenticator.on_successful_authenticate(client,authorized)

