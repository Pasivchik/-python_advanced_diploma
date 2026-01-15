import logging
import mimetypes
import os

from flasgger import Swagger
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from psycopg2.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from .models import DATABASE_URL, Like, Media, Subscribe, Tweet, User, db

logger = logging.getLogger()


app = Flask(__name__, static_folder="static", template_folder="templates")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["SWAGGER"] = {
    "title": "Twitter API",
    "uiversion": 3,
    "specs_route": "/api/docs/",
    "openapi": "3.0.2",
}

swagger = Swagger(app)

db.init_app(app)

initial_db = False


@app.before_request
def before_request_func():
    global initial_db
    if not initial_db:
        db.create_all()

        test_user = (
            db.session.query(User).filter(User.api_key == "test").one_or_none()
        )

        if not test_user:
            test_user = User(name="test", api_key="test")

            db.session.add(test_user)
            db.session.commit()

        test_user_two = (
            db.session.query(User)
            .filter(User.api_key == "test_two")
            .one_or_none()
        )

        if not test_user_two:
            test_user_two = User(name="test_two", api_key="test_two")

            db.session.add(test_user_two)
            db.session.commit()

        initial_db = True


@app.route("/")
def homepage():
    return render_template("index.html")


@app.route("/js/<path:file_name>")
def serve_js(file_name):
    return redirect(url_for("static", filename=f"js/{file_name}"))


@app.route("/css/<path:file_name>")
def serve_css(file_name):
    return redirect(url_for("static", filename=f"css/{file_name}"))


@app.route("/app/static/media/<path:file_name>")
def get_media_data(file_name):
    try:
        file_path = os.path.join("app/static/media", file_name)
        abs_file_path = os.path.abspath(file_path)

        if not os.path.exists(abs_file_path):
            return (
                jsonify(
                    {
                        "result": False,
                        "error_type": "FileNotFoundError",
                        "error_message": f"File {file_name} not found",
                    }
                ),
                404,
            )

        mime_type, _ = mimetypes.guess_type(abs_file_path)

        return (
            send_file(abs_file_path, mimetype=mime_type, as_attachment=False),
            200,
        )

    except Exception as exc:
        logger.error(
            f'"result": False, '
            f'"error_type": {str(type(exc).__name__)}, '
            f'"error_message": {str(exc)}'
        )
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": str(type(exc).__name__),
                    "error_message": str(exc),
                }
            ),
            500,
        )


@app.route("/api/tweets", methods=["POST"])
def create_tweet():
    """
    Создание нового твита
    ---
    tags:
      - Твиты
    summary: Создать новый твит
    description: Создает новый твит для авторизованного пользователя
     с возможностью прикрепления медиафайлов
    parameters:
      - name: API_KEY
        in: header
        type: string
        required: true
        description: API ключ пользователя для авторизации
        example: "550e8400-e29b-41d4-a716-446655440000"
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - tweet_data
          properties:
            tweet_data:
              type: string
              description: Текст твита
              example: "Это мой первый твит!"
            tweet_media_ids:
              type: array
              description: Список ID медиафайлов для прикрепления к твиту
              items:
                type: integer
              example: [1, 2, 3]
    responses:
      201:
        description: Твит успешно создан
        schema:
          type: object
          properties:
            result:
              type: boolean
              example: true
            tweet_id:
              type: integer
              description: ID созданного твита
              example: 42
      400:
        description: Неверные входные данные
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Не удалось получить текст твита"
      401:
        description: Ошибка авторизации
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Не удалось авторизовать пользователя"
      500:
        description: Внутренняя ошибка сервера
        schema:
          type: object
          properties:
            result:
              type: boolean
              example: false
            error_type:
              type: string
              example: "IntegrityError"
            error_message:
              type: string
              example: "Один или несколько медиафайлов не найдены"
    """
    try:
        api_key = request.environ.get("HTTP_API_KEY")
        tweet_data = request.json.get("tweet_data")

        if not tweet_data:
            return jsonify({"error": "Не удалось получить текст твита"}), 400

        tweet_media_ids = request.json.get("tweet_media_ids")

        user = (
            db.session.query(User).filter(User.api_key == api_key)
        ).one_or_none()

        if not user:
            return jsonify(message="Не удалось авторизовать пользователя"), 401

        new_tweet = Tweet(tweet_data=tweet_data, user_id=user.id)

        db.session.add(new_tweet)
        db.session.flush()

        if tweet_media_ids:
            media_items = (
                db.session.query(Media)
                .filter(Media.id.in_(tweet_media_ids))
                .all()
            )

            if len(media_items) != len(tweet_media_ids):
                db.session.rollback()
                return (
                    jsonify(
                        {"error": "Один или несколько медиафайлов не найдены"}
                    ),
                    500,
                )

            new_tweet.medias.extend(media_items)

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(
            f'"result": False, '
            f'"error_type": {str(type(exc).__name__)}, '
            f'"error_message": {str(exc)}'
        )
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": str(type(exc).__name__),
                    "error_message": str(exc),
                }
            ),
            500,
        )

    return jsonify({"result": True, "tweet_id": new_tweet.id}), 201


@app.route("/api/medias", methods=["POST"])
def download_files_from_tweets():
    """
    Загрузка медиафайлов
    ---
    tags:
      - Медиафайлы
    summary: Загрузить медиафайл
    description: |
      Загружает медиафайл на сервер.
      Если файл с таким именем уже существует,
      возвращает ID существующего файла.
      Поддерживает загрузку изображений, видео и других медиафайлов.
    consumes:
      - multipart/form-data
    produces:
      - application/json
    parameters:
      - name: file
        in: formData
        type: file
        required: true
        description: Медиафайл для загрузки
    responses:
      201:
        description: Файл успешно загружен или уже существует
        schema:
          type: object
          properties:
            result:
              type: boolean
              example: true
            media_id:
              type: integer
              description: ID медиафайла в системе
              example: 15
      400:
        description: Неверные входные данные
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Файл не выбран"
      500:
        description: Внутренняя ошибка сервера
        schema:
          type: object
          properties:
            result:
              type: boolean
              example: false
            error_type:
              type: string
              example: "DatabaseError"
            error_message:
              type: string
              example: "Ошибка при сохранении в базу данных"
    """
    try:
        media = request.files.values()

        if not media:
            return jsonify(error="Файл не выбран"), 400

        has_valid_file = False
        for i_media in media:
            if i_media.filename == "":
                continue

            has_valid_file = True
            find_media = (
                db.session.query(Media)
                .filter(Media.file_name == i_media.filename)
                .one_or_none()
            )

            if not find_media:
                if not os.path.exists("app/static/media"):
                    os.makedirs("app/static/media")

                file_path = f"app/static/media/{i_media.filename}"
                i_media.save(file_path)

                new_media = Media(
                    file_name=i_media.filename, file_path=file_path
                )

                db.session.add(new_media)
                db.session.commit()

                return jsonify({"result": True, "media_id": new_media.id}), 201

            return jsonify({"result": True, "media_id": find_media.id}), 201

        if not has_valid_file:
            return jsonify(error="Файл не выбран"), 400

    except Exception as exc:
        db.session.rollback()
        logger.error(
            f'"result": False, '
            f'"error_type": {str(type(exc).__name__)}, '
            f'"error_message": {str(exc)}'
        )
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": str(type(exc).__name__),
                    "error_message": str(exc),
                }
            ),
            500,
        )


@app.route("/api/tweets/<int:tweet_id>", methods=["DELETE"])
def delete_tweet(tweet_id):
    """
    Удаление твита
    ---
    tags:
      - Твиты
    summary: Удалить твит
    description: |
      Удаляет твит по его ID.
      Твит может удалить только его автор.
      Операция необратима - все связанные данные будут удалены.
    parameters:
      - name: tweet_id
        in: path
        type: integer
        required: true
        description: ID твита для удаления
        example: 42
      - name: API_KEY
        in: header
        type: string
        required: true
        description: API ключ пользователя для авторизации
        example: "550e8400-e29b-41d4-a716-446655440000"
    responses:
      200:
        description: Твит успешно удален
        schema:
            type: object
            properties:
                result:
                    type: boolean
                    example: true
      401:
        description: Ошибка авторизации
        schema:
          type: object
          properties:
            errors:
              type: string
              example: "Такого пользователя не существует"
      403:
        description: Запрещено
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Пост не принадлежит вам"
      404:
        description: Твит не найден
        schema:
          type: object
          properties:
            errors:
              type: string
              example: "Такого твита не существует"
      500:
        description: Внутренняя ошибка сервера
        schema:
          type: object
          properties:
            result:
              type: boolean
              example: false
            error_type:
              type: string
              example: "DatabaseError"
            error_message:
              type: string
              example: "Ошибка при удалении из базы данных"
    """
    try:
        api_key = request.environ.get("HTTP_API_KEY")

        tweet = (
            db.session.query(Tweet).filter(Tweet.id == tweet_id).one_or_none()
        )

        if not tweet:
            return jsonify(errors="Такого твита не существует"), 404

        user = (
            db.session.query(User)
            .filter(User.api_key == api_key)
            .one_or_none()
        )

        if not user:
            return jsonify(errors="Такого пользователя не существует"), 401

        if tweet.user_id != user.id:
            return jsonify(error="Пост не принадлежит вам"), 403

        db.session.delete(tweet)
        db.session.commit()

    except Exception as exc:
        db.session.rollback()
        logger.error(
            f'"result": False, '
            f'"error_type": {str(type(exc).__name__)}, '
            f'"error_message": {str(exc)}'
        )
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": str(type(exc).__name__),
                    "error_message": str(exc),
                }
            ),
            500,
        )

    return jsonify(result=True), 200


@app.route("/api/tweets/<int:tweet_id>/likes", methods=["POST"])
def create_like(tweet_id):
    """
    Добавление лайка к твиту
    ---
    tags:
      - Лайки
    summary: Поставить лайк твиту
    description: |
      Добавляет лайк от текущего пользователя к указанному твиту.
      Пользователь может поставить только один лайк на один твит.
      Если лайк уже существует, операция вернет ошибку.
    parameters:
      - name: tweet_id
        in: path
        type: integer
        required: true
        description: ID твита для добавления лайка
        example: 42
      - name: API_KEY
        in: header
        type: string
        required: true
        description: API ключ пользователя для авторизации
        example: "550e8400-e29b-41d4-a716-446655440000"
    responses:
      201:
        description: Лайк успешно добавлен
        schema:
          type: object
          properties:
            result:
              type: boolean
              example: true
      401:
        description: Ошибка авторизации
        schema:
          type: object
          properties:
            errors:
              type: string
              example: "Такого пользователя не существует"
      500:
        description: Внутренняя ошибка сервера
        schema:
          type: object
          properties:
            result:
              type: boolean
              example: false
            error_type:
              type: string
              example: "DatabaseError"
            error_message:
              type: string
              example: "Ошибка при добавлении лайка"
    """
    try:
        api_key = request.environ.get("HTTP_API_KEY")

        user = (
            db.session.query(User)
            .filter(User.api_key == api_key)
            .one_or_none()
        )

        if not user:
            return jsonify(errors="Такого пользователя не существует"), 401

        new_like = Like(tweet_id=tweet_id, user_id=user.id)

        db.session.add(new_like)
        db.session.commit()

    except Exception as exc:
        db.session.rollback()
        logger.error(
            f'"result": False, '
            f'"error_type": {str(type(exc).__name__)}, '
            f'"error_message": {str(exc)}'
        )
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": str(type(exc).__name__),
                    "error_message": str(exc),
                }
            ),
            500,
        )

    return jsonify(result=True), 201


@app.route("/api/tweets/<int:like_id>/likes", methods=["DELETE"])
def delete_like(like_id):
    """
    Удаление лайка
    ---
    tags:
      - Лайки
    summary: Удалить лайк
    description: |
      Удаляет лайк по его ID.
      Лайк может удалить только пользователь, который его поставил.
      Операция необратима.
    parameters:
      - name: like_id
        in: path
        type: integer
        required: true
        description: ID лайка для удаления
        example: 15
      - name: API_KEY
        in: header
        type: string
        required: true
        description: API ключ пользователя для авторизации
        example: "550e8400-e29b-41d4-a716-446655440000"
    responses:
      200:
        description: Лайк успешно удален
      401:
        description: Ошибка авторизации
        schema:
          type: object
          properties:
            errors:
              type: string
              example: "Такого пользователя не существует"
      403:
        description: Запрещено
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Лайк не принадлежит вам"
      404:
        description: Лайк не найден
        schema:
          type: object
          properties:
            errors:
              type: string
              example: "Такого лайка не существует"
      500:
        description: Внутренняя ошибка сервера
        schema:
          type: object
          properties:
            result:
              type: boolean
              example: false
            error_type:
              type: string
              example: "DatabaseError"
            error_message:
              type: string
              example: "Ошибка при удалении лайка"
    """
    try:
        api_key = request.environ.get("HTTP_API_KEY")

        like = db.session.query(Like).filter(Like.id == like_id).one_or_none()

        if not like:
            return jsonify(errors="Такого лайка не существует"), 404

        user = (
            db.session.query(User)
            .filter(User.api_key == api_key)
            .one_or_none()
        )

        if not user:
            return jsonify(errors="Такого пользователя не существует"), 401

        if like.user_id != user.id:
            return jsonify(error="Лайк не принадлежит вам"), 403

        db.session.delete(like)
        db.session.commit()

    except Exception as exc:
        db.session.rollback()
        logger.error(
            f'"result": False, '
            f'"error_type": {str(type(exc).__name__)}, '
            f'"error_message": {str(exc)}'
        )
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": str(type(exc).__name__),
                    "error_message": str(exc),
                }
            ),
            500,
        )

    return jsonify(result=True), 200


@app.route("/api/users/<int:target_id>/follow", methods=["POST"])
def create_subscribe(target_id):
    """
    Создание подписки на пользователя
    ---
    tags:
      - Подписки
    summary: Подписаться на пользователя
    description: |
      Создает подписку текущего пользователя на указанного пользователя.
      Пользователь не может подписаться на самого себя.
      На одного пользователя можно подписаться только один раз.
    parameters:
      - name: target_id
        in: path
        type: integer
        required: true
        description: ID пользователя, на которого нужно подписаться
        example: 5
      - name: API_KEY
        in: header
        type: string
        required: true
        description: API ключ пользователя для авторизации
        example: "550e8400-e29b-41d4-a716-446655440000"
    responses:
      201:
        description: Подписка успешно создана
        schema:
          type: object
          properties:
            result:
              type: boolean
              example: true
      400:
        description: Неверный запрос (попытка подписаться на себя)
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Нельзя подписаться на самого себя"
      401:
        description: Ошибка авторизации
        schema:
          type: object
          properties:
            errors:
              type: string
              example: "Такого пользователя не существует"
      404:
        description: Целевой пользователь не найден
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Целевой пользователь не найден"
      409:
        description: Конфликт (уже подписаны)
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Вы уже подписаны на этого пользователя"
      500:
        description: Внутренняя ошибка сервера
        schema:
          type: object
          properties:
            result:
              type: boolean
              example: false
            error_type:
              type: string
              example: "IntegrityError"
            error_message:
              type: string
              example: "Ошибка при создании подписки"
    """
    try:
        api_key = request.environ.get("HTTP_API_KEY")

        user = (
            db.session.query(User)
            .filter(User.api_key == api_key)
            .one_or_none()
        )

        if not user:
            return jsonify(errors="Такого пользователя не существует"), 401

        if target_id == user.id:
            return jsonify(errors="Нельзя подписаться на самого себя"), 400

        new_subscribe = Subscribe(subscriber_id=user.id, target_id=target_id)

        db.session.add(new_subscribe)
        db.session.commit()

    except IntegrityError as exc:
        db.session.rollback()

        if isinstance(exc.orig, UniqueViolation):
            return (
                jsonify({"error": "Вы уже подписаны на этого пользователя"}),
                409,
            )

        logger.error(
            f'"result": False, '
            f'"error_type": {str(type(exc).__name__)}, '
            f'"error_message": {str(exc)}'
        )
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": str(type(exc).__name__),
                    "error_message": str(exc),
                }
            ),
            500,
        )

    except Exception as exc:
        db.session.rollback()
        logger.error(
            f'"result": False, '
            f'"error_type": {str(type(exc).__name__)}, '
            f'"error_message": {str(exc)}'
        )
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": str(type(exc).__name__),
                    "error_message": str(exc),
                }
            ),
            500,
        )

    return jsonify(result=True), 201


@app.route("/api/users/<int:user_id>/follow", methods=["DELETE"])
def delete_subscribe(user_id):
    """
    Удаление подписки
    ---
    tags:
      - Подписки
    summary: Отписаться от пользователя
    description: |
      Удаляет подписку по ее ID.
      Подписку может удалить только пользователь,
      который ее создал (подписчик).
      Операция необратима.
    parameters:
      - name: subscribe_id
        in: path
        type: integer
        required: true
        description: ID подписки для удаления
        example: 15
      - name: API_KEY
        in: header
        type: string
        required: true
        description: API ключ пользователя для авторизации
        example: "550e8400-e29b-41d4-a716-446655440000"
    responses:
      204:
        description: Подписка успешно удалена
      401:
        description: Ошибка авторизации
        schema:
          type: object
          properties:
            errors:
              type: string
              example: "Такого пользователя не существует"
      403:
        description: Запрещено
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Подписка не принадлежит вам"
      404:
        description: Подписка не найдена
        schema:
          type: object
          properties:
            errors:
              type: string
              example: "Такой подписки не существует"
      500:
        description: Внутренняя ошибка сервера
        schema:
          type: object
          properties:
            result:
              type: boolean
              example: false
            error_type:
              type: string
              example: "DatabaseError"
            error_message:
              type: string
              example: "Ошибка при удалении подписки"
    """
    try:
        api_key = request.environ.get("HTTP_API_KEY")

        user = (
            db.session.query(User)
            .filter(User.api_key == api_key)
            .one_or_none()
        )

        if not user:
            return jsonify(errors="Такого пользователя не существует"), 401

        subscribe = (
            db.session.query(Subscribe)
            .filter(
                Subscribe.target_id == user_id,
                Subscribe.subscriber_id == user.id,
            )
            .one_or_none()
        )

        if not subscribe:
            return jsonify(errors="Такой подписки не существует"), 404

        if subscribe.subscriber_id != user.id:
            return jsonify(error="Подписка не принадлежит вам"), 403

        db.session.delete(subscribe)
        db.session.commit()

        return jsonify(result=True), 204

    except Exception as exc:
        db.session.rollback()
        logger.error(
            f'"result": False, '
            f'"error_type": {str(type(exc).__name__)}, '
            f'"error_message": {str(exc)}'
        )
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": str(type(exc).__name__),
                    "error_message": str(exc),
                }
            ),
            500,
        )


@app.route("/api/tweets", methods=["GET"])
def get_tweets():
    """
    Получение списка твитов
    ---
    tags:
      - Твиты
    summary: Получить все твиты
    description: |
      Возвращает список всех твитов с полной информацией.
      Включает данные авторов, медиавложения и список лайков.
      Твиты возвращаются в обратном хронологическом порядке
      (сначала самые новые).
    produces:
      - application/json
    responses:
      200:
        description: Список твитов успешно получен
        schema:
          type: object
          properties:
            result:
              type: boolean
              example: true
            tweets:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                    description: ID твита
                    example: 42
                  content:
                    type: string
                    description: Текст твита
                    example: "Это мой первый твит!"
                  attachments:
                    type: array
                    description: Список путей к медиавложениям
                    items:
                      type: string
                    example: [
                      "static/media/image1.jpg",
                      "static/media/image2.png"
                    ]
                  author:
                    type: object
                    description: Информация об авторе твита
                    properties:
                      id:
                        type: integer
                        example: 1
                      name:
                        type: string
                        example: "Иван Иванов"
                  likes:
                    type: array
                    description: Список пользователей, поставивших лайк
                    items:
                      type: object
                      properties:
                        user_id:
                          type: integer
                          example: 2
                        name:
                          type: string
                          example: "Петр Петров"
      500:
        description: Внутренняя ошибка сервера
        schema:
          type: object
          properties:
            result:
              type: boolean
              example: false
            error_type:
              type: string
              example: "DatabaseError"
            error_message:
              type: string
              example: "Ошибка при получении данных из базы"
    """
    try:
        tweets = (
            db.session.query(Tweet)
            .options(
                joinedload(Tweet.medias),
                joinedload(Tweet.users),
                joinedload(Tweet.likes).joinedload(Like.users),
            )
            .all()
        )

        return_datas = []

        for i_tweet in tweets:
            attachments = []
            for media in i_tweet.medias:
                attachments.append(media.file_path)

            author_data = None
            if i_tweet.users:
                author_data = {
                    "id": i_tweet.users.id,
                    "name": i_tweet.users.name,
                }

            likes_data = []
            for like in i_tweet.likes:
                if like.users:
                    likes_data.append(
                        {
                            "user_id": like.user_id,
                            "name": like.users.name,
                        }
                    )

            temp_data = {
                "id": i_tweet.id,
                "content": i_tweet.tweet_data,
                "attachments": attachments,
                "author": author_data,
                "likes": likes_data,
            }

            return_datas.append(temp_data)

        return_datas = list(reversed(return_datas))

    except Exception as exc:
        logger.error(
            f'"result": False, '
            f'"error_type": {str(type(exc).__name__)}, '
            f'"error_message": {str(exc)}'
        )
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": str(type(exc).__name__),
                    "error_message": str(exc),
                }
            ),
            500,
        )

    return jsonify({"result": True, "tweets": return_datas}), 200


@app.route("/api/users/me", methods=["GET"])
def get_my_account_info():
    """
    Получение информации о текущем пользователе
    ---
    tags:
      - Пользователи
    summary: Получить информацию о текущем пользователе
    description: |
      Возвращает подробную информацию
       о текущем аутентифицированном пользователе.
      Включает информацию о подписчиках (фолловерах) и пользователях,
      на которых подписан текущий пользователь.
      Требует авторизации через API ключ.
    parameters:
      - name: API_KEY
        in: header
        type: string
        required: true
        description: API ключ пользователя для авторизации
        example: "550e8400-e29b-41d4-a716-446655440000"
    responses:
      200:
        description: Информация о пользователе успешно получена
        schema:
          type: object
          properties:
            result:
              type: boolean
              example: true
            user:
              type: object
              properties:
                id:
                  type: integer
                  description: ID пользователя
                  example: 1
                name:
                  type: string
                  description: Имя пользователя
                  example: "Иван Иванов"
                followers:
                  type: array
                  description: Список подписчиков
                  (пользователей, которые подписаны на текущего пользователя)
                  items:
                    type: object
                    properties:
                      id:
                        type: integer
                        example: 2
                      name:
                        type: string
                        example: "Петр Петров"
                following:
                  type: array
                  description: Список подписок
                  (пользователей, на которых подписан текущий пользователь)
                  items:
                    type: object
                    properties:
                      id:
                        type: integer
                        example: 3
                      name:
                        type: string
                        example: "Анна Смирнова"
      401:
        description: Ошибка авторизации
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Пользователь не найден"
      500:
        description: Внутренняя ошибка сервера
        schema:
          type: object
          properties:
            result:
              type: boolean
              example: false
            error_type:
              type: string
              example: "DatabaseError"
            error_message:
              type: string
              example: "Ошибка при получении данных пользователя"
    """
    try:
        api_key = request.environ.get("HTTP_API_KEY")

        user = (
            db.session.query(User)
            .options(
                joinedload(User.subscribers).joinedload(Subscribe.subscribers),
                joinedload(User.targets).joinedload(Subscribe.targets),
            )
            .filter(User.api_key == api_key)
            .one_or_none()
        )

        if not user:
            return jsonify(error="Пользователь не найден"), 401

        followers = []
        for i_subscriber in user.subscribers:
            follower_user = (
                db.session.query(User)
                .filter(User.id == i_subscriber.target_id)
                .first()
            )

            follower_data = {
                "id": follower_user.id,
                "name": follower_user.name,
            }

            followers.append(follower_data)

        following = []
        for i_target in user.targets:
            target_user = (
                db.session.query(User)
                .filter(User.id == i_target.subscriber_id)
                .first()
            )

            following_data = {"id": target_user.id, "name": target_user.name}
            following.append(following_data)

        return_data = {
            "id": user.id,
            "name": user.name,
            "followers": list(reversed(followers)),
            "following": list(reversed(following)),
        }

        return jsonify({"result": True, "user": return_data}), 200

    except Exception as exc:
        logger.error(
            f'"result": False, '
            f'"error_type": {str(type(exc).__name__)}, '
            f'"error_message": {str(exc)}'
        )
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": str(type(exc).__name__),
                    "error_message": str(exc),
                }
            ),
            500,
        )


@app.route("/api/users/<int:user_id>", methods=["GET"])
def get_account_info_by_id(user_id):
    """
    Получение информации о пользователе по ID
    ---
    tags:
      - Пользователи
    summary: Получить информацию о пользователе
    description: |
      Возвращает подробную информацию о пользователе по его ID.
      Включает информацию о подписчиках (фолловерах) и пользователях,
      на которых подписан указанный пользователь.
      Не требует авторизации - информация публичная.
    parameters:
      - name: user_id
        in: path
        type: integer
        required: true
        description: ID пользователя
        example: 1
    responses:
      200:
        description: Информация о пользователе успешно получена
        schema:
          type: object
          properties:
            result:
              type: boolean
              example: true
            user:
              type: object
              properties:
                id:
                  type: integer
                  description: ID пользователя
                  example: 1
                name:
                  type: string
                  description: Имя пользователя
                  example: "Иван Иванов"
                followers:
                  type: array
                  description: Список подписчиков пользователя
                  items:
                    type: object
                    properties:
                      id:
                        type: integer
                        example: 2
                      name:
                        type: string
                        example: "Петр Петров"
                following:
                  type: array
                  description: Список подписок пользователя
                  items:
                    type: object
                    properties:
                      id:
                        type: integer
                        example: 3
                      name:
                        type: string
                        example: "Анна Смирнова"
      404:
        description: Пользователь не найден
        schema:
          type: object
          properties:
            errors:
              type: string
              example: "Пользователь не найден"
      500:
        description: Внутренняя ошибка сервера
        schema:
          type: object
          properties:
            result:
              type: boolean
              example: false
            error_type:
              type: string
              example: "DatabaseError"
            error_message:
              type: string
              example: "Ошибка при получении данных пользователя"
    """
    try:
        user = (
            db.session.query(User)
            .options(
                joinedload(User.subscribers).joinedload(Subscribe.subscribers),
                joinedload(User.targets).joinedload(Subscribe.targets),
            )
            .filter(User.id == user_id)
            .one_or_none()
        )

        if not user:
            return jsonify(errors="Пользователь не найден"), 404

        following = []
        for i_subscriber in user.subscribers:
            following_user = (
                db.session.query(User)
                .filter(User.id == i_subscriber.target_id)
                .first()
            )

            following_data = {
                "id": following_user.id,
                "name": following_user.name,
            }

            following.append(following_data)

        followers = []
        for i_target in user.targets:
            target_user = (
                db.session.query(User)
                .filter(User.id == i_target.subscriber_id)
                .first()
            )

            followers_data = {"id": target_user.id, "name": target_user.name}
            followers.append(followers_data)

        return_data = {
            "id": user.id,
            "name": user.name,
            "followers": list(reversed(followers)),
            "following": list(reversed(following)),
        }

    except Exception as exc:
        logger.error(
            f'"result": False, '
            f'"error_type": {str(type(exc).__name__)}, '
            f'"error_message": {str(exc)}'
        )

        return (
            jsonify(
                {
                    "result": False,
                    "error_type": str(type(exc).__name__),
                    "error_message": str(exc),
                }
            ),
            500,
        )

    return jsonify({"result": True, "user": return_data}), 200
