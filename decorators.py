from functools import wraps
from flask import request,redirect,abort
from backend import BACKEND

def wait(redirect_to=None):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            path = request.path.lower()

            blocked_pages = BACKEND.blocked_pages

            for blocked_page in blocked_pages:
                if path.startswith(blocked_page.lower()):
                    if redirect_to is not None:
                        return redirect(redirect_to)
                    else:
                        abort(403)

            # no match -> call original view
            return view_func(*args, **kwargs)

        return wrapped
    return decorator