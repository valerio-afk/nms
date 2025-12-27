from . import  BACKEND
from functools import wraps
from flask import request,redirect,abort
from typing import Optional, Any, Callable

def wait(redirect_to:Optional[str]=None, tag:Optional[str]=None) -> Callable:
    def decorator(view_func:Callable)->Callable:
        @wraps(view_func)
        def wrapped(*args, **kwargs) -> Any:
            path = request.path.lower()

            for task in BACKEND.get_tasks:
                if path.startswith(task.page):
                    if (tag is None) or (task.tag == tag):
                        if not task.completed:
                            if redirect_to is not None:
                                return redirect(redirect_to)
                            else:
                                abort(403)

            # no match -> call original view
            return view_func(*args, **kwargs)

        return wrapped
    return decorator