import json
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import ApiAccessError, SendMessageError

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s (%(funcName)s | %(lineno)d)"
)
handler.setFormatter(formatter)
logger.addHandler(handler)

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


def check_tokens():
    """Проверка доступности переменных окружения."""
    for var in (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID):
        if not var:
            logger.critical('Отсутствует переменная окружения.')
            return False
    return True


def send_message(bot, message):
    """Отправляет сообщение пользователю в Телеграмм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as send_message_error:
        logger.error('Ошибка с отправкой сообщения')
        raise SendMessageError('Ошибка отправки сообщения', send_message_error)
    else:
        logger.debug(f'Сообщение "{message}" успешно отправлено.')
    finally:
        return True


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса Практикум Домашка."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException as error:
        message = f'Эндпойнт недоступен: {error}'
        logger.error(message)
        raise ApiAccessError(message)
    if response.status_code != HTTPStatus.OK:
        raise response.raise_for_status()
    try:
        return response.json()
    except json.JSONDecodeError as error:
        raise json.JSONDecodeError(f'Формат не json: {error}'.format(error))


def check_response(response):
    """Проверяет ответ API на валидность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не в формате словаря.')
    elif 'homeworks' not in response:
        raise KeyError('В ответе API нет ключа "homeworks"')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError
    return homeworks


def parse_status(homework):
    """Извлекает информацию о конкретной домашке."""
    if homework:
        try:
            homework_name = homework["homework_name"]
            homework_status = homework["status"]
        except Exception as error:
            raise KeyError(f'Нет ключа: {homework_name}'.format(error))
    else:
        return False
    try:
        verdict = HOMEWORK_VERDICTS[homework_status]
    except KeyError:
        raise ValueError
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    send_message(bot, 'Бот запущен.')
    timestamp = int(time.time())
    api_error = 0

    while True:
        try:
            response = get_api_answer(timestamp)
            check = check_response(response)
            if check:
                status_homework = parse_status(check[0])
                send_message(bot, status_homework)
                logger.debug('Сообщение с новым статусом отправлено')
            timestamp = response["current_date"]
        except SendMessageError as send_message_error:
            logging.error('Ошибка  отправки сообщения', send_message_error)
        except ApiAccessError as error_api:
            message = f'Нет доступа к API: {error_api}'
            logger.error(message)
            if api_error == 0:
                send_message(bot, message)
                logger.info('Отправка ошибки ApiAccessError')
                api_error += 1
        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            logger.error(message)
            send_message(bot, message)
            logger.info("Непредвиденная ошибка программы.")
        else:
            logger.debug('В статусе домашки нет изменений.')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        datefmt="%H:%M:%S",
        filename="main.log",
        encoding="UTF-8",
        filemode="a",
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(funcName)s - %(message)s'
    )
    main()
