import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet


class CaseInsensitiveDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._convert_keys()

    def __getitem__(self, key):
        return super().__getitem__(key.lower())

    def __setitem__(self, key, value):
        super().__setitem__(key.lower(), value)

    def __delitem__(self, key):
        return super().__delitem__(key.lower())

    def __contains__(self, key):
        return super().__contains__(key.lower())

    def update(self, other=(), /, *args, **kwds):
        super().update(other, *args, **kwds)
        self._convert_keys()

    def _convert_keys(self):
        for key in list(self.keys()):
            val = super().pop(key)
            self.__setitem__(key, val)


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


def decrypt_password():
    # retrieve the key from secure storage
    with open("key.key", "rb") as key_file:
        key = key_file.read()
    cipher_suite = Fernet(key)
    # read the encrypted password from the file
    with open('password.dat', 'rb') as file_object:
        encryptedpwd = file_object.read()
    return cipher_suite.decrypt(encryptedpwd).decode('utf-8')


def convert_to_european_time(server_time_str):
    # Extract datetime from string (remove "Server time: " prefix)
    datetime_str = server_time_str.split(": ", 1)[1]

    # Parse GMT time and set UTC timezone
    gmt_time = datetime.strptime(datetime_str, '%a, %d %b %Y %H:%M:%S GMT')
    gmt_time = gmt_time.replace(tzinfo=ZoneInfo("UTC"))

    # Convert to Europe/Berlin time (auto-handles CET/CEST)
    europe_time = gmt_time.astimezone(ZoneInfo("Europe/Berlin"))
    return europe_time.strftime('%Y-%m-%d %H:%M:%S %Z')


