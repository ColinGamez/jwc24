"""Check retained real categories using offline native menu candidate framing."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_database import DemaeDatabase
from tools.build_demae_menu_fixture import build_menu_categories
from tools.verify_demae_menu_consumer import verify
from tools.verify_demae_xml_parser import verify_tree
from tools.verify_demae_menu_model import verify as verify_model


def main():
    private = Path(__file__).resolve().parents[1]/'private/demae'
    source = (private/'fixtures/HCHJ-local-api.dol').read_bytes()
    directory = DemaeDatabase(private/'demae.sqlite').menu_directory()
    accepted, blocked = [], []
    for row in directory.coverage()['restaurants']:
        if not row['menu_plan_ready']:
            continue
        identifier = row['restaurant_id']
        menu = directory.menu(identifier)
        try:
            xml, entries = build_menu_categories(menu)
        except UnicodeEncodeError:
            blocked.append({'restaurant_id': identifier, 'reason': 'source_category_not_cp932'})
            continue
        tree = verify_tree(source, xml)
        result = verify(source, xml)
        if (not result['accepted'] or [r['menuCode'] for r in result['inserted_rows']]
                != [e['menu_code'] for e in entries]
                or [r['name'] for r in result['inserted_rows']] != [e['source_category'] for e in entries]):
            raise ValueError('Native category candidate lost branch codes, names or rows')
        model = verify_model(source, result['inserted_rows'])
        accepted.append({'restaurant_id': identifier, 'categories': entries,
                         'xml_bytes': len(xml), 'parser_stack_bytes': tree['max_stack_bytes'],
                         'native_model_rows_verified': model['rows_verified']})
    report = {'candidate_branches_verified': len(accepted),
              'categories_verified': sum(len(r['categories']) for r in accepted),
              'blocked_branches': blocked, 'results': accepted,
              'native_model_mocked': True, 'native_menu_integrated': False,
              'separate_native_model_verified': True,
              'native_rendering_verified': False, 'orders_submitted': 0}
    (private/'menus/native-menu-verification.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'results'}))


if __name__ == '__main__':
    main()
