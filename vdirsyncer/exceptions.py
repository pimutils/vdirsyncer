class Error(Exception):
    pass

class NotFoundError(Error):
    pass

class AlreadyExistingError(Error):
    pass

class WrongEtagError(Error):
    pass
