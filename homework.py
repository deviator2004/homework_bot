import logging
import os
import sys
import requests
import telegram
import time

from dotenv import load_dotenv
from http import HTTPStatus

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
            sys.exit(f'Отсутствует переменная окружения {env}')


def send_message(bot, message):
    """Отправляет сообщение в чат."""
    try:
        logger.debug('Начата отправка сообщения в Telegram')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение :{message}')
    except Exception as error:
        logger.error(f'Сбой при отправке сообщения в Telegram: {error}')


def get_api_answer(timestamp):
    """Делает запрос к API."""
    payload = {'from_date': timestamp}
    try:
        logger.debug('Начато выполнение запроса к API')
        request = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException as error:
        logger.critical(f'Сбой в работе программы: {error}. '
                        f'Параметры запроса: URL: {ENDPOINT}, '
                        f'Headers: {HEADERS}, Payload: {payload}')
    if request.status_code == HTTPStatus.OK:
        return request.json()
    elif request.status_code == HTTPStatus.NOT_FOUND:
        raise ex.Error404(f'Эндпоинт {ENDPOINT} недоступен. Код ответа: 404')
    else:
        raise Exception(f'Эндпоинт {ENDPOINT} недоступен. '
                        f'Код ответа: {request.status_code}')


def check_response(response):
    """Проверяет ответ от API на соответствие типу."""
    logger.debug('Начата проверка ответа сервиса')
    if not isinstance(response, dict):
        raise TypeError(f'Тип данных ответа: {type(response)}, '
                        'ожидается <class dict>')
    elif all(keys not in response for keys in ('homeworks', 'current_time')):
        raise KeyError('В словаре ответа не найдены ожидаемые ключи')
    elif not isinstance(response['homeworks'], list):
        raise TypeError('Тип данных ключа homeworks: '
                        f'{type(response["homeworks"])}, '
                        'ожидается <class list>')
    elif len(response['homeworks']) == 0:
        raise ex.NotSendingMessageError('Нет новых статусов')
    else:
        return response['homeworks'][0]


def parse_status(homework):
    """Извлекает статус домашки из ответа API."""
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise ex.UnexpectedStatusError('Неожиданный статус проверки домашней '
                                       'работы')
    if 'homework_name' not in homework:
        raise KeyError('В словаре homework не найден ключ homework_name')
    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    previous_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_time', int(time.time()))
            homework = check_response(response)
            message = parse_status(homework)
            if message != previous_message:
                send_message(bot, message)
                previous_message = message
        except ex.NotSendingMessageError as message:
            logger.debug(message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != previous_message:
                send_message(bot, message)
                previous_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
