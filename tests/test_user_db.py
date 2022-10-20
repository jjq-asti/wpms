import pytest
from wmps import db


class TestDB:
    def test_config_username_password_ok(self):
        assert(db.username)
