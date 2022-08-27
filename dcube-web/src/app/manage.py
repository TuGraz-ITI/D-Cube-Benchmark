from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand
from app import create_app,db

app=create_app()

migrate = Migrate(app, db)

manager = Manager(app)
manager.add_command('db', MigrateCommand)

if __name__ == '__main__':
    manager.run()
