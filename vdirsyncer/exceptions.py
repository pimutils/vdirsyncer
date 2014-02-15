class Error(Exception):
    pass

class AlreadyExistingError(Error):
    pass

class WrongEtagError(Error):
    pass
