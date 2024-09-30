import base64
from collections.abc import Iterable
import datetime as dt
import hashlib
from os import environ
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

from cryptography.fernet import Fernet


TMP_DPATH = Path(tempfile.gettempdir()) / 'env-config'


def print_err(*args, **kwargs):
    kwargs.setdefault('file', sys.stderr)
    return print(*args, **kwargs)


def sub_run(
    *args,
    capture=False,
    returns: None | Iterable[int] = None,
    **kwargs,
) -> subprocess.CompletedProcess:
    kwargs.setdefault('check', not bool(returns))
    capture = kwargs.setdefault('capture_output', capture)
    args = args + kwargs.pop('args', ())
    env = kwargs.pop('env', None)
    if env:
        kwargs['env'] = environ | env
    if capture:
        kwargs.setdefault('text', True)

    try:
        result = subprocess.run(args, **kwargs)
        if returns and result.returncode not in returns:
            raise subprocess.CalledProcessError(result.returncode, args[0])
        return result
    except subprocess.CalledProcessError as e:
        if capture:
            print_err('subprocess stdout:', e.stdout)
            print_err('subprocess stderr:', e.stderr)
        raise


def op_read(uri: str):
    return sub_run('op', 'read', '-n', uri, capture=True).stdout


def machine_ident():
    """
    Return a deterministic value based on the current machine's hardware and OS.

    Intended to be used to encrypt AWS session details that will be stored on the file system.
    Predictible but just trying to keep a rogue app on the dev's system from scraping creds
    from a plain text file.  Should be using a dedicated not-important account for testing anyway.
    """
    etc_mid = Path('/etc/machine-id')
    dbus_mid = Path('/var/lib/dbus/machine-id')
    machine_id = etc_mid.read_text() if etc_mid.exists() else dbus_mid.read_text()

    return str(uuid.getnode()) + machine_id


class EncryptedTempFile:
    """
    NOT ROBUST against determined attacker!

    Just a small step up from security through obscurity.
    """

    def __init__(
        self,
        identifier: str,
        dpath: Path | None = None,
        enc_key: str | None = None,
    ):
        dpath = dpath or TMP_DPATH
        fname = hashlib.sha256(identifier.encode()).hexdigest()
        self.fpath: Path = (dpath / fname).with_suffix('.bin')

        enc_key = enc_key or (machine_ident() + identifier)
        # sha256 gives us 32 bytes, which is what fernet needs
        id_hash: bytes = hashlib.sha256(enc_key.encode()).digest()
        # b64encode b/c that's how Fernet.generate_key() does it
        self.fernet_key: str = base64.urlsafe_b64encode(id_hash)

    def save(self, data: bytes) -> None:
        cipher_suite = Fernet(self.fernet_key)
        encrypted_data = cipher_suite.encrypt(data)
        self.fpath.write_bytes(encrypted_data)

    def read(self) -> bytes:
        blob: bytes = self.fpath.read_bytes()

        cipher_suite = Fernet(self.fernet_key)
        return cipher_suite.decrypt(blob)

    def exists(self) -> bool:
        return self.fpath.exists()


def utc_now():
    return dt.datetime.now(dt.UTC)


def utc_now_in(**kwargs):
    return utc_now() + dt.timedelta(**kwargs)
