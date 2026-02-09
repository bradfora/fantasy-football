"""User model for Flask-Login integration."""

from flask_login import UserMixin


class User(UserMixin):
    """Wraps a MongoDB user document for Flask-Login."""

    def __init__(self, user_doc):
        self._doc = user_doc

    def get_id(self):
        return str(self._doc["_id"])

    @property
    def username(self):
        return self._doc["username"]
