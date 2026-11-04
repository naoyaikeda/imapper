# imapper

複数のIMAPサーバーから未読メールを取得し、ターミナル上にテーブル形式で一覧表示するCLIツールです。

## 特徴

- `imapper-profiles.yaml` による複数IMAPアカウントの一括管理
- 指定日数以内（デフォルト: 1日前以降）の未読メール（`UNSEEN`）を検索
- MIMEエンコードされた差出人名などのデコードに対応
- [Rich](https://github.com/Textualize/rich) を用いた見やすいテーブル出力（件名・差出人・日時）

## 必要要件

- Python 3.13 以上
- [uv](https://docs.astral.sh/uv/)（推奨パッケージマネージャー）

## セットアップ

1. 依存パッケージのインストール:

```bash
uv sync
```

2. プロファイル設定ファイルの作成:

プロジェクトルート（実行時のカレントディレクトリ）に `imapper-profiles.yaml` を作成し、接続先のIMAPサーバー情報を記述します（このファイルは `.gitignore` によりGit管理対象外となっています）。

```yaml
example_account:
  server: imap.example.com
  user: user@example.com
  password: your_password

another_account:
  server: mail.example.org
  user: account@example.org
  password: your_secret_password
```

必要に応じて環境変数ファイル `.env` も配置できます（起動時に自動で読み込まれます）。

## 使い方

### 未読メールのクロール (`crawl`)

登録されているすべてのプロファイルの `INBOX` を巡回し、未読メールの一覧を表示します。

```bash
# デフォルト（過去1日以内の未読メールを取得）
uv run imapper crawl

# 過去7日以内の未読メールを取得
uv run imapper crawl --days-delta 7
```

### コマンドライン引数

| 引数 / オプション | 説明 | デフォルト値 |
| :--- | :--- | :--- |
| `crawl` | 各プロファイルのIMAPサーバーから未読メールを取得して表示するサブコマンド | （必須） |
| `--days-delta <int>` | 今日から何日前以降の未読メールを検索対象とするかを指定 | `1` |

## 開発

リンター / フォーマッターとして [Ruff](https://docs.astral.sh/ruff/) を使用しています。

```bash
uv run ruff check .
uv run ruff format .
```
