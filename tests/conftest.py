import os
import pytest
from dotenv import load_dotenv
from app.__main__ import app as my_app
from app.models import db as _db, User

load_dotenv()
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

DATABASE_URL = f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"


@pytest.fixture
def app():
    _app = my_app
    _app.config["TESTING"] = True
    _app.config[
        "SQLALCHEMY_DATABASE_URI"] = f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

    with _app.app_context():
        _db.create_all()

        test_user = _db.session.query(User).filter(User.api_key == 'test').one_or_none()
        if not test_user:
            test_user = User(
                name='test',
                api_key='test'
            )

            _db.session.add(test_user)

        test_user_two = _db.session.query(User).filter(User.api_key == 'test_two').one_or_none()
        if not test_user_two:
            test_user_two = User(
                name='test_two',
                api_key='test_two'
            )

            _db.session.add(test_user_two)

        _db.session.commit()

        yield _app
        _db.session.close()
        _db.drop_all()


@pytest.fixture
def client(app):
    client = app.test_client()
    yield client


@pytest.fixture
def db(app):
    with app.app_context():
        yield _db
