# Changelog

このプロジェクトに対するすべての主な変更はこのファイルに記録されます。

フォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に基づいており、
このプロジェクトは [セマンティック バージョニング](https://semver.org/lang/ja/) に準拠しています。

## [Unreleased]

## [0.2.0] - 2026-11-04

### Added

- `crawl` の一覧表示テーブルにメールを識別する「ID」列を追加。
- メールIDを指定してメール詳細および本文を表示する `read` コマンドを追加（`--account` / `-a` オプションによるアカウント指定にも対応）。

## [0.1.0] - 2026-11-04

### Added

- プロジェクトの初期セットアップ（Python 3.13+、`uv_build` 構成）。
- `imapper-profiles.yaml` から複数のIMAPサーバー接続プロファイルを読み込む機能を追加。
- `.env` ファイルの自動読み込み（`python-dotenv`）をサポート。
- `crawl` コマンドおよび `--days-delta` オプションによるCLIインターフェースを実装。
- `IMAPClient` を使用して `INBOX` 内の未読メール（`UNSEEN`）および指定日数以降の未読メールを検索・フェッチする機能を実装。
- MIMEエンコードされたメールヘッダー（差出人表示名など）のデコード処理を実装。
- `rich` の `Table` を用いた未読メール一覧（Subject / Sender / Date）のコンソール出力機能を実装。
