#flask-security stuff
from flask_security import SQLAlchemyUserDatastore

from backend.database import db
from models.user import User
from models.role import Role

# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)

from flask_security.forms import LoginForm
from wtforms import StringField
from wtforms.validators import InputRequired

class ExtendedLoginForm(LoginForm):
    email = StringField('Username', [InputRequired()])
