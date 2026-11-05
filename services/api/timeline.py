"""A complete chronological frame plan, including requested years without imagery."""


def timeline_observations(result):
    request = result['request']
    observations = result['observations']
    if request['mode'] != 'history':
        return sorted(observations, key=lambda item: item['label'])
    by_year = {int(item['label']): item for item in observations}
    return [by_year.get(year, {
        'index': year - request['from_year'], 'year': year, 'label': str(year),
        'state': 'missing', 'scenes': [], 'reason': 'No usable observation; no frame was interpolated.'
    }) for year in range(request['from_year'], request['to_year'] + 1)]
