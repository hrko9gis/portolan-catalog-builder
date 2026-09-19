# 詳細検証の手順

カタログ作成時には基本チェックのみを実施します。Portolan/STAC仕様への適合性と
実データの詳細検証は**未実施**です。公開・配布前に、データの所有者または公開担当者が
以下の確認を行ってください。

## 1. QGISとは別の環境を準備する

QGISのPython環境へ検証ライブラリをインストールしないでください。
uvを利用できる別の端末または独立したツール環境で、以下を実行します。

```text
uv tool install "rashid==0.1.8"
```

uvの導入方法：https://docs.astral.sh/uv/getting-started/installation/
初回の取得にはインターネット接続と、環境に対応するPythonパッケージが必要です。
rashidが見つからない場合はuvのPATH設定の案内に従ってください。
この手順はrashid 0.1.8・Portolan 0.2.0を対象とします。実際の依存関係のバージョンも記録します。

## 2. カタログ全体を検証する

OUTPUT_FOLDERをcatalog.jsonがあるフォルダーへ置き換えます。
生成したファイルとサブフォルダーの構成を維持し、QGISの外で実行してください。

```text
rashid check "OUTPUT_FOLDER" --schema --data-scope local
```

レポートを保存する場合は、カタログの外のフォルダーで次を実行します。

```text
rashid check "OUTPUT_FOLDER" --schema --data-scope local --json > validation-report.json
```

エラーを修正し、警告、ルールID、検査のスキップも確認してください。
終了コード0だけでは全検査が完了したと判断できません。依存ライブラリ不足や
検査不能を成功として扱わないでください。PMTilesを省略した場合には推奨事項の警告が出ることがあります。
データやカタログを変更した場合は再検証します。

## 3. 目視でデータを確認する

QGISで属性、形状、CRS、範囲を確認します。PMTilesを作成した場合は複数のズームで
プレビューを確認します。簡略化やタイル境界での切抜きにより、タイルの地物数と
GeoParquetの件数は一致しない場合があります。分析にはGeoParquetを使用してください。

## 4. 公開後に配信設定を確認する

例のURLを、実際のカタログの公開ベースURLへ置き換えます。

```text
rashid check "OUTPUT_FOLDER" --schema --data-scope local --live --live-base-url "https://data.example.org/my-catalog/"
```

公開先へ通信し、HTTP RangeやCORSなどを調べます。ローカルの検査だけでは配信設定は確認できません。
レポートはカタログの外に保存してください。プラグインは外部の検証結果を自動取り込みせず、
検証済みへ自動変更しません。この文書は作成時点の状態を示します。

参照：https://github.com/portolan-sdi/rashid
