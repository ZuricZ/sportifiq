from cryptography.fernet import Fernet
import getpass

# Generate a key for encryption and decryption
# In an actual usage situation, you'd only do this once, then store this key securely
key = Fernet.generate_key()
cipher_suite = Fernet(key)

# Store the key in a secure place
with open("key.key", "wb") as key_file:
    key_file.write(key)

# Get the password in a secure manner
password = getpass.getpass('Please enter your password: ')
password = password.encode()

# Encrypt the password
ciphered_text = cipher_suite.encrypt(password)

# Write the encrypted password to a file
with open('password.dat', 'wb') as file_object:
    file_object.write(ciphered_text)
