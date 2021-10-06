from flask import current_app

import nextbus.live.tapi
import nextbus.live.timetabled


def get_times(atco_code, use_live):
    """ Get bus times at this stop point. """
    if use_live and current_app.config.get("TRANSPORT_API_ACTIVE"):
        return tapi.get_nextbus_times(atco_code)
    else:
        return timetabled.get_timetabled_times(atco_code)
