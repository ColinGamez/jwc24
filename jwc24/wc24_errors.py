"""Diagnostic categories from the recovered April 2008 WC24 v0.25 message list.

These are reference examples, not complete channel-specific root-cause rules.
No errors are repaired, retried or acknowledged by this module.
"""
import re


def explain_error(code: str | int) -> dict:
    if type(code) is int and 0 <= code <= 999999:
        code = f'{code:06d}'
    if not isinstance(code, str) or re.fullmatch(r'[0-9]{6}', code) is None:
        raise ValueError('Expected a six-digit ASCII Wii error code')
    exact = {
        '109014': 'file_or_storage', '109016': 'file_or_storage',
        '109017': 'file_or_storage', '109049': 'system_update_required',
        '109001': 'wc24_initialization', '109042': 'wc24_initialization',
        '109026': 'busy_retry_timeout', '109107': 'wc24_setting_disabled',
        '109139': 'wc24_setting_disabled', '102304': 'network_configuration',
        '102312': 'network_configuration', '102305': 'service_connection',
        '109106': 'outbox_capacity', '109999': 'other_wc24_error',
        '107304': 'download_task', '107305': 'download_task',
    }
    category = exact.get(code)
    if category is None:
        if code.startswith('05'):
            category = 'network_configuration'
        elif code.startswith('11'):
            category = 'service_connection'
        elif code.startswith('109') and code.endswith('14'):
            category = 'file_or_storage'
        else:
            category = 'unknown'
    checks = {
        'file_or_storage': 'Inspect the failing file operation and native storage result.',
        'system_update_required': 'Check the client and System Menu compatibility requirements.',
        'wc24_initialization': 'Inspect NWC24OpenLib and IPC results.',
        'busy_retry_timeout': 'Check whether bounded library-open retries exhausted their timeout.',
        'wc24_setting_disabled': 'Check the relevant WC24 setting and native readiness result.',
        'network_configuration': 'Inspect the connection configuration and network result.',
        'service_connection': 'Inspect the service request and connection result.',
        'outbox_capacity': 'Inspect the native outgoing mailbox capacity result.',
        'other_wc24_error': 'Capture the original API result and calling context.',
        'download_task': 'Inspect the individual download task result and fetched payload.',
        'unknown': 'Trace this channel and API context before assigning a meaning.',
    }
    return {'code': code, 'category': category, 'next_check': checks[category],
            'reference': 'WC24 message list v0.25 (2008-04-04)' if category != 'unknown' else None,
            'diagnostic_only': True, 'root_cause_verified': False}
