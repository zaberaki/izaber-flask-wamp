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

    def create_challenge(self,hello):
        """ Return the CHALLENGE object to be sent to the
            user
        """
        return CHALLENGE(
                        auth_method='ticket',
                        extra={}
                    )

    def authenticate_challenge_response(self,hello,challenge,authenticate):
        pass

class TicketAuthenticator(Authenticator):
    authmethod = 'ticket'

    def ticket_authorize(self,username,password):
        """ Return the role if the user authenticates successfully.
            Return None if unable to authenticate

            hello is the original request
            challenge is the server's challenge request
            authenticate is the response to the challenge
        """
        return None

    def authenticate_challenge_response(self,hello,challenge,authenticate):
        return self.ticket_authorize(
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
        """
        self.users = users
        self.users_lookup = {}
        for user in users:
            self.users_lookup[user['login']] = user

    def ticket_authorize(self,username,password):
        """ Return the role if the user authenticates successfully.
            Return None if unable to authenticate

            challenge is the server's challenge request
            authenticate is the response to the challenge
        """
        user = self.users_lookup.get(username)
        if not user: return

        if user['password'] == password:
            return user['role']

        return

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

