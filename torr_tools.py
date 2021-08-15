import PTN


def parse_torr_name(name):
    return PTN.parse(name)


def get_torr_quality(name):
    return int(PTN.parse(name)['resolution'][:-1])