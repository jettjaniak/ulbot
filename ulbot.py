import json
import re
import logging
import requests
import bs4
import time
import argparse
from datetime import datetime, timedelta

# TODO: async (grequests), don't login again if not required

CAS_LOGIN_URL = 'https://logowanie.uw.edu.pl/cas/login'
CAS_LOGIN_POST_DATA_BASE = dict(
    execution='e1s1',
    _eventId='submit'
)
UL_COOKIE_NAME = 'BIGipServerrejestracja.usos.uw.app~rejestracja.usos.uw_pool'
COURSE_URL_BASE = 'http://rejestracja.usos.uw.edu.pl/course.php?course_id=%d&gr_no=%d'
REGISTER_URL = 'http://rejestracja.usos.uw.edu.pl/cart.php?op=reg'


def soup(response):
    return bs4.BeautifulSoup(response.text, 'html.parser')


def select_one(response, selector):
    return soup(response).select_one(selector)


def send_prepped(session, prepped):
    while True:
        try:
            response = session.send(prepped)
            return response
        except requests.exceptions.ConnectionError:
            continue


def cas_login(session, username, password):
    get_response = session.get(CAS_LOGIN_URL)
    token = select_one(get_response, 'input[name=lt]')['value']
    post_data = dict(**CAS_LOGIN_POST_DATA_BASE, username=username, password=password, lt=token)
    post_response = session.post(CAS_LOGIN_URL, data=post_data)
    message = select_one(post_response, '#msg')
    return 'success' in message['class']


def ul_auth(session):
    url = 'https://logowanie.uw.edu.pl/cas/login;jsessionid=%s' % session.cookies['JSESSIONID']
    params = dict(service='http://rejestracja.usos.uw.edu.pl/caslogin.php')
    response = session.get(url, params=params)
    return UL_COOKIE_NAME in session.cookies


def fetch_group(session, course_id, group_nr):
    response = session.get(COURSE_URL_BASE % (course_id, group_nr))
    logging.debug(response.history)
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


def register(session, course_id, group_nr, csrf, prgos):
    try:
        # req_list = [grequests.post(REGISTER_URL, data=dict(**REGISTER_POST_DATA, csrftoken=csrf, prgos_id=prgos), session=s)]
        # response = grequests.map(req_list)[0]
        register_post_data = dict(course_id=course_id, gr_no=group_nr, csrftoken=csrf, prgos_id=prgos)
        register_request = requests.Request('POST',  REGISTER_URL, data=register_post_data)
        prepped_register_request = session.prepare_request(register_request)
        response = send_prepped(session, prepped_register_request)

        logging.debug(response.text)
        if response.json()['komunikat'] == 'ERR_REG_NOT_ACTIVE_YET':
            open_date = datetime.strptime(response.json()['params']['openDate'], '%Y-%m-%d %H:%M:%S')
            now = datetime.strptime(response.json()['params']['now'], '%Y-%m-%d %H:%M:%S')
            time_left = open_date - now
            print("  Registration not active yet.")
            if time_left < timedelta(minutes=4):
                print(' ', time_left, 'left, waiting to send register request...')
                time.sleep(time_left.total_seconds())
                # time.sleep(3)
                response = send_prepped(session, prepped_register_request)
                print('  %s' % response.text)
                return response.json()['komunikat'] in {'CONF_REG_SUCCESS', 'CONF_REG_SUCCESS_WITH_LINK'}
            else:
                print('  More than 4 minutes left, waiting ', time_left-timedelta(minutes=2), ' to login again...')
                time.sleep((time_left-timedelta(minutes=2)).total_seconds())
                # time.sleep(3)
                return False
        elif response.json()['komunikat'] in {'CONF_REG_SUCCESS', 'CONF_REG_SUCCESS_WITH_LINK'}:
            print("  Registered!")
            return True
        else:
            print("  Status: %s" % response.json()['komunikat'])
            return False
    except json.JSONDecodeError:
        # probably authentication error
        print("JSONDecode error.")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--username')
    parser.add_argument('-p', '--password')
    parser.add_argument('-c', '--course_id')
    parser.add_argument('-g', '--group_nr')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    course_id = int(args.course_id)
    group_nr = int(args.group_nr)

    try:
        while True:
            with requests.Session() as s:
                print("Logging in to CAS... ", end='')
                if cas_login(s, args.username, args.password):
                    print("success.")
                    print(" * CASTGCNG:     %s" % s.cookies['CASTGCNG'])
                    print(" * JSESSIONID:   %s" % s.cookies['JSESSIONID'])
                    print("Authorizing to UL... ", end='')
                    if ul_auth(s):
                        print("success.")
                        print(" * PHPSESSID:   %s" % s.cookies['PHPSESSID'])
                        print(" * BIGipSer...: %s" % s.cookies[UL_COOKIE_NAME])
                        print("Fetching data from group page... ", end='')
                        fg = fetch_group(s, course_id, group_nr)
                        if fg:
                            print("success.")
                            print(" * CSRF:    %s" % fg['csrf'])
                            print(" * prgos:   %s" % fg['prgos'])
                            print("Registering to group:")
                            if register(s, course_id, group_nr, **fg):
                                break
                        else:
                            print("fail.")
                    else:
                        print("fail.")
                else:
                    print("fail.")
            print()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()