"""Recovered native UI taxonomy; provider genres are a separate namespace."""
_CATEGORIES = (
    ('01', 'ピザ'), ('02', '弁当'), ('03', 'すし'), ('04', '和食'),
    ('05', '中華'), ('06', '洋食'), ('07', 'ファーストフード'), ('08', 'カレー'),
    ('09', '仕出し・パーティ'), ('10', 'デザート・ドリンク'), ('11', 'その他'),
)


def native_categories():
    return [{'code': code, 'name': name} for code, name in _CATEGORIES]


_DIRECTORY_GENRES = {
    '居酒屋': '11', '焼肉・ホルモン': '11', 'バー・カクテル': '11',
    'イタリアン・フレンチ': '06', 'ダイニングバー・バル': '11',
    '韓国料理': '11', 'カラオケ・パーティ': '09', '創作料理': '11',
    '各国料理': '11', 'カフェ・スイーツ': '10',
    'アジア・エスニック料理': '11', 'その他グルメ': '11',
    'お好み焼き・もんじゃ': '04', 'ラーメン': '11',
}


def exact_genre_mapping(provider_name):
    """Map explicit directory labels; unknown labels still remain unmapped.

    Broad genres use the native Other category. This is directory navigation,
    never evidence that a restaurant delivers or accepts orders.
    """
    native = next((code for code, name in _CATEGORIES if provider_name == name), None)
    if native is not None:
        return native
    return _DIRECTORY_GENRES.get(provider_name) if isinstance(provider_name, str) else None
