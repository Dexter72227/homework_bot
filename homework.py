import logging
import os
import sys
import time
import telegram
import requests
import json
import contextlib
from dotenv import load_dotenv
from telegram import Bot
from http import HTTPStatus


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
fileHandler = logging.FileHandler("bot.log", encoding='utf-8')
streamHandler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
logger.setLevel(logging.DEBUG)
streamHandler.setFormatter(formatter)
fileHandler.setFormatter(formatter)
logger.addHandler(streamHandler)
logger.addHandler(fileHandler)


def check_tokens():
    """Функция проверки наличия токенов."""
    tokens = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
    for token in tokens:
        logger.info(f'Проверка токена {token}')
        if token not in os.environ:
            logger.critical(f'Ошибка: не найден токен {token}')
            return f'Ошибка: не найден токен {token}'
    logger.info('Токены найдены')
    return TELEGRAM_TOKEN or PRACTICUM_TOKEN or TELEGRAM_CHAT_ID


def send_message(bot, message):
    """Функция отправки сообщения в Телеграм."""
    try:
        logger.info("Сообщение отправлено в телеграм")
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError as e:
        logging.error(f'Ошибка при отправке сообщения в Телеграм: {e}')
    else:
        logger.debug(f'В Telegram отправлено сообщение "{message}"')


def get_api_answer(timestamp_now):
    """Функция запроса данных API."""
    timestamp = timestamp_now or int(time.time())
    params = {'from_date': timestamp}
    try:
        logger.info('Запрос к API-сервису')
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise ValueError(
                f'Ошибка при запросе данных API: код {response.status_code}'
            )
        data = response.json()
        if 'error' in data:
            raise json.JSONDecodeError(data['error'], '', 0)
        return {
            'data': data,
            'from_date': data.get('from_date'),
            'status_code': HTTPStatus.OK
        }
    except (
        requests.exceptions.RequestException, ValueError, json.JSONDecodeError
    ) as e:
        raise ValueError(f'Ошибка при запросе данных API: {e}') from e


def check_response(response):
    """Функция проверки корректности ответа API."""
    logger.info("Проверка корректности ответа API")
    if not isinstance(response, dict):
        message = (
            'Некорректный тип данных ответа API: ' + str(type(response))
        )
        raise TypeError(message)
    keys = ['current_date', 'homeworks']
    for key in keys:
        if key not in response:
            message = f'В ответе API нет ключа {key}'
            raise KeyError(message)
    homework = response.get('homeworks')
    if not isinstance(homework, list):
        message = (f'API вернул {type(homework)} под ключом homeworks, '
                   'а должен быть список')
        raise TypeError(message)
    return homework


def parse_status(homework):
    """Функция парсинга статуса проверки домашней работы."""
    logger.info("Смотрим статус домашней работы")
    if "homework_name" not in homework:
        message = "В словаре homework не найден ключ homework_name"
        raise KeyError(message)
    homework_name = homework.get('homework_name')
    if "status" not in homework:
        message = "В словаре homework не найден ключ status"
        raise KeyError(message)
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        message = (
            f"В словаре HOMEWORK_STATUSES не найден ключ {homework_status}")
        raise KeyError(message)
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = ("Отсутствуют переменные окружения")
        logger.critical(message)
        sys.exit(message)

    bot = Bot(token=TELEGRAM_TOKEN)
    from_date = None

    while True:
        try:
            response = get_api_answer(from_date)
            homework = check_response(response['data'])
            if homework:
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                logger.debug("В ответе API отсутсвуют новые статусы")
            from_date = response['from_date']
        except Exception as error:
            with contextlib.suppress(Exception):
                logger.error(f'Сбой в работе Бота: {error}')
                print(f'Сбой в работе Бота: {error}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
