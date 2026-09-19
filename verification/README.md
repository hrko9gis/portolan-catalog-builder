# 0.2.0 検証結果・残作業

確認日：2026年9月17日（日本時間）。ここにあるログとレポートは、確認済みの証拠としてソースと一緒に保管します。

## 最終配布ZIPと結果

- ファイル：`dist/portolan_catalog_builder-0.2.0.zip`
- 容量：427,716 bytes（約0.43 MB）
- SHA-256：`5aa2432693b2eb24c853129eb5818359021a0c96d01a641d48e436d2108a065c`
- 環境：Windows x64、QGIS 3.44.13、Python 3.12、GDAL 3.13.2
- [実行結果一覧・コマンド・終了コード](release-0.2.0-20260917-084100/results.json)

| 検査 | 結果 | 証拠 |
| --- | --- | --- |
| ZIP公開前チェック | 成功。サイズ上限・必須ファイル・ネイティブバイナリ非同梱 | [ログ](release-0.2.0-20260917-084100/publication.log) |
| 自動テスト | 14件成功。展開済みZIPから実装を読み込み | [ログ](release-0.2.0-20260917-084100/unit-integration.log) |
| 英語GUI | 作成成功。詳細検証未実施表示とガイドを確認 | [ログ](release-0.2.0-20260917-084100/gui-en.log)・[画面](release-0.2.0-20260917-084100/gui-en.png) |
| 日本語GUI | 作成成功。詳細検証未実施表示とガイドを確認 | [ログ](release-0.2.0-20260917-084100/gui-ja.log)・[画面](release-0.2.0-20260917-084100/gui-ja.png) |
| PMTiles地図 | Edgeで実描画、JavaScript・地図エラーなし | [ログ](release-0.2.0-20260917-084100/browser.log)・[画面](release-0.2.0-20260917-084100/pmtiles-preview.png) |
| 外部詳細検証 | rashid 0.1.8、エラー0・警告0 | [JSONレポート](release-0.2.0-20260917-084100/external-validation.json) |

外部詳細検証は開発環境で別途実行しています。利用者向けプラグインが詳細検証を行ったことにはなりません。
出力の[作成レポート](release-0.2.0-20260917-084100/build-report-ja.json)には、引き続き `detailed_validation.status=not_run` と記録されます。

## QGIS本体での確認

専用プロファイルで実際のQGIS本体を非表示起動し、ZIPからの導入、有効化、画面と検証ガイドの表示、無効化がすべて成功しました。
確認はQGIS本体の `installFromZipFile` を使用し、マウス操作での手動試験とは区別します。
普段のQGISプロファイルは変更していません。
結果と対象ZIPハッシュは [QGIS ZIPインストーラーの記録](qgis-zip-installer.json) に保存しています。

初回は検証スクリプトがQGISの `--code` 実行環境で使えない `__file__` を参照し停止しました。
これはプラグインの不具合ではなく、検証スクリプトの不備です。修正前の結果も
[初回記録](qgis-zip-installer-attempt1.json)として残しています。

次の試行では起動時の作業ディレクトリからソースを読み込んでいたため、
[その記録](qgis-zip-installer-attempt2.json)は配布ZIPの成功証拠として採用していません。
読込先をインストールディレクトリへ限定して再実行し、最終記録では対象ZIPのハッシュ一致、
専用プロファイル内の読込先、`_vendor` が存在しないことを確認しています。

## 公開前に残っている作業

1. **GitHubへソース・READMEをアップロードする。** 公開リポジトリとIssues有効は確認済みですが、READMEの取得はHTTP 404でした。[確認結果](github-status.json)
2. **QGIS公式へ申請し、公式セキュリティスキャン・審査を受ける。** ローカルチェックの成功は公式承認ではありません。
3. **外部検証ツールの新規導入手順を試験する。** 今回の外部検証は既存開発環境を利用しており、uv未導入の端末からの初回導入は未検証です。

Linux・macOS・QGIS 4、独立したPortolan Browser、公開先のCORS/Range、大規模ポリゴンの性能は未検証です。
対応宣言や公開先が決まった段階でそれぞれ試験します。
詳細は [検証結果と残作業の説明](../docs/verification-ja.md) を参照してください。

## 再確認の方法

```text
python scripts/verify_release.py --qgis-python "C:/Program Files/QGIS 3.44.13/bin/python-qgis-ltr.bat"
```

実行ごとに新しいフォルダーへ証拠を保存します。過去のフォルダーは上書きしません。
`075433` の記録は文書更新前のZIPに対する成功記録です。最終ZIPの結果には `084100` を使用してください。
