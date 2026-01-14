from app.models import Tweet, User, Media, Like


def test_create_tweet_success_no_media(client, db):
    """Тест: успешное создание твита без медиафайлов"""
    user = User.query.filter_by(api_key='test').first()

    headers = {
        'API_KEY': 'test'
    }

    data = {
        'tweet_data': 'Тестовый твит без медиафайлов'
    }

    response = client.post('/api/tweets', json=data, headers=headers)

    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data['result'] is True
    assert 'tweet_id' in json_data

    tweet = db.session.get(Tweet, json_data['tweet_id'])
    assert tweet is not None
    assert tweet.tweet_data == 'Тестовый твит без медиафайлов'
    assert tweet.user_id == user.id
    assert len(tweet.medias) == 0


def test_create_tweet_success_with_media(client, db):
    """Тест: успешное создание твита с медиафайлами"""
    media1 = Media(file_name='test1.jpg', file_path='static/media/test1.jpg')
    media2 = Media(file_name='test2.png', file_path='static/media/test2.png')
    db.session.add_all([media1, media2])
    db.session.commit()

    headers = {
        'API_KEY': 'test'
    }

    data = {
        'tweet_data': 'Тестовый твит с медиафайлами',
        'tweet_media_ids': [media1.id, media2.id]
    }

    response = client.post('/api/tweets', json=data, headers=headers)

    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data['result'] is True

    tweet = db.session.get(Tweet, json_data['tweet_id'])
    assert tweet is not None
    assert len(tweet.medias) == 2
    assert media1 in tweet.medias
    assert media2 in tweet.medias


def test_create_tweet_no_api_key(client):
    """Тест: создание твита без API ключа"""
    data = {
        'tweet_data': 'Тестовый твит'
    }

    response = client.post('/api/tweets', json=data)

    assert response.status_code == 401
    json_data = response.get_json()
    assert json_data['message'] == 'Не удалось авторизовать пользователя'


def test_create_tweet_invalid_api_key(client):
    """Тест: создание твита с неверным API ключом"""
    headers = {
        'API_KEY': 'invalid_key'
    }

    data = {
        'tweet_data': 'Тестовый твит'
    }

    response = client.post('/api/tweets', json=data, headers=headers)

    assert response.status_code == 401


def test_create_tweet_no_text(client):
    """Тест: создание твита без текста"""
    headers = {
        'API_KEY': 'test'
    }

    data = {
        'tweet_data': ''
    }

    response = client.post('/api/tweets', json=data, headers=headers)

    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['error'] == 'Не удалось получить текст твита'


def test_create_tweet_invalid_media_ids(client, db):
    """Тест: создание твита с несуществующими медиафайлами"""
    headers = {
        'API_KEY': 'test'
    }

    data = {
        'tweet_data': 'Твит с несуществующими медиа',
        'tweet_media_ids': [999, 1000]
    }

    response = client.post('/api/tweets', json=data, headers=headers)

    assert response.status_code == 500
    json_data = response.get_json()
    assert json_data['error'] == 'Один или несколько медиафайлов не найдены'

    tweet_count = Tweet.query.filter_by(tweet_data='Твит с несуществующими медиа').count()
    assert tweet_count == 0


def test_delete_tweet_success(client, db):
    """Тест: успешное удаление своего твита"""
    user = User.query.filter_by(api_key='test').first()
    tweet = Tweet(tweet_data='Твит для удаления', user_id=user.id)
    db.session.add(tweet)
    db.session.commit()
    tweet_id = tweet.id

    headers = {
        'API_KEY': 'test'
    }

    response = client.delete(f'/api/tweets/{tweet_id}', headers=headers)

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['result'] is True

    deleted_tweet = db.session.get(Tweet, tweet_id)
    assert deleted_tweet is None


def test_delete_tweet_not_found(client):
    """Тест: удаление несуществующего твита"""
    headers = {
        'API_KEY': 'test'
    }

    response = client.delete('/api/tweets/999', headers=headers)

    assert response.status_code == 404
    json_data = response.get_json()
    assert json_data['errors'] == 'Такого твита не существует'


def test_delete_tweet_no_api_key(client, db):
    """Тест: удаление твита без API ключа"""
    user = User.query.filter_by(api_key='test').first()
    tweet = Tweet(tweet_data='Твит', user_id=user.id)
    db.session.add(tweet)
    db.session.commit()

    response = client.delete(f'/api/tweets/{tweet.id}')

    assert response.status_code == 401


def test_delete_tweet_forbidden(client, db):
    """Тест: попытка удаления чужого твита"""
    user_test = User.query.filter_by(api_key='test').first()
    tweet = Tweet(tweet_data='Чужой твит', user_id=user_test.id)
    db.session.add(tweet)
    db.session.commit()

    headers = {
        'API_KEY': 'test_two'
    }

    response = client.delete(f'/api/tweets/{tweet.id}', headers=headers)

    assert response.status_code == 403
    json_data = response.get_json()
    assert json_data['error'] == 'Пост не принадлежит вам'

    assert db.session.get(Tweet, tweet.id) is not None


def test_delete_tweet_invalid_api_key(client, db):
    """Тест: удаление твита с неверным API ключом"""
    user = User.query.filter_by(api_key='test').first()
    tweet = Tweet(tweet_data='Твит', user_id=user.id)
    db.session.add(tweet)
    db.session.commit()

    headers = {
        'API_KEY': 'invalid_key'
    }

    response = client.delete(f'/api/tweets/{tweet.id}', headers=headers)

    assert response.status_code == 401


def test_get_tweets_empty(client, db):
    """Тест: получение пустого списка твитов"""
    Tweet.query.delete()
    db.session.commit()

    response = client.get('/api/tweets')

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['result'] is True
    assert json_data['tweets'] == []


from sqlalchemy import text


def test_get_tweets_with_data(client, db):
    """Тест: получение списка твитов с данными"""
    db.session.query(Like).delete()
    db.session.execute(text('DELETE FROM tweet_media'))
    db.session.query(Media).delete()
    db.session.query(Tweet).delete()
    db.session.query(User).filter(~User.api_key.in_(['test', 'test_two'])).delete()
    db.session.commit()

    user1 = User.query.filter_by(api_key='test').first()
    user2 = User.query.filter_by(api_key='test_two').first()

    print(f"DEBUG: User1 ID: {user1.id}, User2 ID: {user2.id}")

    media1 = Media(file_name='img1.jpg', file_path='static/media/img1.jpg')
    media2 = Media(file_name='img2.png', file_path='static/media/img2.png')
    db.session.add_all([media1, media2])
    db.session.flush()

    tweet1 = Tweet(tweet_data='Первый твит', user_id=user1.id)
    tweet2 = Tweet(tweet_data='Второй твит', user_id=user2.id)

    tweet1.medias.append(media1)
    tweet2.medias.append(media2)

    db.session.add_all([tweet1, tweet2])
    db.session.flush()

    like1 = Like(tweet_id=tweet1.id, user_id=user2.id)
    like2 = Like(tweet_id=tweet2.id, user_id=user1.id)

    db.session.add_all([like1, like2])
    db.session.commit()

    response = client.get('/api/tweets')
    json_data = response.get_json()

    assert response.status_code == 200
    assert json_data['result'] is True

    found_tweet1 = None
    found_tweet2 = None

    for tweet in json_data['tweets']:
        if tweet['id'] == tweet1.id:
            found_tweet1 = tweet
        elif tweet['id'] == tweet2.id:
            found_tweet2 = tweet

    assert found_tweet1 is not None
    assert found_tweet2 is not None

    assert found_tweet2['content'] == 'Второй твит'
    assert found_tweet2['attachments'] == ['static/media/img2.png']
    assert found_tweet2['author']['id'] == user2.id
    assert found_tweet2['author']['name'] == 'test_two'
    assert len(found_tweet2['likes']) == 1
    assert found_tweet2['likes'][0]['user_id'] == user1.id
    assert found_tweet2['likes'][0]['name'] == 'test'


def test_get_tweets_various_data(client, db):
    """Тест: получение твитов с различными комбинациями данных"""
    Tweet.query.delete()
    db.session.commit()

    user = User.query.filter_by(api_key='test').first()

    tweet1 = Tweet(tweet_data='Твит без медиа и лайков', user_id=user.id)

    tweet2 = Tweet(tweet_data='Твит только с медиа', user_id=user.id)
    media = Media(file_name='test.jpg', file_path='static/media/test.jpg')
    db.session.add(media)
    tweet2.medias.append(media)

    tweet3 = Tweet(tweet_data='Твит только с лайками', user_id=user.id)
    like = Like(tweet_id=tweet3.id, user_id=user.id)
    db.session.add(like)

    db.session.add_all([tweet1, tweet2, tweet3])
    db.session.commit()

    response = client.get('/api/tweets')

    assert response.status_code == 200
    json_data = response.get_json()
    assert len(json_data['tweets']) == 3

    for tweet in json_data['tweets']:
        assert 'id' in tweet
        assert 'content' in tweet
        assert 'attachments' in tweet
        assert 'author' in tweet
        assert 'likes' in tweet

        assert tweet['author'] is not None
        assert tweet['author']['id'] == user.id
        assert tweet['author']['name'] == 'test'
