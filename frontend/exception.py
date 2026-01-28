class AuthError(RuntimeError):
    pass

class NotAuthenticatedError(AuthError):
    pass
