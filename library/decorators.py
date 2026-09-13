from django.core.exceptions import PermissionDenied

def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_admin():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


def librarian_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not (
            request.user.is_librarian() or request.user.is_admin()
        ):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper