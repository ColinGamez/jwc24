"""Read-only text diagnostics; never replace provider names automatically."""
import unicodedata


def _encodable(value, codec):
    try:
        value.encode(codec, errors='strict')
        return True
    except UnicodeEncodeError:
        return False


def inspect_native_text(value):
    if not isinstance(value, str):
        raise ValueError('Native text inspection requires a string')
    if len(value) > 4096:
        raise ValueError('Text exceeds the diagnostic limit')
    normalized = unicodedata.normalize('NFKC', value)
    unsupported = sorted({ord(char) for char in value if not _encodable(char, 'shift_jis')})
    return {'strict_shift_jis': _encodable(value, 'shift_jis'),
            'cp932': _encodable(value, 'cp932'),
            'nfkc_changes_text': normalized != value,
            'nfkc_strict_shift_jis': _encodable(normalized, 'shift_jis'),
            'unsupported_codepoints': [f'U+{number:04X}' for number in unsupported],
            'xml_controls': any(ord(char) < 32 and char not in '\t\r\n' for char in value),
            'scope': 'Python codec diagnostics; native extension repertoire unverified'}


def prepare_native_display(value):
    """Preserve supported text; audited native cache characters match CP932.

    Whole-codec equivalence outside that audited repertoire is not asserted.
    """
    report = inspect_native_text(value)
    if report['cp932'] and not report['xml_controls']:
        return {'display_text': value, 'ready': True, 'substitutions': 0, 'source_changed': False}
    return {'display_text': None, 'ready': False, 'substitutions': 0, 'source_changed': False}
