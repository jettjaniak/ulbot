import json
import logging
import requests
import time
import argparse
from datetime import datetime, timedelta

import settings
from helpers import send_prepped, provide_secrets, select_one, send_green_prepped

# TODO: async (grequests)


def register(course_id, group_nr, cookie, username, password, delay=0.0, async=False):
    secrets = provide_secrets(cookie, username, password, course_id, group_nr)
    post_data = dict(course_id=course_id, gr_no=group_nr, csrftoken=secrets['csrf'], prgos_id=secrets['prgos'])
    request = requests.Request('POST', settings.REGISTER_URL, data=post_data, cookies={'PHPSESSID': secrets['cookie']})
    prepped = request.prepare()
    limit = settings.DEFAULT_LIMIT
    period = settings.DEFAULT_PERIOD

    print("Registering:")
    success = False
    attempts = 0
    while not success:
        attempts += 1
        local_now = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S.%f")
        print("# %s, attempt %d #" % (local_now, attempts))
        response = send_prepped(prepped)
        logging.debug(response.text)

        try:
            response_json = response.json()
        except json.JSONDecodeError:
            print("Authentication error.")
            return register(course_id, group_nr, secrets['cookie'], username, password)

        komunikat = response_json['komunikat']
        if komunikat == 'ERR_REG_NOT_ACTIVE_YET':
            open_date = datetime.strptime(response_json['params']['openDate'], '%Y-%m-%d %H:%M:%S')
            now = datetime.strptime(requests.get(settings.APISRV_NOW_URL).text, '"%Y-%m-%d %H:%M:%S.%f"')
            time_left = open_date - now
            print("  * Registration not active yet.")
            if time_left < timedelta(minutes=1):
                if not async:
                    if time_left < timedelta(0):
                        logging.info("time_left < 0: %f" % time_left.total_seconds())
                    else:
                        print('    Waiting', time_left, 'to send register request...')
                        time.sleep(time_left.total_seconds() + delay)
                        # time.sleep(3)
                    continue
                else:
                    time.sleep(time_left.total_seconds() + delay - 1)
                    for greenlet in send_green_prepped(prepped, 17, 2):
                        print(greenlet.value)
                    break
            else:
                print('    More than one minute left, waiting ', time_left-timedelta(minutes=1), ' to try again...')
                time.sleep((time_left-timedelta(minutes=1)).total_seconds())
                # time.sleep(3)
                return register(course_id, group_nr, secrets['cookie'], username, password)
        elif komunikat == 'ERR_REG_COURSE_FULL':
            if limit and period:
                wait_time = period / limit
                print("  * Course full, waiting %0.1f seconds... " % wait_time, end='', flush=True)
                time.sleep(wait_time)
                print("and trying again...")
            else:
                print("  * Course full, trying again...")
            continue
        elif komunikat == 'ERR_REG_ALREADY_REG':
            print("Error: Already registered for this course.")
            break

        elif komunikat == 'WARN_REGISTER_TRY_LIMIT_NEAR':
            remaining = response_json['params']['remaining'] + 1
            limit = response_json['params']['limit']
            count = response_json['params']['count']
            period = response_json['params']['period']
            wait_time = remaining/(limit-count) if limit-count else remaining
            print("  * Register try limit near, waiting %0.1f seconds... " % wait_time, end='', flush=True)
            time.sleep(wait_time)
            print("and trying again...")
            continue
        elif komunikat == 'WARN_REGISTER_TRY_LIMIT_EXCEEDED':
            remaining = response_json['params']['remaining']
            print("  * Register try limit exceeded, waiting %d seconds... " % remaining, end='', flush=True)
            time.sleep(remaining)
            print("and trying again...")
            continue

        elif komunikat in {'CONF_REG_SUCCESS', 'CONF_REG_SUCCESS_WITH_LINK'}:
            success = True
            print("  REGISTERED!")
        else:
            print("  UNHANDLED STATUS: %s" % response.json()['komunikat'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--username')
    parser.add_argument('-p', '--password')
    parser.add_argument('-c', '--cookie')
    parser.add_argument('-d', '--delay', type=float, default=0.0)
    parser.add_argument('-a', '--async')
    parser.add_argument('course_id', type=int)
    parser.add_argument('group_nr', type=int)
    args = parser.parse_args()
    try:
        logging.basicConfig(
            filename='logs/u%s_%s.log' %
                     (args.username, datetime.strftime(datetime.now(), "%Y%m%d_%H-%M-%S.%f")),
            level=logging.DEBUG,
            format='%(asctime)s %(message)s'
        )
    except OSError:
        print("OSError while configuring logging to file, changing to console.")
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')

    if not ((args.username and args.password) or args.cookie):
        print("You need to provide username and password OR cookie.")
        exit()

    try:
        group_page = requests.get(settings.COURSE_URL_BASE % (args.course_id, args.group_nr))
        if group_page.url != settings.UNKNOWN_COURSE_URL:
            print("Group found:", select_one(group_page, 'td h1').text)
            register(args.course_id, args.group_nr, args.cookie, args.username, args.password, args.delay, args.async)
        else:
            print("Unknown group.")
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()