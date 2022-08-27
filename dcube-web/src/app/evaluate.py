from app import create_app,db
from service.evaluator import Evaluator

create_app().app_context().push()

def main():
    db.create_all()
    e = Evaluator()
    try:
        e.run()
    except KeyboardInterrupt:
        print("Stopping")

if __name__ == "__main__":
    main()
