from datetime import datetime, timezone
import hashlib
from pathlib import Path
from .domain import PROFILE, inherited, write_json

EXTENSIONS = {
    'file': 'https://stac-extensions.github.io/file/v2.1.0/schema.json',
    'table': 'https://stac-extensions.github.io/table/v1.2.0/schema.json',
    'web': 'https://stac-extensions.github.io/web-map-links/v1.3.0/schema.json',
}

def link(rel, href, type_='application/json', **extra):
    return {'rel': rel, 'href': href, 'type': type_, **extra}

def asset(path, href, type_, role):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return {'href': href, 'type': type_, 'roles': [role],
            'file:size': Path(path).stat().st_size, 'file:checksum': '1220' + digest.hexdigest()}

def doc_links():
    return [link('describedby', './README.md', 'text/markdown'), link('agents', './AGENTS.md', 'text/markdown')]

def providers(plan, layer):
    producer, host, contact = [inherited(plan, layer, k) for k in ('producer', 'host', 'contact')]
    result = []
    if producer != host:
        result.append({'name': producer, 'roles': ['producer']})
    result.append({'name': host, 'roles': ['producer', 'host'] if producer == host else ['host'],
                   'url' if contact.startswith('https://') else 'email': contact})
    return result

def build_catalog(root, plan, results):
    root = Path(root)
    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    catalog = {'type': 'Catalog', 'stac_version': '1.1.0', 'stac_extensions': [PROFILE],
               'id': plan.id, 'title': plan.title, 'description': plan.description,
               'links': [link('root', './catalog.json')] + doc_links()}
    total = 0
    japanese = plan.document_language == 'ja'
    def d(en, ja):
        return ja if japanese else en
    guide = (Path(__file__).parent / 'help' / ('validation-ja.md' if japanese else 'validation-en.md')).read_text(encoding='utf-8')
    notice = d('Basic export checks only. Detailed validation has not been run. Before publishing, follow [Detailed validation](VALIDATION.md).',
               '作成時の基本チェックのみを実施しています。詳細検証は未実施です。公開前に[詳細検証の手順](VALIDATION.md)を確認してください。')
    (root / 'VALIDATION.md').write_text(guide, encoding='utf-8')
    catalog['links'].append(link('describedby', './VALIDATION.md', 'text/markdown', title='Detailed validation'))
    root_lines = [f'# {plan.title}', '', plan.description, '', d('| Collection | Features |', '| Collection | 地物数 |'), '|---|---:|']
    for layer, result in results:
        folder = root / layer.id
        data_name = layer.id + '.parquet'
        assets = {'data': asset(folder / data_name, './' + data_name, 'application/vnd.apache.parquet', 'data')}
        (folder / 'VALIDATION.md').write_text(guide, encoding='utf-8')
        assets['validation-guide'] = asset(folder / 'VALIDATION.md', './VALIDATION.md', 'text/markdown', 'metadata')
        columns = [{'name': f.name, 'type': result['types'].get(f.name, f.type),
                    'description': f.description or f.title or f.name} for f in layer.fields if f.include]
        columns.append({'name': 'portolan_id', 'type': 'string', 'description': 'Unique identifier within this export.'})
        collection = {'type': 'Collection', 'stac_version': '1.1.0',
            'stac_extensions': [PROFILE, EXTENSIONS['file'], EXTENSIONS['table']],
            'id': layer.id, 'title': layer.title, 'description': layer.description,
            'license': inherited(plan, layer, 'license'), 'providers': providers(plan, layer),
            'extent': {'spatial': {'bbox': [result['bbox']]}, 'temporal': {'interval': [[layer.start or None, layer.end or None]]}},
            'links': [link('root', '../catalog.json'), link('parent', '../catalog.json')] + doc_links(),
            'assets': assets, 'table:columns': columns, 'table:row_count': result['count'],
            'keywords': [s.strip() for s in (layer.keywords or plan.keywords).split(',') if s.strip()]}
        if inherited(plan, layer, 'producer') != inherited(plan, layer, 'host'):
            collection['links'].append(link('via', inherited(plan, layer, 'source_url'), 'text/html'))
            collection['updated'] = now
            if inherited(plan, layer, 'canonical_url'):
                collection['links'].append(link('canonical', inherited(plan, layer, 'canonical_url')))
        if collection['license'] == 'other':
            collection['links'].append(link('license', inherited(plan, layer, 'license_url'), 'text/html'))
        if layer.pmtiles:
            collection['stac_extensions'].append(EXTENSIONS['web'])
            collection['links'].append(link('pmtiles', './' + layer.id + '.pmtiles', 'application/vnd.pmtiles',
                                            **{'pmtiles:layers': [layer.id]}))
            assets['style'] = asset(folder / 'styles/default.json', './styles/default.json',
                                    'application/vnd.mapbox.style+json', 'style')
        if (folder / 'thumbnail.png').exists():
            assets['thumbnail'] = asset(folder / 'thumbnail.png', './thumbnail.png', 'image/png', 'thumbnail')
        write_json(folder / 'collection.json', collection)
        total += result['count']
        root_lines.append(f'| [{escape(layer.title)}]({layer.id}/README.md) | {result["count"]} |')
        catalog['links'].append(link('child', './' + layer.id + '/collection.json', title=layer.title))
        count_label = '確認済み地物数' if japanese else 'Verified feature count'
        lines = [f'# {layer.title}', '', layer.description, '', f'{count_label}: {result["count"]}',
            f'CRS: {result["crs"]}', d('License: ', 'ライセンス: ') + collection['license'],
            d('Producer: ', '作成者: ') + inherited(plan, layer, 'producer'), d('Host: ', '管理者: ') + inherited(plan, layer, 'host'),
            d('Contact: ', '連絡先: ') + inherited(plan, layer, 'contact'),
            d('Source: ', '出典: ') + (inherited(plan, layer, 'source_url') or d('Self-produced', '自ら作成したデータ')),
            d('Time: ', '対象期間: ') + f'{layer.start or d("Unknown", "不明")} / {layer.end or d("Unknown", "不明")}', '',
            '## 属性' if japanese else '## Fields', '',
            d('| Name | Type | Description | Unit | Null | Codes |', '| 列名 | 型 | 説明 | 単位 | 欠損値 | コード値 |'), '|---|---|---|---|---|---|']
        for f in layer.fields:
            if f.include:
                lines.append('| ' + ' | '.join(escape(x) for x in (f.name, result['types'].get(f.name, f.type), f.description or f.title, f.unit, f.null_meaning, f.codes)) + ' |')
        lines += ['', '## 処理と制約' if japanese else '## Processing and limitations', '',
            d(f'Scope: {layer.scope}; repaired: {result["repaired"]}; omitted empty geometries: {result["skipped"]}.',
              f'抽出方法: {layer.scope}、修復件数: {result["repaired"]}、空ジオメトリの除外件数: {result["skipped"]}。'),
            d('Current edits, selected published fields and evaluated field values were captured at export time.',
              '出力時点の編集内容、公開対象列、評価済み属性値を固定して作成しました。'),
            plan.notes, layer.notes, '', '## 確認済み統計' if japanese else '## Verified statistics', '',
            '```json', __import__('json').dumps(result['statistics'], ensure_ascii=False, indent=2), '```']
        lines += ['', notice]
        (folder / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        agents = [f'# {layer.title}', '', f'{count_label}: {result["count"]}.',
            f'分析には `{data_name}` を使用してください。' if japanese else f'Use `{data_name}` for analysis.',
            '列の意味と確認済み統計はREADME.mdを参照してください。' if japanese else 'Read README.md for field meanings and verified statistics.',
            f'CRS: {result["crs"]}.',
            '経緯度の度をメートルとして扱わないでください。' if japanese else 'Do not interpret geographic degrees as metres.',
            d('portolan_id is unique within this export, not a stable identifier across exports.',
              'portolan_idは今回の出力内の一意キーです。再作成をまたぐ不変性は保証しません。'),
            d('License: ', 'ライセンス: ') + collection['license'], layer.notes]
        if layer.pmtiles:
            agents += [d('Visualization: ', '地図表示: ') + f'`{layer.id}.pmtiles`, `styles/default.json`.',
                       d('Tiles are simplified and clipped; do not use tile geometry for measurement.',
                         'タイルは簡略化・切抜きされるため、計測にはGeoParquetを使用してください。')]
        agents.append(notice)
        (folder / 'AGENTS.md').write_text('\n\n'.join(agents) + '\n', encoding='utf-8')
    root_lines += ['', plan.notes, '', d('Total verified features: ', 'カタログ全体の確認済み地物数: ') + str(total)]
    root_lines += ['', notice]
    (root / 'README.md').write_text('\n'.join(root_lines) + '\n', encoding='utf-8')
    (root / 'AGENTS.md').write_text(f'# {plan.title}\n\n' + d('Total verified features: ', 'カタログ全体の確認済み地物数: ') + str(total) + '\n\n' + '\n'.join(
        f'- [{layer.title}]({layer.id}/AGENTS.md)' for layer, _ in results) + '\n\n' +
        d('Read each collection guide before combining data.', 'データを組み合わせる前に、各Collectionの利用ガイドを確認してください。') + '\n\n' + notice + '\n', encoding='utf-8')
    write_json(root / 'catalog.json', catalog)

def escape(text):
    return str(text).replace('|', '\\|').replace('\n', ' ')
