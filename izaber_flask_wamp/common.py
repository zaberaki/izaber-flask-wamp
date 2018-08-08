import random
import six
from six.moves import queue

from swampyer.messages import *

STATE_DISCONNECTED = 0
STATE_CONNECTING = 1
STATE_WEBSOCKET_CONNECTED = 3
STATE_AUTHENTICATING = 4
STATE_CONNECTED = 2

SESSION_COOKIE = 'zfwid'

###########################################
# Data mangling and syntax sugar classes
###########################################

class DictObject(dict):
    def __init__(self, noerror=True, *args, **kwargs):
        super(DictObject, self).__init__(*args, **kwargs)
        self.__dict__ = self
        self.noerror_ = noerror

    def __getattr__(self,k):
        if self.noerror_:
            return self.__dict__.get(k)
        return super(DictObject).__getattr__(k)

    def __nonzero__(self):
        # Evaluate the object to "True" only if there is data contained within
        return bool(self.__dict__)

class DictInterface(object):
    """ Merely provides a way to manipulate attributes via
        obj[key] access rather than obj.key. Particularly
        useful for dynamic attributes
    """

    def __getitem__(self,k):
        return getattr(self,k)

    def __setitem__(self,k,v):
        return setattr(self,k,v)

class Listable(object):
    def __init__(self,data=None):
        if data is None:
            data = []
        self.data = data

    def filter(self,filter_function):
        items = filter(filter_function,self.data)
        return items

    def remove(self,filter_function):
        """ For all entries where the filter function returns True,
            the record will be removed from self.data
        """
        removed = list(self.filter(filter_function))
        self.data = list(self.filter(lambda d: not filter_function(d)))
        return removed

    def sort(self,key):
        self.data.sort(key=key)

    def append(self,item):
        self.data.append(item)

    def __getitem__(self,k):
        return self.data[int(k)]

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        for item in self.data:
            yield item

rng = random.SystemRandom()
def secure_rand():
    #return rng.randint(0,sys.maxsize)
    # Use the size from Javascript:
    # https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/MAX_SAFE_INTEGER
    return rng.randint(0,9007199254740991)

