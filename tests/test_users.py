from app.models import User, Subscribe
from unittest.mock import patch, MagicMock


def test_get_my_account_info_no_subscriptions(client, db):
    """Тест: получение информации о текущем пользователе без подписок"""
    headers = {
        'API_KEY': 'test'
    }

    response = client.get('/api/users/me', headers=headers)

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['result'] is True
    assert 'user' in json_data

    user_data = json_data['user']
    assert user_data['id'] == 1
    assert user_data['name'] == 'test'
    assert user_data['followers'] == []
    assert user_data['following'] == []


def test_get_my_account_info_with_subscriptions(client, db):
    """Тест: получение информации о текущем пользователе с подписками"""
    user_test = User.query.filter_by(api_key='test').first()
    user_test_two = User.query.filter_by(api_key='test_two').first()

    subscribe1 = Subscribe(subscriber_id=user_test_two.id, target_id=user_test.id)
    subscribe2 = Subscribe(subscriber_id=user_test.id, target_id=user_test_two.id)

    db.session.add_all([subscribe1, subscribe2])
    db.session.commit()

    headers = {
        'API_KEY': 'test'
    }

    response = client.get('/api/users/me', headers=headers)

    assert response.status_code == 200
    json_data = response.get_json()
    user_data = json_data['user']

    assert len(user_data['followers']) == 1
    assert user_data['followers'][0]['id'] == user_test_two.id
    assert user_data['followers'][0]['name'] == 'test_two'

    assert len(user_data['following']) == 1
    assert user_data['following'][0]['id'] == user_test_two.id
    assert user_data['following'][0]['name'] == 'test_two'


def test_get_my_account_info_no_api_key(client):
    """Тест: получение информации о текущем пользователе без API ключа"""
    response = client.get('/api/users/me')

    assert response.status_code == 401
    json_data = response.get_json()
    assert json_data['error'] == 'Пользователь не найден'


def test_get_my_account_info_invalid_api_key(client):
    """Тест: получение информации о текущем пользователе с неверным API ключом"""
    headers = {
        'API_KEY': 'invalid_key'
    }

    response = client.get('/api/users/me', headers=headers)

    assert response.status_code == 401


def test_get_account_info_by_id_public(client, db):
    """Тест: получение информации о пользователе по ID (публичный доступ)"""
    user = User.query.filter_by(api_key='test').first()

    response = client.get(f'/api/users/{user.id}')

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['result'] is True
    assert json_data['user']['id'] == user.id
    assert json_data['user']['name'] == 'test'
    assert json_data['user']['followers'] == []
    assert json_data['user']['following'] == []


def test_get_account_info_by_id_with_subscriptions(client, db):
    """Тест: получение информации о пользователе по ID с подписками"""
    user_test = User.query.filter_by(api_key='test').first()
    user_test_two = User.query.filter_by(api_key='test_two').first()

    subscribe1 = Subscribe(subscriber_id=user_test_two.id, target_id=user_test.id)
    subscribe2 = Subscribe(subscriber_id=user_test.id, target_id=user_test_two.id)

    db.session.add_all([subscribe1, subscribe2])
    db.session.commit()

    response = client.get(f'/api/users/{user_test.id}')

    assert response.status_code == 200
    json_data = response.get_json()
    user_data = json_data['user']

    assert len(user_data['followers']) == 1
    assert user_data['followers'][0]['id'] == user_test_two.id
    assert user_data['followers'][0]['name'] == 'test_two'

    assert len(user_data['following']) == 1
    assert user_data['following'][0]['id'] == user_test_two.id
    assert user_data['following'][0]['name'] == 'test_two'

    response2 = client.get(f'/api/users/{user_test_two.id}')
    user_data2 = response2.get_json()['user']

    assert len(user_data2['followers']) == 1
    assert user_data2['followers'][0]['id'] == user_test.id
    assert user_data2['followers'][0]['name'] == 'test'

    assert len(user_data2['following']) == 1
    assert user_data2['following'][0]['id'] == user_test.id
    assert user_data2['following'][0]['name'] == 'test'


def test_get_account_info_by_id_not_found(client):
    """Тест: получение информации о несуществующем пользователе по ID"""
    response = client.get('/api/users/999')

    assert response.status_code == 404
    json_data = response.get_json()
    assert json_data['errors'] == 'Пользователь не найден'


def test_get_account_info_complex_subscriptions(client, db):
    """Тест: сложная схема подписок между несколькими пользователями"""
    user1 = User.query.filter_by(api_key='test').first()
    user2 = User.query.filter_by(api_key='test_two').first()

    user3 = User(name='user3', api_key='key3')
    user4 = User(name='user4', api_key='key4')
    db.session.add_all([user3, user4])
    db.session.commit()

    subscribe1 = Subscribe(subscriber_id=user2.id, target_id=user1.id)
    subscribe2 = Subscribe(subscriber_id=user3.id, target_id=user1.id)
    subscribe3 = Subscribe(subscriber_id=user4.id, target_id=user1.id)
    subscribe4 = Subscribe(subscriber_id=user1.id, target_id=user2.id)
    subscribe5 = Subscribe(subscriber_id=user1.id, target_id=user3.id)

    db.session.add_all([subscribe1, subscribe2, subscribe3, subscribe4, subscribe5])
    db.session.commit()

    response = client.get(f'/api/users/{user1.id}')

    assert response.status_code == 200
    json_data = response.get_json()
    user1_data = json_data['user']

    assert len(user1_data['followers']) == 3

    follower_ids = [f['id'] for f in user1_data['followers']]
    assert user2.id in follower_ids
    assert user3.id in follower_ids
    assert user4.id in follower_ids

    assert len(user1_data['following']) == 2

    following_ids = [f['id'] for f in user1_data['following']]
    assert user2.id in following_ids
    assert user3.id in following_ids

    assert user4.id not in following_ids


def test_get_account_info_subscriptions_order(client, db):
    """Тест: проверка порядка следования подписок (должны быть в обратном порядке)"""
    user1 = User.query.filter_by(api_key='test').first()
    user2 = User.query.filter_by(api_key='test_two').first()

    user3 = User(name='user3', api_key='key3')
    user4 = User(name='user4', api_key='key4')
    db.session.add_all([user3, user4])
    db.session.flush()

    subscribe1 = Subscribe(subscriber_id=user2.id, target_id=user1.id)  # 1
    db.session.add(subscribe1)
    db.session.flush()

    subscribe2 = Subscribe(subscriber_id=user3.id, target_id=user1.id)  # 2
    db.session.add(subscribe2)
    db.session.flush()

    subscribe3 = Subscribe(subscriber_id=user4.id, target_id=user1.id)  # 3
    db.session.add(subscribe3)
    db.session.commit()

    response = client.get(f'/api/users/{user1.id}')
    user1_data = response.get_json()['user']

    assert len(user1_data['followers']) == 3
    assert user1_data['followers'][0]['id'] == user4.id
    assert user1_data['followers'][1]['id'] == user3.id
    assert user1_data['followers'][2]['id'] == user2.id


def test_compare_my_account_and_by_id_endpoints(client, db):
    """Тест: сравнение результатов двух эндпоинтов для одного пользователя"""
    user = User.query.filter_by(api_key='test').first()

    headers = {'API_KEY': 'test'}
    response_me = client.get('/api/users/me', headers=headers)
    data_me = response_me.get_json()['user']

    response_id = client.get(f'/api/users/{user.id}')
    data_id = response_id.get_json()['user']

    assert data_me['id'] == data_id['id']
    assert data_me['name'] == data_id['name']
    assert len(data_me['followers']) == len(data_id['followers'])
    assert len(data_me['following']) == len(data_id['following'])

    assert data_me['followers'] == data_id['followers']
    assert data_me['following'] == data_id['following']


def test_get_account_info_after_subscription_delete(client, db):
    """Тест: получение информации после удаления подписок"""
    user1 = User.query.filter_by(api_key='test').first()
    user2 = User.query.filter_by(api_key='test_two').first()

    subscribe = Subscribe(subscriber_id=user2.id, target_id=user1.id)
    db.session.add(subscribe)
    db.session.commit()
    subscribe_id = subscribe.id

    response1 = client.get(f'/api/users/{user1.id}')
    user1_data1 = response1.get_json()['user']
    assert len(user1_data1['followers']) == 1

    subscribe_to_delete = db.session.get(Subscribe, subscribe_id)
    db.session.delete(subscribe_to_delete)
    db.session.commit()

    response2 = client.get(f'/api/users/{user1.id}')
    user1_data2 = response2.get_json()['user']
    assert len(user1_data2['followers']) == 0


def test_get_account_info_many_followers(client, db):
    """Тест: пользователь с большим количеством подписчиков"""
    user_main = User.query.filter_by(api_key='test').first()

    test_users = []
    for i in range(10):
        user = User(name=f'test_follower_{i}', api_key=f'key_follower_{i}')
        test_users.append(user)

    db.session.add_all(test_users)
    db.session.flush()

    subscriptions = []
    for user in test_users:
        subscribe = Subscribe(subscriber_id=user.id, target_id=user_main.id)
        subscriptions.append(subscribe)

    db.session.add_all(subscriptions)
    db.session.commit()

    response = client.get(f'/api/users/{user_main.id}')
    user_data = response.get_json()['user']

    assert len(user_data['followers']) == 10

    follower_ids = [f['id'] for f in user_data['followers']]
    assert len(set(follower_ids)) == 10


from unittest.mock import patch, MagicMock


def test_get_my_account_info_database_error(client, db):
    """Тест: обработка ошибок базы данных при получении информации о пользователе"""
    with patch('app.routers.db.session.query') as mock_query:
        mock_query_instance = MagicMock()
        mock_options = MagicMock()
        mock_filter = MagicMock()

        mock_filter.one_or_none.side_effect = Exception('Database connection error')
        mock_options.filter.return_value = mock_filter
        mock_query_instance.options.return_value = mock_options
        mock_query.return_value = mock_query_instance

        headers = {'API_KEY': 'test'}
        response = client.get('/api/users/me', headers=headers)

        assert response.status_code == 500
        json_data = response.get_json()
        assert json_data['result'] is False
        assert json_data['error_type'] == 'Exception'
        assert 'Database connection' in json_data['error_message']


def test_get_account_info_empty_subscription_objects(client, db):
    """Тест: проверка обработки пустых объектов в подписках"""
    user = User.query.filter_by(api_key='test').first()

    subscribe = Subscribe(subscriber_id=user.id, target_id=999)

    headers = {'API_KEY': 'test'}
    response = client.get('/api/users/me', headers=headers)

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['result'] is True
    assert json_data['user']['followers'] == []
    assert json_data['user']['following'] == []
