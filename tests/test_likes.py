from app.models import Tweet, User, Like


def test_create_like_success(client, db):
    """Тест: успешное добавление лайка к твиту"""
    user = User.query.filter_by(api_key='test').first()
    tweet = Tweet(tweet_data='Тестовый твит для лайка', user_id=user.id)
    db.session.add(tweet)
    db.session.commit()

    headers = {
        'API_KEY': 'test_two'
    }

    response = client.post(f'/api/tweets/{tweet.id}/likes', headers=headers)

    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data['result'] is True

    user_two = User.query.filter_by(api_key='test_two').first()

    like = Like.query.filter_by(tweet_id=tweet.id, user_id=user_two.id).first()
    assert like is not None

    user_liker = User.query.filter_by(api_key='test_two').first()
    assert like.user_id == user_liker.id


def test_create_like_own_tweet_success(client, db):
    """Тест: успешное добавление лайка к своему твиту"""
    user = User.query.filter_by(api_key='test').first()
    tweet = Tweet(tweet_data='Свой твит', user_id=user.id)
    db.session.add(tweet)
    db.session.commit()

    headers = {
        'API_KEY': 'test'
    }

    response = client.post(f'/api/tweets/{tweet.id}/likes', headers=headers)

    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data['result'] is True


def test_create_like_tweet_not_found(client, db):
    """Тест: попытка поставить лайк несуществующему твиту"""
    headers = {
        'API_KEY': 'test'
    }

    response = client.post('/api/tweets/999/likes', headers=headers)

    assert response.status_code in [404, 500]

    if response.status_code == 500:
        json_data = response.get_json()
        assert json_data['result'] is False
        assert 'error_type' in json_data


def test_create_like_no_api_key(client, db):
    """Тест: попытка поставить лайк без API ключа"""
    user = User.query.filter_by(api_key='test').first()
    tweet = Tweet(tweet_data='Твит', user_id=user.id)
    db.session.add(tweet)
    db.session.commit()

    response = client.post(f'/api/tweets/{tweet.id}/likes')

    assert response.status_code == 401
    json_data = response.get_json()
    assert json_data['errors'] == 'Такого пользователя не существует'


def test_create_like_invalid_api_key(client, db):
    """Тест: попытка поставить лайк с неверным API ключом"""
    user = User.query.filter_by(api_key='test').first()
    tweet = Tweet(tweet_data='Твит', user_id=user.id)
    db.session.add(tweet)
    db.session.commit()

    headers = {
        'API_KEY': 'invalid_key'
    }

    response = client.post(f'/api/tweets/{tweet.id}/likes', headers=headers)

    assert response.status_code == 401


def test_create_like_duplicate(client, db):
    """Тест: попытка поставить второй лайк на тот же твит"""
    user = User.query.filter_by(api_key='test').first()
    user_liker = User.query.filter_by(api_key='test_two').first()

    tweet = Tweet(tweet_data='Твит', user_id=user.id)
    db.session.add(tweet)
    db.session.commit()

    like = Like(tweet_id=tweet.id, user_id=user_liker.id)
    db.session.add(like)
    db.session.commit()

    headers = {
        'API_KEY': 'test_two'
    }

    response = client.post(f'/api/tweets/{tweet.id}/likes', headers=headers)

    assert response.status_code == 500
    json_data = response.get_json()
    assert json_data['result'] is False
    assert 'error_type' in json_data


def test_create_like_after_delete(client, db):
    """Тест: добавление лайка после удаления предыдущего"""
    user = User.query.filter_by(api_key='test').first()
    user_liker = User.query.filter_by(api_key='test_two').first()

    tweet = Tweet(tweet_data='Твит', user_id=user.id)
    db.session.add(tweet)
    db.session.commit()

    like = Like(tweet_id=tweet.id, user_id=user_liker.id)
    db.session.add(like)
    db.session.commit()
    like_id = like.id

    delete_headers = {'API_KEY': 'test_two'}
    client.delete(f'/api/tweets/{like_id}/likes', headers=delete_headers)

    create_headers = {'API_KEY': 'test_two'}
    response = client.post(f'/api/tweets/{tweet.id}/likes', headers=create_headers)

    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data['result'] is True

    likes = Like.query.filter_by(tweet_id=tweet.id, user_id=user_liker.id).all()
    assert len(likes) == 1
    assert likes[0].id != like_id


def test_delete_like_success(client, db):
    """Тест: успешное удаление своего лайка"""
    user = User.query.filter_by(api_key='test').first()
    user_liker = User.query.filter_by(api_key='test_two').first()

    tweet = Tweet(tweet_data='Твит', user_id=user.id)
    db.session.add(tweet)
    db.session.commit()

    like = Like(tweet_id=tweet.id, user_id=user_liker.id)
    db.session.add(like)
    db.session.commit()

    headers = {
        'API_KEY': 'test_two'
    }

    response = client.delete(f'/api/tweets/{like.id}/likes', headers=headers)

    assert response.status_code == 200

    deleted_like = db.session.get(Like, like.id)
    assert deleted_like is None


def test_delete_like_not_found(client):
    """Тест: попытка удалить несуществующий лайк"""
    headers = {
        'API_KEY': 'test'
    }

    response = client.delete('/api/tweets/999/likes', headers=headers)

    assert response.status_code == 404
    json_data = response.get_json()
    assert json_data['errors'] == 'Такого лайка не существует'


def test_delete_like_no_api_key(client, db):
    """Тест: попытка удалить лайк без API ключа"""
    user = User.query.filter_by(api_key='test').first()
    tweet = Tweet(tweet_data='Твит', user_id=user.id)
    like = Like(tweet_id=tweet.id, user_id=user.id)

    db.session.add_all([tweet, like])
    db.session.commit()

    response = client.delete(f'/api/tweets/{like.id}/likes')

    assert response.status_code == 401


def test_delete_like_forbidden(client, db):
    """Тест: попытка удалить чужой лайк"""
    user1 = User.query.filter_by(api_key='test').first()
    user2 = User.query.filter_by(api_key='test_two').first()

    tweet = Tweet(tweet_data='Твит', user_id=user1.id)
    like = Like(tweet_id=tweet.id, user_id=user2.id)

    db.session.add_all([tweet, like])
    db.session.commit()

    headers = {
        'API_KEY': 'test'
    }

    response = client.delete(f'/api/tweets/{like.id}/likes', headers=headers)

    assert response.status_code == 403
    json_data = response.get_json()
    assert json_data['error'] == 'Лайк не принадлежит вам'

    assert db.session.get(Like, like.id) is not None


def test_delete_like_invalid_api_key(client, db):
    """Тест: попытка удалить лайк с неверным API ключом"""
    user = User.query.filter_by(api_key='test').first()
    tweet = Tweet(tweet_data='Твит', user_id=user.id)
    like = Like(tweet_id=tweet.id, user_id=user.id)

    db.session.add_all([tweet, like])
    db.session.commit()

    headers = {
        'API_KEY': 'invalid_key'
    }

    response = client.delete(f'/api/tweets/{like.id}/likes', headers=headers)

    assert response.status_code == 401


def test_delete_like_cascade_check(client, db):
    """Тест: удаление лайка и проверка, что твит не удаляется"""
    user = User.query.filter_by(api_key='test').first()
    user_liker = User.query.filter_by(api_key='test_two').first()

    tweet = Tweet(tweet_data='Твит', user_id=user.id)
    like = Like(tweet_id=tweet.id, user_id=user_liker.id)

    db.session.add_all([tweet, like])
    db.session.commit()

    tweet_id = tweet.id
    like_id = like.id

    headers = {'API_KEY': 'test_two'}
    response = client.delete(f'/api/tweets/{like_id}/likes', headers=headers)

    assert response.status_code == 200

    assert db.session.get(Like, like_id) is None

    assert db.session.get(Tweet, tweet_id) is not None


def test_like_full_cycle(client, db):
    """Тест: полный цикл работы с лайком (создание и удаление)"""
    user_author = User.query.filter_by(api_key='test').first()
    user_liker = User.query.filter_by(api_key='test_two').first()

    tweet = Tweet(tweet_data='Твит для полного цикла', user_id=user_author.id)
    db.session.add(tweet)
    db.session.commit()

    like_headers = {'API_KEY': 'test_two'}
    create_response = client.post(f'/api/tweets/{tweet.id}/likes', headers=like_headers)

    assert create_response.status_code == 201

    like = Like.query.filter_by(tweet_id=tweet.id, user_id=user_liker.id).first()
    assert like is not None
    like_id = like.id

    duplicate_response = client.post(f'/api/tweets/{tweet.id}/likes', headers=like_headers)
    assert duplicate_response.status_code == 500

    delete_response = client.delete(f'/api/tweets/{like_id}/likes', headers=like_headers)
    assert delete_response.status_code == 200

    assert db.session.get(Like, like_id) is None

    create_again_response = client.post(f'/api/tweets/{tweet.id}/likes', headers=like_headers)
    assert create_again_response.status_code == 201


def test_delete_already_deleted_like(client, db):
    """Тест: попытка удаления уже удаленного лайка"""
    user = User.query.filter_by(api_key='test').first()
    tweet = Tweet(tweet_data='Твит', user_id=user.id)
    like = Like(tweet_id=tweet.id, user_id=user.id)

    db.session.add_all([tweet, like])
    db.session.commit()

    like_id = like.id

    headers = {'API_KEY': 'test'}
    response1 = client.delete(f'/api/tweets/{like_id}/likes', headers=headers)
    assert response1.status_code == 200

    response2 = client.delete(f'/api/tweets/{like_id}/likes', headers=headers)
    assert response2.status_code == 404
    json_data = response2.get_json()
    assert json_data['errors'] == 'Такого лайка не существует'
