"""Reviewed Hot Pepper branch identities linked to official Demae-can pages."""
from datetime import datetime, timezone
import re
import unicodedata
from urllib.parse import urlsplit


def provider_shop_url(value):
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError('Invalid Demae-can shop URL')
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or parsed.netloc != 'demae-can.com'
            or not re.fullmatch(r'/shop/menu/[0-9]{1,12}', parsed.path)
            or parsed.query or parsed.fragment):
        raise ValueError('Expected a direct official Demae-can shop URL')
    return value


def _identity(value, *, address=False):
    if not isinstance(value, str) or not value.strip() or len(value) > 1024:
        raise ValueError('Missing restaurant identity')
    value = unicodedata.normalize('NFKC', value).casefold()
    value = re.sub(r'\s+', '', value)
    if address:
        value = re.sub(r'(?<=[0-9])丁目(?=[0-9])', '-', value)
        # Formatting variants observed on reviewed Kyoto/Nagaoka branches.
        # Preserve every lot/floor number; do not drop building or unit data.
        value = re.sub(r'(?<=[0-9])番地(?=[^0-9]|$)', '', value)
        value = re.sub(r'(?<=[0-9])f$', '階', value)
        # Official Kanazawa listing writes ア－ク for the catalog's アーク.
        # Only a hyphen between katakana is treated as a vowel-length mark;
        # numeric lot separators and Latin building/unit names are untouched.
        value = re.sub(r'(?<=[ァ-ヶ])-(?=[ァ-ヶ])', 'ー', value)
    return value


def validate_context(context):
    """Bound the public snapshot saved into a checkout session."""
    if not isinstance(context, dict) or set(context) != {'restaurant_id', 'name', 'provider_url'}:
        raise ValueError('Invalid restaurant handoff context')
    if not isinstance(context['restaurant_id'], str) or not re.fullmatch(r'hotpepper:J[0-9]{9}', context['restaurant_id']):
        raise ValueError('Invalid Hot Pepper restaurant ID')
    name = context['name']
    if not isinstance(name, str) or not name.strip() or len(name) > 256 or any(ord(c) < 32 for c in name):
        raise ValueError('Invalid restaurant name')
    return {'restaurant_id': context['restaurant_id'], 'name': name,
            'provider_url': provider_shop_url(context['provider_url'])}


def resolve_reviewed_link(restaurant, review, *, now=None):
    """Require a recent, exact branch match; never guess from chain name alone.

    review is a locally curated evidence record, not an untrusted HTTP input.
    Its Demae-can name/address must be read from the linked official page.
    """
    if not isinstance(restaurant, dict) or not isinstance(review, dict):
        raise ValueError('Invalid restaurant or review')
    if review.get('restaurant_id') != restaurant.get('id'):
        raise ValueError('Restaurant review ID mismatch')
    if _identity(review.get('provider_name')) != _identity(restaurant.get('name')):
        raise ValueError('Restaurant branch name mismatch')
    if _identity(review.get('provider_address'), address=True) != _identity(restaurant.get('address'), address=True):
        raise ValueError('Restaurant branch address mismatch')
    try:
        verified = datetime.fromisoformat(review['verified_at'])
        if verified.tzinfo is None:
            raise ValueError
        age = ((now or datetime.now(timezone.utc)) - verified).total_seconds()
    except (KeyError, TypeError, ValueError):
        raise ValueError('Invalid restaurant review timestamp') from None
    if not 0 <= age <= 30 * 86400:
        raise ValueError('Restaurant review needs refreshing')
    return validate_context({'restaurant_id': restaurant['id'], 'name': restaurant['name'],
                             'provider_url': review.get('provider_url')})
