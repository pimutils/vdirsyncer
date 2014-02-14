class Syncer(object):
    def list_items(self):
        '''
        :returns: list of (href, etag)
        '''
        raise NotImplementedError()

    def get_items(self, hrefs):
        '''
        :param hrefs: list of hrefs to fetch
        :returns: list of (object, href, etag)
        '''
        raise NotImplementedError()

    def item_exists(self, href):
        '''
        check if item exists
        '''
        raise NotImplementedError()

    def upload(self, obj):
        '''
        Upload a new object, raise error if it already exists.
        :returns: (href, etag)
        '''
        raise NotImplementedError()

    def update(self, obj, etag):
        '''
        Update the object, raise error if the etag on the server doesn't match
        the given etag.

        :returns: etag on the server
        '''
        raise NotImplementedError()
