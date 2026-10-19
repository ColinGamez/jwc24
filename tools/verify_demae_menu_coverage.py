"""Validate every available branch menu and basket plan across 47 prefectures."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_menu_directory import MenuDirectory
from jwc24.demae_database import DemaeDatabase


def main():
    private = Path(__file__).resolve().parents[1]/'private/demae'
    archive = private/'demae.sqlite'
    if archive.is_file():
        directory = DemaeDatabase(archive).menu_directory()
    else:
        catalogs = [json.loads(path.read_text(encoding='utf-8'))
                    for path in sorted((private/'hotpepper').glob('JP-*-catalog.json'))]
        reviews = json.loads((private/'restaurant-link-reviews.json').read_text(encoding='utf-8'))
        observations = [json.loads(path.read_text(encoding='utf-8'))
                        for path in sorted((private/'menus').glob('demaecan-*.observed.json'))]
        directory = MenuDirectory(catalogs, reviews, observations)
    if set(directory.prefectures) != {f'JP-{n:02d}' for n in range(1, 48)}:
        raise ValueError('Nationwide menu coverage requires all 47 prefectures')
    report = directory.coverage()
    for row in report['restaurants']:
        if row['menu_plan_ready']:
            menu = directory.menu(row['restaurant_id'])
            plan = directory.plan(row['restaurant_id'], [{'item_id': menu['items'][0]['id'], 'quantity': 2}])
            if plan['listed_items_subtotal_yen'] != 2*menu['items'][0]['listed_price_yen']:
                raise ValueError('Branch basket subtotal mismatch')
    (private/'menus/nationwide-menu-coverage.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'catalog_prefectures': len(report['prefectures']),
        'catalog_restaurants': len(report['restaurants']),
        'prefectures_with_menu_plans': sum(bool(p['menu_plan_restaurants']) for p in report['prefectures']),
        'menu_plan_restaurants': report['menu_plan_restaurants'],
        'observed_menu_items': report['observed_menu_items'], 'native_menu_integrated': False,
        'cp932_menu_restaurants': report['cp932_menu_restaurants'],
        'orders_submitted': 0, 'notices_created': 0}))


if __name__ == '__main__':
    main()
