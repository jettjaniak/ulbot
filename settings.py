CAS_LOGIN_URL = 'https://logowanie.uw.edu.pl/cas/login'

CAS_LOGIN_POST_DATA_BASE = dict(
    execution='e1s1',
    _eventId='submit'
)

CAS_COOKIE_NAME = 'BIGipServerlogowanie.uw.edu.pl.app~logowanie.uw.edu.pl_pool'

UL_COOKIE_NAME = 'BIGipServerrejestracja.usos.uw.app~rejestracja.usos.uw_pool'

UL_URL = 'http://rejestracja.usos.uw.edu.pl/'
UNKNOWN_COURSE_URL = UL_URL + 'index.php?msg=ERR_REG_UNK_COURSE'

COURSE_URL_BASE = UL_URL + 'course.php?course_id=%d&gr_no=%d'

REGISTER_URL = UL_URL + 'cart.php?op=reg'

APISRV_NOW_URL = 'http://usosapps.uw.edu.pl/services/apisrv/now'
