from unittest import mock


def patch_obj(*args, **kwargs):
    kwargs.setdefault('autospec', True)
    kwargs.setdefault('spec_set', True)
    return mock.patch.object(*args, **kwargs)


def patch(*args, **kwargs):
    kwargs.setdefault('autospec', True)
    kwargs.setdefault('spec_set', True)
    return mock.patch(*args, **kwargs)
