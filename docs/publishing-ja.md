# QGIS公式プラグインリポジトリへの公開準備状況

[English](publishing.md)

2026年9月16日に、以下の公式ガイドと照合しました。

- [プラグインの公開要件](https://plugins.qgis.org/docs/publish)
- [承認手順](https://plugins.qgis.org/docs/approval)
- [Pythonプラグインの構成・メタデータ](https://docs.qgis.org/3.44/en/docs/pyqgis_developer_cookbook/plugins/plugins.html)

## ソースコードの公開先

作者のGitHubリポジトリ
[hrko9gis/portolan-catalog-builder](https://github.com/hrko9gis/portolan-catalog-builder)
を**公開リポジトリ**にし、ソースコードを閲覧できる形で掲載します。
不具合報告用のIssuesも有効にしてください。独立したウェブサイトは不要です。
ルートのREADMEで、インストール方法、使い方、対応環境、制約を説明しています。

`portolan_catalog_builder/metadata.txt` には、以下を設定済みです。

| 項目 | 設定値 |
| --- | --- |
| `homepage`（ホームページ） | `https://github.com/hrko9gis/portolan-catalog-builder#readme` |
| `repository`（コード公開先） | `https://github.com/hrko9gis/portolan-catalog-builder` |
| `tracker`（不具合報告先） | `https://github.com/hrko9gis/portolan-catalog-builder/issues` |
| `author`（作者名） | Kohei Hara |
| `email`（連絡先） | hrko9gis@gmail.com |

リポジトリURLと作者名には、作者から指定された情報を使用しています。
メールアドレスには、既存の
[GSI-AddressSearchの公開メタデータ](https://github.com/hrko9gis/GSI-AddressSearch/blob/main/metadata.txt)
に記載された連絡先を使用しています。
アップロード後には、新しいリポジトリとIssuesへ一般公開状態でアクセスできるか確認が必要です。
コード公開先にはZIPだけを置くのではなく、申請するバージョンに対応したソースコードを掲載してください。

公開用ファイルには、英語の利用説明、日本語の操作ガイド、設計書、検証記録、
GPLライセンス本文、第三者ライセンスの説明、変更履歴、人工的に作成したサンプルデータ、
テスト、ビルド手順が含まれています。これらをプラグインのソースコードとともにコミットします。
依存ライブラリと生成物をGit管理から除外する既存の設定は維持してください。

## バージョン0.2.0の配布構成

**検証用ネイティブライブラリを配布ZIPから除外する構成に変更しました。**

公式ガイドのバイナリ非同梱・25 MB以下という条件に対応するため、旧版で約84 MBあったZIPから `_vendor` を除外します。作成時の基本チェックは維持し、詳細検証は利用者が別環境で実施します。英語・日本語のガイドをプラグインと成果物に添付します。

環境チェックと出力確定条件からrashidの必須条件を外しています。カタログ作成は引き続きGUIで完結します。QGIS環境のGeoParquet対応GDALとPyArrow、PMTiles出力時の対応ドライバーは引き続き必要です。公式承認や公開リポジトリのアクセス確認は別途必要です。

Windows向けの配布構成については、他のOSへの対応と検証も必要です。
Linux、macOS、QGIS 4での動作は、現時点では検証していません。
未検証の環境への対応をうたわず、実際の制約をメタデータに記載してください。

## 申請前の確認

ソースコードのルートフォルダーで、以下の確認用スクリプトを実行します。

```text
python scripts/check_publication.py
python scripts/check_publication.py --zip dist/portolan_catalog_builder-0.2.0.zip
```

このスクリプトは、必須メタデータ、文書、ソースコードの構成を確認します。
ZIPを指定した場合は、ZIP内のメタデータ、容量、ネイティブバイナリの有無、必須ファイルも確認します。
作者情報やURL・連絡先が未設定の場合、ネイティブバイナリを同梱した場合、容量超過の場合には、
未解決事項を検出して失敗するようにしています。
このチェックは、公式のセキュリティスキャンや人による審査を代替するものではありません。
URLに一般公開状態でアクセスできるかどうかも確認しません。

アップロード前には、次の点を確認してください。

- GitHubからサインアウトした状態で、公開先のリンクを開けること。
- Issuesが有効になっていること。
- メタデータに未設定の項目が残っていないこと。
- 対応を表明する各環境でテストを実施していること。
- 申請するZIPと、公開するソースコードのバージョンが一致していること。
- 再配布するすべての依存ライブラリに、提供元のライセンス本文を含めていること。

最終的な承認は、QGISプラグインリポジトリの運営側が行います。
