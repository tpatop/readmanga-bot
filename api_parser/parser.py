import logging
from fake_useragent import UserAgent
from requests import get, post
from bs4 import BeautifulSoup
from pydantic import BaseModel
from time import sleep


# Конфигурация логгирования
logging.basicConfig(
    format='%(filename)s:%(lineno)d #%(levelname)-8s [%(asctime)s] - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Вывод на консоль
        logging.FileHandler('api_parser/logfile.log')  # Запись в файл
    ],
    level=logging.INFO
)


HEADERS = {'User-Agent': UserAgent().chrome}
URLS = ('https://readmanga.live', 'https://mintmanga.com')


class UpdateManga(BaseModel):
    url_id: int
    link: str
    chapters: str
    name: str


def process_download_page(url: str, headers):
    result = get(url, headers=headers)
    return result.text


def process_validate_chapters(data: list) -> str:
    result = []
    for el in data:
        if el != '...' and el != '-' and el.lower() != 'сингл' and el.strip(',').isalpha():
            continue
        else:
            result.append(el)
    if result:
        return ' '.join(result)


def process_parsing_html(html: str, url_id: int):
    '''Функция сбора необходимой информации с сайта'''
    if html is None:
        return None
    soup = BeautifulSoup(html, 'lxml')
    # Выбираем область "Последних обновлений каталога"
    last_updates = soup.find('div', {'id': 'last-updates'})
    # Получаем список обновлений
    updates = last_updates.find_all('div', {'class': 'tile'})
    # Проходим по списку и собираем необходимую информацию
    result = []
    for data in updates:
        # # поиск названия
        name = data.find('div', {'class': 'desc'}).find('a')['title']
        # # # поиск жанров
        # print(update.find('div', {'class': 'tile-info'}).text.strip())
        # # # поиск картинки
        # if update.find('div', {'class': 'no-image'}):  # отсутствие картинки
        #     print(IMAGE_NOT_FOUND)
        # else:
        #     print(update.find('img')['data-original'].replace('_p.', '.'))
        # # # поиск ссылки
        link = data.find('div', {'class': 'desc'}).find('a')['href']
        # # # поиск информации по обновлению глав
        chapters = process_validate_chapters(
            data.find('div', {'class': 'chapters-text'}).text.split()
        )
        if chapters is not None:
            update = UpdateManga(
                url_id=url_id,
                link=link,
                chapters=chapters,
                name=name
            )
            result.append(update)
    return result


def get_url_id(url: str):
    for x in range(len(URLS)):
        if URLS[x] in url:
            return x


def process_send_updates_in_db(updates):
    updates = [update.model_dump() for update in updates]
    response = post('http://127.0.0.1:8080/manga/add_update', json=updates)
    # необходима проверка статуса кода и возвращения кода разрешения или запрета парсинга следующей страницы
    # вместо True должно быть что-то типа response.status
    return True


def process_start_parsing():
    for _url in URLS:
        for page in range(1):
            url_id = get_url_id(_url)
            url = _url + f'/?offset={page * 50}#last-updates'
            html = process_download_page(url, HEADERS)
            result = process_parsing_html(html, url_id)
            status = process_send_updates_in_db(result)
            logging.info(f'Url = {url},\tstatus= {status}')
            if not status:
                break
            # нужна отправка на сервер для проверки наличия в БД
            sleep(5)


if __name__ == '__main__':
    while True:
        try:
            logging.info('Start process')
            process_start_parsing()
        except Exception as e:
            logging.error(f'An error occurred: {str(e)}')
        finally:
            logging.info('Process sleep on 10 minutes')
            sleep(10 * 60)
