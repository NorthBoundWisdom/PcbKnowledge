"""Repository-scoped derived outputs tolerate system aliases above their authority."""
from pathlib import Path
import stat


def redirected(path):
    if path.is_symlink():
        return True
    try:
        return bool(getattr(path.lstat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except FileNotFoundError:
        return False


def repository_boundary(root, path):
    root = Path(root).absolute()
    parent = root.parent.resolve()
    return next((p for p in reversed((path, *path.parents))
                 if p.name == root.name and p.parent.resolve() == parent), None)


def repository_path(root, value):
    root = Path(root).absolute()
    if redirected(root):
        raise ValueError('Repository root must not redirect through a symlink or reparse point')
    parent = root.parent.resolve()
    canonical = parent / root.name
    path = Path(value)
    path = path if path.is_absolute() else root / path
    boundary = repository_boundary(root, path)
    if boundary is None:
        raise ValueError('Path is outside the repository')
    for p in (path, *path.parents):
        if redirected(p):
            raise ValueError('Repository paths must not traverse symlinks or reparse points')
        if p == boundary:
            break
    result = path.resolve()
    if not result.is_relative_to(canonical):
        raise ValueError('Path escapes repository')
    return result


def derived_output(root, value):
    try:
        path = repository_path(root, value)
    except ValueError as error:
        raise ValueError(f'Derived output must be written below build/: {error}') from error
    build = Path(root).resolve() / 'build'
    if not path.is_relative_to(build) or path == build:
        raise ValueError('Derived output must be written below build/')
    return path
