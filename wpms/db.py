import configparser
import os
from pymongo import MongoClient

from dotenv import load_dotenv

load_dotenv()

config = configparser.ConfigParser()
config.read('wmps/wpms.ini')
address = config['mongodb']['address']
port = config['mongodb']['port']
username = os.environ.get('ADMINUSERNAME')
password = os.environ.get('ADMINPASSWORD')


class DBHandler(MongoClient):
    def __init__(self):
        self.uri = "mongodb://{}:{}@{}:{}".format(
            username, password, address, port)
        print(self.uri)
        super().__init__(self.uri)

    def get_user_model(self):
        return self.user.model

    def __del__(self):
        self.close()
        print("DB connection closed")


if __name__ == "__main__":
    # create unique index on username field
    client = DBHandler()
    client.user.model.create_index([('username', 1)], unique=True)
