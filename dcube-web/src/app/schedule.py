from app import create_app,db
from service.scheduler import Scheduler

create_app().app_context().push()

def main():
    db.create_all()
    s = Scheduler()
    try:
        s.run()
    except KeyboardInterrupt:
        print("Stopping")

if __name__ == "__main__":
    main()
