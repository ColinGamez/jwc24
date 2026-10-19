"""Conservative catalog classification; category membership is not delivery."""
from .demae_categories import exact_genre_mapping, native_categories


def classify_restaurants(restaurants):
    categories = {row['code']: {'name': row['name'], 'restaurant_ids': []}
                  for row in native_categories()}
    unmapped = []
    seen = set()
    for row in restaurants:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id']:
            raise ValueError('Restaurant requires a stable source ID')
        if row['id'] in seen:
            raise ValueError('Duplicate restaurant ID in classification input')
        seen.add(row['id'])
        code = exact_genre_mapping(row.get('genre'))
        if code is None:
            unmapped.append(row['id'])
        else:
            categories[code]['restaurant_ids'].append(row['id'])
    return {'categories': categories, 'unmapped_restaurant_ids': unmapped,
            'restaurants': len(seen), 'ordering_supported': False,
            'scope': 'exact directory genre labels; not delivery or native availability'}
