from cryptography.fernet import Fernet
from db import DBHandler

from pymongo.errors import DuplicateKeyError


def generate_token():
    token = Fernet.generate_key()
    return token


def encrypt_password(password, token):
    fernet = Fernet(token)
    encrypted_password = fernet.encrypt(bytes(password.encode()))
    return encrypted_password


def create_user(username, password, **kwargs):
    token = generate_token()
    password = encrypt_password(password, token)
    user_model = {
        "username": username,
        "password": password,
        "token": token
        }
    client = DBHandler()
    user_db = client.get_user_model()
    try:
        id = user_db.insert_one(user_model).inserted_id
        return id
    except DuplicateKeyError:
        print("Username Already Exists!")


if __name__ == "__main__":
    id = create_user("kay", "supersecretpassword")
    print(id)
