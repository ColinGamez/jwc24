"""Validate curated branch matches against cached Hot Pepper directory data."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_restaurant_links import resolve_reviewed_link
from tools.asset_publication import publish_assets


def build(catalogs, reviews):
    restaurants = {}
    for document in catalogs:
        if document.get('provider') != 'hotpepper':
            raise ValueError('Expected Hot Pepper directory catalogs')
        for restaurant in document['restaurants']:
            identifier = restaurant['id']
            if identifier in restaurants:
                raise ValueError('Duplicate Hot Pepper catalog identity')
            restaurants[identifier] = restaurant
    links = {}
    seen_urls = set()
    for review in reviews:
        identifier = review.get('restaurant_id')
        if identifier not in restaurants or identifier in links:
            raise ValueError('Unknown or duplicate reviewed restaurant')
        context = resolve_reviewed_link(restaurants[identifier], review)
        if context['provider_url'] in seen_urls:
            raise ValueError('One provider branch mapped to multiple restaurant identities')
        seen_urls.add(context['provider_url'])
        links[identifier] = {'context': context, 'verified_at': review['verified_at']}
    return {'schema_version': 1, 'restaurants_checked': len(restaurants),
            'reviewed_links': links, 'delivery_eligibility': 'checked by provider at checkout',
            'native_navigation_integrated': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog-directory', type=Path, required=True)
    parser.add_argument('--reviews', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    private = Path(__file__).resolve().parents[1] / 'private'
    if not args.output.resolve().is_relative_to(private.resolve()):
        parser.error('Reviewed mappings must remain private')
    snapshots = [(path, path.read_bytes()) for path in sorted(args.catalog_directory.glob('JP-*-catalog.json'))]
    if not snapshots:
        parser.error('No cached catalogs found')
    reviews = args.reviews.read_bytes()
    result = build([json.loads(data) for _, data in snapshots], json.loads(reviews))
    publish_assets([(args.output, json.dumps(result, ensure_ascii=False, indent=2).encode())],
                   source_checks=snapshots + [(args.reviews, reviews)])
    print(f"Validated {len(result['reviewed_links'])} reviewed branch links against {result['restaurants_checked']} restaurants; no orders or notices sent")


if __name__ == '__main__':
    main()
