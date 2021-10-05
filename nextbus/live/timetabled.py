"""
Uses database to retrieve timetabled bus times data.
"""
import datetime

import dateutil.tz

from nextbus import timetable

GB_TZ = dateutil.tz.gettz("Europe/London")


def get_timetabled_times(atco_code, timestamp=None):
    """ Get all services stopping at specified stop point in the next hour. """
    if timestamp is None:
        ts = datetime.datetime.now(datetime.timezone.utc)
    else:
        ts = timestamp

    result = timetable.get_next_services(atco_code, ts)

    services = []
    for row in result:
        # Group services by line and operator
        iterator = (
            s for s in services
            if s["line"] == row["line"] and s["opCode"] == row["op_code"]
        )
        if (service := next(iterator, None)) is None:
            service = {
                "line": row["line"],
                "name": row["line"],
                "dest": row["destination"],
                "opName": row["op_name"],
                "opCode": row["op_code"],
                "expected": [],
            }
            services.append(service)

        expected = service["expected"]
        if expected and expected[-1]["secs"] == row["seconds"]:
            # Don't add duplicate departures
            continue

        expected.append({
            "live": False,
            "secs": row["seconds"],
            "expDate": row["expected"].astimezone(dateutil.tz.UTC)
        })

    return {
        "atcoCode": atco_code,
        "smsCode": None,
        "live": False,
        "isoDate": ts.isoformat(),
        "localTime": ts.astimezone(GB_TZ).strftime("%H:%M"),
        "services": services
    }
