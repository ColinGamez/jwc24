"""Conservative shop-list producer checks, not full native or order validation."""


def assess_shop_list_record(record):
    if not isinstance(record, dict):
        raise ValueError('Shop-list record must be an object')
    reasons = []
    for field in ('shopCode', 'homeCode', 'name', 'catchphrase', 'yoyaku'):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            reasons.append('missing_' + field)
            continue
        if len(value.encode('utf-8', errors='surrogatepass')) > 4096:
            reasons.append('oversized_' + field)
        try:
            value.encode('cp932', errors='strict')
        except UnicodeEncodeError:
            reasons.append('encoding_' + field)
        if ']]>' in value or any(ord(char) < 32 and char not in '\t\r\n' for char in value):
            reasons.append('xml_' + field)
    if record.get('activate') not in ('on', 'stop', 'near'):
        reasons.append('unsupported_activate')
    payments = record.get('paymentList')
    if not isinstance(payments, list) or '代金引換' not in payments:
        reasons.append('cash_on_delivery_unestablished')
    status = record.get('shopStatus')
    if not isinstance(status, dict) or not isinstance(status.get('status'), dict):
        reasons.append('missing_shopStatus_status')
    for field in ('minPrice', 'waitTime'):
        value = record.get(field)
        if value is not None and (type(value) is not int or not 0 <= value <= 1_000_000):
            reasons.append('invalid_' + field)
    return {'producer_fields_complete': not reasons, 'reasons': reasons,
            'native_verified': False, 'ordering_verified': False}


def assess_directory_record(row):
    """Use only established directory fields; no invented service capabilities."""
    if not isinstance(row, dict):
        raise ValueError('Directory record must be an object')
    return assess_shop_list_record({'shopCode': row.get('id'), 'name': row.get('name'),
                                    'catchphrase': row.get('catchphrase')})
