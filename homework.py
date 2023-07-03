import logging
import os
import sys
import requests
import telegram
import time

from dotenv import load_dotenv

import exceptions as ex

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
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Проверяет наличие переменных окружения."""
    for env in [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]:
        if env is None:
            logger.critical('Отсутствует обязательная переменная окружения: ',
                            f'{env}. Программа принудительно остановлена.')
            raise ex.EnvIsNoneError(f'Отсутствует переменная окружения {env}')


def send_message(bot, message):
    """Отправляет сообщение в чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение :{message}')
    except Exception as error:
        logger.error(f'Сбой при отправке сообщения в Telegram: {error}')


def get_api_answer(timestamp):
    """Делает запрос к API."""
    payload = {'from_date': timestamp}
    try:
        request = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException as error:
        logger.critical(f'Сбой в работе программы: {error}')
    if request.status_code == 200:
        return request.json()
    elif request.status_code == 404:
        raise ex.Error404(f'Эндпоинт {ENDPOINT} недоступен. Код ответа: 404')
    else:
        raise Exception(f'Эндпоинт {ENDPOINT} недоступен. '
                        f'Код ответа: {request.status_code}')


def check_response(response):
    """Проверяет ответ от API на соответствие типу."""
    if not isinstance(response, dict):
        raise TypeError('Тип данных ответа не соответствует ожидаемому')
    elif all(keys not in response for keys in ('homeworks', 'current_time')):
        raise KeyError('В словаре ответа не найдены ожидаемые ключи')
    elif not isinstance(response['homeworks'], list):
        raise TypeError('Тип данных ключа homeworks не соответствует '
                        'ожидаемому')
    elif len(response['homeworks']) == 0:
        raise IndexError('Нет новых статусов')
    else:
        return response['homeworks'][0]


def parse_status(homework):
    """Извлекает статус домашки из ответа API."""
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ex.UnexpectedStatusError('Неожиданный статус ДЗ')
    if 'homework_name' not in homework:
        raise KeyError('В словаре homework не найден ключ homework_name')
    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - RETRY_PERIOD
    previous_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)
        except IndexError as message:
            logger.debug(message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != previous_message:
                send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
