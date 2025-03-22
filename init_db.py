from main import db, app

with app.app_context():
    db.create_all()
    print("Databse initialized successfully.")