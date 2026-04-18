"""One-time setup: generate key.key and password.dat for local runs."""
import getpass

from cryptography.fernet import Fernet

if __name__ == "__main__":
    key = Fernet.generate_key()
    cipher_suite = Fernet(key)

    with open("key.key", "wb") as key_file:
        key_file.write(key)

    password = getpass.getpass("Please enter your password: ").encode()
    ciphered_text = cipher_suite.encrypt(password)

    with open("password.dat", "wb") as file_object:
        file_object.write(ciphered_text)

    print("key.key and password.dat written.")
