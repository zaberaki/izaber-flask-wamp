import re

from .common import *

###########################################
# Handling of URIs
###########################################

class WAMPURI(object):
    def __init__(self,uri,payload=None,options=None):
        """ Hooks the payload up to a URI
        """
        self.uri = uri
        self.match_uri = uri
        self.payload = payload or {}
        self.options = options or {'match':None}

        self.prefix = False
        self.regex = False
        self.scheme = self.options.get('match')

        if self.scheme == 'exact':
            return

        elif self.scheme == 'prefix':
            self.prefix = True
            return

        elif self.scheme == 'wildcard':
            self.scheme = 'regex'
            regex_elements = []
            for e in self.match_uri.split('.'):
                if e == '':
                    regex_elements.append('.*')
                else:
                    regex_elements.append(re.escape(e))

            regex = "^"+"\\.".join(regex_elements)+"$"
            self.regex = re.compile(regex)
            return

        try:
            if self.uri[-2:] == '**':
                self.prefix = True
                self.scheme = 'regex'
                self.match_uri = uri[:-2]
        except IndexError:
            pass

        if self.uri[-1] == '*' and self.scheme != 'regex':
            self.scheme = 'prefix'
            self.match_uri = uri[:-1]
            return

        # Now look for wildcards within the uri
        elements = map(re.escape,self.match_uri.split('*'))
        regex = "^" + ".*".join(elements)
        if not self.prefix:
            regex += '$'

        self.regex = re.compile(regex)
        self.scheme = 'regex'

    def match(self,uri):
        """ Respect the match pattern defined to see where
            to send the requests
        """
        if self.scheme == 'prefix':
            try:
                return uri.index(self.match_uri) == 0
            except:
                return False

        elif self.scheme == 'regex':
            if self.regex.search(uri):
                return True
            else:
                return False

        elif self.scheme == 'exact':
            return uri == self.uri

        # URIs are matching
        if uri == self.match_uri:
            return True

        return False

    def __getitem__(self,k):
        return self.payload[k]

    def __setitem__(self,k,v):
        self.payload[k] = v

    def __str__(self):
        return '<WAMPURI({s.uri})=>{s.payload}>'.format(s=self)

    def get(self,k,default=None):
        return self.payload.get(k,default)

class WAMPURIList(Listable):
    def match(self,uri):
        return list(self.filter(
            lambda u: u.match(uri)
        ))

