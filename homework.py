import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import ApiAccessError

load_dotenv()

logger = logging.getLogger(__name__)

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
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    if any(tokens):
        return True
    logger.critical('Отсутствует переменная окружения.')
    return False


def send_message(bot, message):
    """Отправляет сообщение пользователю в Телеграмм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение "{message}" успешно отправлено.')
    except Exception as exc:
        logger.error(f'Ошибка с отправкой сообщения: {exc}')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса Практикум Домашка."""
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS,
                                params={'from_date': timestamp})
    except requests.exceptions.RequestException as err:
        raise ApiAccessError(f'Эндпойнт недоступен: {err}')
    if response.status_code != HTTPStatus.OK:
        raise response.raise_for_status()
    return response.json()


def check_response(response):
    """Проверяет ответ API на валидность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не в формате словаря.')
    elif 'homeworks' not in response:
        raise KeyError('В словаре из ответа API нет ключа "homeworks"')
    elif 'current_date' not in response:
        raise KeyError('В словаре из ответа API нет ключа "current_date"')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Ответ API по ключю "homeworks" не в формате списка.')
    current_date = response['current_date']
    if current_date is not int and 2000000000 < current_date < 1549962000:
        logger.error(f'В ответе API получено неверное значение'
                     f'current_date: ({current_date}).')
    return homeworks


def parse_status(homework):
    """Извлекает информацию о конкретной домашке."""
    key_list = ['homework_name', 'status']
    try:
        for i in range(len(key_list)):
            if not homework[key_list[i]]:
                raise KeyError(f'В ответе API нет ключа: {key_list[i]}')
        if homework[key_list[1]] not in HOMEWORK_VERDICTS:
            raise ValueError('Неожиданный статус домашки в ответе API.')
    except KeyError:
        raise KeyError('Иначе не проходит тест.')
    verdict = HOMEWORK_VERDICTS[homework[key_list[1]]]
    return (f'Изменился статус проверки работы "{homework[key_list[0]]}".'
            f'{verdict}')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    send_message(bot, 'Бот запущен.')
    timestamp = int(time.time())
    prev_err = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                status_homework = parse_status(homework[0])
                send_message(bot, status_homework)
                logger.debug('Сообщение с новым статусом отправлено')
            timestamp = response['current_date']
            logger.debug('В статусе домашки нет изменений.')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if prev_err != error:
                send_message(bot, message)
                prev_err = error
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
#    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s (%(funcName)s | %(lineno)d)"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    main()
