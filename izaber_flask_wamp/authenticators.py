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
    def authenticate_on_hello(self,client,hello):
        cookie = client.cookies.get()

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
            authenticated = authenticator.authenticate_challenge_response(client,hello,challenge,authenticate)
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
            authenticated = authenticator.authenticate_on_hello(client,hello)
            if authenticated:
                return authenticated
        return

    def on_successful_authenticate(self,client,authorized):
        """ This should be called when a successful authentication
            takes place. We iterate over all the authorizers just in
            case they want to do something.
        """
        for authenticator in self:
            authenticator.on_successful_authenticate(client,authorized)

