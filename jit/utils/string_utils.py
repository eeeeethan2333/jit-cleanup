from datetime import datetime
from datetime import timezone


def try_parsing_date(s, fmt_list):
    """
    parse string s into datetime format using fmt options in fmt_list
    :param s:
    :param fmt_list: ["%d/%m/%YT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%SZ"]
    :return:
    """
    # Get rid of the microsecond as some datetime implementation use 8 digit precision
    datetime_seconds = s.split(".", 1)

    for fmt in fmt_list:
        try:
            return datetime.strptime(datetime_seconds[0]+'Z', fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    raise ValueError('no valid date format found')
