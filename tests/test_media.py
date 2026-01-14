import io
from unittest.mock import patch
from werkzeug.datastructures import FileStorage
from app.models import Media


def test_no_files_provided(client):
    """Тест: нет переданных файлов"""
    response = client.post('/api/medias')

    assert response.status_code == 400
    assert response.json == {'error': 'Файл не выбран'}


def test_successful_file_upload_new_media(client, db):
    """Тест: успешная загрузка нового файла"""
    file_content = b'test file content'
    file = FileStorage(
        stream=io.BytesIO(file_content),
        filename='test.jpg',
        content_type='image/jpeg'
    )

    data = {'media': file}

    media_count_before = db.session.query(Media).count()

    with patch('werkzeug.datastructures.FileStorage.save') as mock_save:
        response = client.post('/api/medias', data=data)

        assert response.status_code == 201
        json_data = response.get_json()
        assert json_data['result'] is True
        assert 'media_id' in json_data

        mock_save.assert_called_once()
        call_args = mock_save.call_args[0][0]
        assert call_args.startswith('app/static/media/test.jpg')

        media_count_after = db.session.query(Media).count()
        assert media_count_after == media_count_before + 1

        new_media = db.session.query(Media).filter_by(file_name='test.jpg').first()
        assert new_media is not None
        assert new_media.file_path.startswith('app/static/media/test.jpg')
        assert new_media.id == json_data['media_id']


def test_successful_file_upload_existing_media(client, db):
    """Тест: загрузка уже существующего файла"""
    existing_media = Media(
        file_name='existing.jpg',
        file_path='static/media/existing.jpg'
    )
    db.session.add(existing_media)
    db.session.commit()
    existing_id = existing_media.id

    file_content = b'test file content'
    file = FileStorage(
        stream=io.BytesIO(file_content),
        filename='existing.jpg',
        content_type='image/jpeg'
    )

    data = {'media': file}

    with patch('werkzeug.datastructures.FileStorage.save') as mock_save:
        response = client.post('/api/medias', data=data)

        assert response.status_code == 201
        json_data = response.get_json()
        assert json_data['result'] is True
        assert json_data['media_id'] == existing_id

        mock_save.assert_not_called()


def test_file_upload_empty_filename(client):
    """Тест: загрузка файла с пустым именем"""
    file_content = b'test file content'
    file = FileStorage(
        stream=io.BytesIO(file_content),
        filename='',
        content_type='image/jpeg'
    )

    data = {'media': file}

    response = client.post('/api/medias', data=data)

    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['error'] == 'Файл не выбран'


def test_file_upload_database_error(client, db):
    """Тест: ошибка при сохранении в базу данных"""
    file_content = b'test file content'
    file = FileStorage(
        stream=io.BytesIO(file_content),
        filename='error.jpg',
        content_type='image/jpeg'
    )

    data = {'media': file}

    with patch('werkzeug.datastructures.FileStorage.save'):
        with patch.object(db.session, 'commit', side_effect=Exception('Database error')):
            response = client.post('/api/medias', data=data)

            assert response.status_code == 500
            json_data = response.get_json()
            assert json_data['result'] is False
            assert 'error_type' in json_data
            assert 'error_message' in json_data