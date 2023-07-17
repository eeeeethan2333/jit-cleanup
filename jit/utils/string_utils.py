from datetime import datetime
from datetime import timezone


def try_parsing_date(s, fmt_list):
    """
    parse string s into datetime format using fmt options in fmt_list
    :param s:
    :param fmt_list: ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"]
    :return:
    """
    for fmt in fmt_list:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    raise ValueError('no valid date format found')
