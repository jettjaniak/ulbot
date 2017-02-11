import re
import bs4
import requests
import settings
import logging
import time
import json
import gevent
import numpy as np


def soup(response):
    return bs4.BeautifulSoup(response.text, 'html.parser')


def select_one(response, selector):
    try:
        return soup(response).select_one(selector)
    except TypeError:
        pass


def send_prepped(prepped):
    with requests.Session() as s:
        while True:
            try:
                response = s.send(prepped)
                return response
            except requests.exceptions.ConnectionError:
                continue


def send_green_prepped(prepped, quantity, period):
    def send(delay):
        gevent.sleep(delay)
        try:
            response = s.send(prepped)
            response_json = response.json()
        except requests.exceptions.ConnectionError:
            return "connection error"
        except json.JSONDecodeError:
            return "auth error"
        return response_json['komunikat']

    s = requests.Session()
    distribution = np.linspace(0, period, quantity)
    return gevent.joinall([gevent.spawn(send, d) for d in distribution])


def ul_auth(session, username, password):
    def cas_login():
        while True:
            cas_success = False
            print("Logging in to CAS... ", end='')
            get_response = session.get(settings.CAS_LOGIN_URL)
            token = select_one(get_response, 'input[name=lt]')['value']
            if token:
                post_data = dict(**settings.CAS_LOGIN_POST_DATA_BASE, username=username, password=password, lt=token)
                post_response = session.post(settings.CAS_LOGIN_URL, data=post_data)
                message = select_one(post_response, '#msg')
                try:
                    cas_success = 'success' in message['class']
                except TypeError:
                    print("fail. (message None)")
                    logging.debug(post_response.text)
                if cas_success:
                    print("success.")
                    logging.info(" * BIGipSer...:  %s" % session.cookies[settings.CAS_COOKIE_NAME])
                    logging.info(" * CASTGCNG:     %s" % session.cookies['CASTGCNG'])
                    logging.info(" * JSESSIONID:   %s" % session.cookies['JSESSIONID'])
                    break
                else:
                    print("fail. (message classes: %s)" % ', '.join(message['class']))
            else:
                print("fail. (no token)")
            time.sleep(1)

    success = False
    while not success:
        cas_login()
        print("Authorizing to UL... ", end='')
        url = 'https://logowanie.uw.edu.pl/cas/login;jsessionid=%s' % session.cookies['JSESSIONID']
        params = dict(service='http://rejestracja.usos.uw.edu.pl/caslogin.php')
        response = session.get(url, params=params)
        success = settings.UL_COOKIE_NAME in session.cookies
    print("success.")
    print(" * PHPSESSID:   %s" % session.cookies['PHPSESSID'])
    logging.info(" * BIGipSer...: %s" % session.cookies[settings.UL_COOKIE_NAME])


def fetch_group(cookie, course_id, group_nr):
    response = requests.get(settings.COURSE_URL_BASE % (course_id, group_nr), cookies={'PHPSESSID': cookie})
    group_soup = soup(response)
    prgos_div = group_soup.select_one('.groupCart div')
    if prgos_div:
        prgos = prgos_div['data-prgos-id']
        if prgos != 'null':
            return dict(
                prgos=prgos,
                csrf=re.search('csrfToken: \'([0-9]{4}-[0-9]{2}-[0-9]{2}-[a-f0-9]{16})\'',
                               response.text).group(1)
            )
    print("Error: No prgos_id.")
    exit()


def auth_and_return_cookie(username, password):
    with requests.Session() as s:
        ul_auth(s, username, password)
        return s.cookies['PHPSESSID']


def provide_secrets(cookie, username, password, course_id, group_nr):
    if cookie:
        response = requests.get(settings.UL_URL, cookies={'PHPSESSID': cookie})
        if not select_one(response, 'b.casmenu'):
            print("Expired or wrong cookie.")
            if not (username and password):
                print("Credentials not provided, exiting.")
                exit()
            cookie = auth_and_return_cookie(username, password)
    else:
        cookie = auth_and_return_cookie(username, password)

    return dict(cookie=cookie, **fetch_group(cookie, course_id, group_nr))