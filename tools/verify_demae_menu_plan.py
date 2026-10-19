"""Verify reviewed real menu observations and a local basket calculation.

Only temporary test handoffs are created. No Wii notice, provider cart or order.
"""
import json
from pathlib import Path
import sys
import tempfile
import threading
from http.client import HTTPConnection
from html import escape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_menu import basket_plan
from jwc24.demae_menu_directory import MenuDirectory
from jwc24.demae_database import DemaeDatabase
from jwc24.demae_handoff import HandoffStore
from tools.demae_phone_server import create_server


def verify_menu(menu):
    subtotal = pages = checked = 0
    with tempfile.TemporaryDirectory() as temporary:
        store = HandoffStore(Path(temporary)/'handoff.sqlite')
        server = create_server('127.0.0.1', 0, store, object())
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for start in range(0, len(menu['items']), 50):
                items = menu['items'][start:start+50]
                selections = [{'item_id': item['id'], 'quantity': 1} for item in items]
                plan = basket_plan(menu, selections)
                token = store.create('1234567890123456', restaurant=menu['restaurant'],
                                     menu=menu, selections=selections)
                connection = HTTPConnection(*server.server_address, timeout=3)
                try:
                    connection.request('GET', '/h/'+token)
                    response = connection.getresponse()
                    text = response.read().decode('utf-8')
                finally:
                    connection.close()
                if (response.status != 200 or text.count('<li>') != len(items)
                        or any(escape(item['name']) not in text for item in items)
                        or f'¥{plan["listed_items_subtotal_yen"]:,}' not in text
                        or store.status(token)['confirmed'] or store.status(token)['notice_queued']):
                    raise ValueError('Real menu phone summary verification failed')
                subtotal += plan['listed_items_subtotal_yen']
                checked += len(items)
                pages += 1
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)
    return {'restaurant_id': menu['restaurant']['restaurant_id'], 'menu_items_verified': len(menu['items']),
        'phone_basket_items_verified': checked, 'phone_basket_pages_verified': pages,
        'listed_items_subtotal_yen': subtotal,
        'checkout_total_yen': None,
        'phone_basket_summary_verified': True,
        'native_menu_integrated': False, 'orders_submitted': 0, 'notices_created': 0}


def main():
    private = Path(__file__).resolve().parents[1] / 'private/demae'
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
    coverage = directory.coverage()
    results = []
    for row in coverage['restaurants']:
        if not row['menu_plan_ready']:
            continue
        identifier = row['restaurant_id']
        menu = directory.menu(identifier)
        first = directory.menu_page(identifier)
        pages = [first] + [directory.menu_page(identifier, page=number)
                           for number in range(2, first['total_pages']+1)]
        if [item for page in pages for item in page['items']] != menu['items']:
            raise ValueError('Menu pagination lost or changed observed items')
        for category in first['categories']:
            filtered = directory.menu_page(identifier, category=category)
            items = filtered['items'][:]
            for number in range(2, filtered['total_pages']+1):
                items.extend(directory.menu_page(identifier, category=category, page=number)['items'])
            if items != [item for item in menu['items'] if item['category'] == category]:
                raise ValueError('Category pagination lost or changed observed items')
        result = verify_menu(menu)
        result['menu_pages_verified'] = len(pages)
        result['menu_category_pages_verified'] = True
        results.append(result)
    if not results:
        raise ValueError('No currently valid branch menus to verify')
    report = {'branches_verified': len(results), 'menu_items_verified': sum(row['menu_items_verified'] for row in results),
              'phone_basket_items_verified': sum(row['phone_basket_items_verified'] for row in results),
              'menu_pages_verified': sum(row['menu_pages_verified'] for row in results),
              'results': results, 'native_menu_integrated': False, 'orders_submitted': 0, 'notices_created': 0}
    (private/'menus/menu-plan-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
