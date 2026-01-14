import json
from unittest.mock import patch
from sqlalchemy.exc import IntegrityError
from psycopg2.errors import UniqueViolation
from app.models import User, Subscribe


def test_create_subscribe_success(client, db):
    """Тест: успешное создание подписки на пользователя"""
    user1 = User.query.filter_by(api_key='test').first()
    user2 = User.query.filter_by(api_key='test_two').first()

    headers = {
        'API_KEY': 'test'
    }

    response = client.post(f'/api/users/{user2.id}/follow', headers=headers)

    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data['result'] is True

    subscribe = Subscribe.query.filter_by(
        subscriber_id=user1.id,
        target_id=user2.id
    ).first()

    assert subscribe is not None


def test_create_subscribe_self(client):
    """Тест: попытка подписаться на самого себя"""
    user = User.query.filter_by(api_key='test').first()

    headers = {
        'API_KEY': 'test'
    }

    response = client.post(f'/api/users/{user.id}/follow', headers=headers)

    assert response.status_code >= 400


def test_create_subscribe_no_api_key(client, db):
    """Тест: попытка подписаться без API ключа"""
    user = User.query.filter_by(api_key='test_two').first()

    response = client.post(f'/api/users/{user.id}/follow')

    assert response.status_code == 401
    json_data = response.get_json()
    assert json_data['errors'] == 'Такого пользователя не существует'


def test_create_subscribe_invalid_api_key(client, db):
    """Тест: попытка подписаться с неверным API ключом"""
    user = User.query.filter_by(api_key='test_two').first()

    headers = {
        'API_KEY': 'invalid_key'
    }

    response = client.post(f'/api/users/{user.id}/follow', headers=headers)

    assert response.status_code == 401


def test_create_subscribe_target_not_found(client):
    """Тест: попытка подписаться на несуществующего пользователя"""
    headers = {
        'API_KEY': 'test'
    }

    response = client.post('/api/users/999/follow', headers=headers)

    assert response.status_code in [404, 500]

    if response.status_code == 500:
        json_data = response.get_json()
        assert json_data['result'] is False
        assert 'error_type' in json_data


def test_create_subscribe_duplicate(client, db):
    """Тест: попытка повторно подписаться на того же пользователя"""
    user1 = User.query.filter_by(api_key='test').first()
    user2 = User.query.filter_by(api_key='test_two').first()

    subscribe = Subscribe(subscriber_id=user1.id, target_id=user2.id)
    db.session.add(subscribe)
    db.session.commit()

    headers = {
        'API_KEY': 'test'
    }

    response = client.post(f'/api/users/{user2.id}/follow', headers=headers)

    assert response.status_code == 409
    json_data = response.get_json()
    assert json_data['error'] == 'Вы уже подписаны на этого пользователя'


def test_create_subscribe_other_integrity_error(client, db, monkeypatch):
    """Тест: обработка других IntegrityError"""
    with patch('app.routers.db.session.add') as mock_add:
        mock_integrity_error = IntegrityError("Some other integrity error", {}, None)
        mock_integrity_error.orig = Exception("Not a UniqueViolation")
        mock_add.side_effect = mock_integrity_error

        user = User.query.filter_by(api_key='test_two').first()

        headers = {
            'API_KEY': 'test'
        }

        response = client.post(f'/api/users/{user.id}/follow', headers=headers)

        assert response.status_code == 500
        json_data = response.get_json()
        assert json_data['result'] is False
        assert json_data['error_type'] == 'IntegrityError'


def test_create_subscribe_other_exception(client, db, monkeypatch):
    """Тест: обработка других исключений"""
    with patch('app.routers.db.session.add', side_effect=Exception("Some other error")):
        user = User.query.filter_by(api_key='test_two').first()

        headers = {
            'API_KEY': 'test'
        }

        response = client.post(f'/api/users/{user.id}/follow', headers=headers)

        assert response.status_code == 500
        json_data = response.get_json()
        assert json_data['result'] is False
        assert 'error_type' in json_data


def test_delete_subscribe_success(client, db):
    """Тест: успешное удаление своей подписки"""
    user1 = User.query.filter_by(api_key='test').first()
    user2 = User.query.filter_by(api_key='test_two').first()

    subscribe = Subscribe(subscriber_id=user1.id, target_id=user2.id)
    db.session.add(subscribe)
    db.session.commit()
    subscribe_id = subscribe.id

    headers = {
        'API_KEY': 'test'
    }

    response = client.delete(f'/api/users/{user2.id}/follow', headers=headers)

    assert response.status_code == 204

    deleted_subscribe = db.session.get(Subscribe, subscribe_id)
    assert deleted_subscribe is None


def test_delete_subscribe_not_found(client):
    """Тест: попытка удалить несуществующую подписку"""
    headers = {
        'API_KEY': 'test'
    }

    response = client.delete('/api/users/999/follow', headers=headers)

    assert response.status_code == 404
    json_data = response.get_json()
    assert json_data['errors'] == 'Такой подписки не существует'


def test_delete_subscribe_no_api_key(client, db):
    """Тест: попытка удалить подписку без API ключа"""
    user1 = User.query.filter_by(api_key='test').first()
    user2 = User.query.filter_by(api_key='test_two').first()

    subscribe = Subscribe(subscriber_id=user1.id, target_id=user2.id)
    db.session.add(subscribe)
    db.session.commit()

    response = client.delete(f'/api/users/{subscribe.id}/follow')

    assert response.status_code == 401


def test_delete_subscribe_invalid_api_key(client, db):
    """Тест: попытка удалить подписку с неверным API ключом"""
    user1 = User.query.filter_by(api_key='test').first()
    user2 = User.query.filter_by(api_key='test_two').first()

    subscribe = Subscribe(subscriber_id=user1.id, target_id=user2.id)
    db.session.add(subscribe)
    db.session.commit()

    headers = {
        'API_KEY': 'invalid_key'
    }

    response = client.delete(f'/api/users/{subscribe.id}/follow', headers=headers)

    assert response.status_code == 401


def test_delete_subscribe_exception(client, db, monkeypatch):
    """Тест: обработка исключений при удалении подписки"""
    user1 = User.query.filter_by(api_key='test').first()
    user2 = User.query.filter_by(api_key='test_two').first()

    subscribe = Subscribe(subscriber_id=user1.id, target_id=user2.id)
    db.session.add(subscribe)
    db.session.commit()

    with patch('app.routers.db.session.commit', side_effect=Exception("Database error")):
        headers = {
            'API_KEY': 'test'
        }

        response = client.delete(f'/api/users/{user2.id}/follow', headers=headers)

        assert response.status_code == 500
        json_data = response.get_json()
        assert json_data['result'] is False
        assert 'error_type' in json_data

        assert db.session.get(Subscribe, subscribe.id) is not None


def test_subscribe_full_cycle(client, db):
    """Тест: полный цикл работы с подпиской (создание и удаление)"""
    user1 = User.query.filter_by(api_key='test').first()
    user2 = User.query.filter_by(api_key='test_two').first()

    headers_create = {'API_KEY': 'test'}
    response_create = client.post(f'/api/users/{user2.id}/follow', headers=headers_create)

    assert response_create.status_code == 201

    subscribe = Subscribe.query.filter_by(
        subscriber_id=user1.id,
        target_id=user2.id
    ).first()

    assert subscribe is not None
    subscribe_id = subscribe.id

    response_duplicate = client.post(f'/api/users/{user2.id}/follow', headers=headers_create)
    assert response_duplicate.status_code == 409

    headers_delete = {'API_KEY': 'test'}
    response_delete = client.delete(f'/api/users/{user2.id}/follow', headers=headers_delete)

    assert response_delete.status_code == 204

    assert db.session.get(Subscribe, subscribe_id) is None

    response_delete_again = client.delete(f'/api/users/{user2.id}/follow', headers=headers_delete)
    assert response_delete_again.status_code == 404


def test_subscribe_affects_user_info(client, db):
    """Тест: проверка влияния подписок на информацию о пользователе"""
    user1 = User.query.filter_by(api_key='test').first()
    user2 = User.query.filter_by(api_key='test_two').first()

    response1 = client.get(f'/api/users/{user1.id}')
    user1_data1 = response1.get_json()['user']
    assert len(user1_data1['following']) == 0
    assert len(user1_data1['followers']) == 0

    headers = {'API_KEY': 'test'}
    client.post(f'/api/users/{user2.id}/follow', headers=headers)

    response2 = client.get(f'/api/users/{user1.id}')
    user1_data2 = response2.get_json()['user']
    assert len(user1_data2['following']) == 1
    assert user1_data2['following'][0]['id'] == user2.id
    assert len(user1_data2['followers']) == 0

    response3 = client.get(f'/api/users/{user2.id}')
    user2_data = response3.get_json()['user']
    assert len(user2_data['followers']) == 1
    assert user2_data['followers'][0]['id'] == user1.id
    assert len(user2_data['following']) == 0


def test_mutual_subscriptions(client, db):
    """Тест: взаимные подписки между пользователями"""
    user1 = User.query.filter_by(api_key='test').first()
    user2 = User.query.filter_by(api_key='test_two').first()

    headers1 = {'API_KEY': 'test'}
    client.post(f'/api/users/{user2.id}/follow', headers=headers1)

    headers2 = {'API_KEY': 'test_two'}
    client.post(f'/api/users/{user1.id}/follow', headers=headers2)

    response1 = client.get(f'/api/users/{user1.id}')
    user1_data = response1.get_json()['user']
    assert len(user1_data['following']) == 1
    assert len(user1_data['followers']) == 1

    response2 = client.get(f'/api/users/{user2.id}')
    user2_data = response2.get_json()['user']
    assert len(user2_data['following']) == 1
    assert len(user2_data['followers']) == 1



def test_delete_subscribe_updates_user_info(client, db):
    """Тест: удаление подписки и проверка обновления информации"""
    user1 = User.query.filter_by(api_key='test').first()
    user2 = User.query.filter_by(api_key='test_two').first()

    subscribe = Subscribe(subscriber_id=user1.id, target_id=user2.id)
    db.session.add(subscribe)
    db.session.commit()
    subscribe_id = subscribe.id

    response1 = client.get(f'/api/users/{user1.id}')
    user1_data1 = response1.get_json()['user']
    assert len(user1_data1['following']) == 1

    headers = {'API_KEY': 'test'}
    client.delete(f'/api/users/{user2.id}/follow', headers=headers)

    response2 = client.get(f'/api/users/{user1.id}')
    user1_data2 = response2.get_json()['user']
    assert len(user1_data2['following']) == 0


def test_subscribe_data_integrity(client, db):
    """Тест: целостность данных при создании подписки"""
    user1 = User.query.filter_by(api_key='test').first()
    user2 = User.query.filter_by(api_key='test_two').first()

    headers = {'API_KEY': 'test'}
    response = client.post(f'/api/users/{user2.id}/follow', headers=headers)

    assert response.status_code == 201

    subscribe = Subscribe.query.filter_by(
        subscriber_id=user1.id,
        target_id=user2.id
    ).first()

    assert subscribe is not None
    assert subscribe.subscriber_id == user1.id
    assert subscribe.target_id == user2.id
    assert subscribe.id > 0

    subscribe_from_db = db.session.get(Subscribe, subscribe.id)
    assert subscribe_from_db is not None
    assert subscribe_from_db.subscribers.id == user1.id
    assert subscribe_from_db.targets.id == user2.id