# imapper

複数のIMAPサーバーから未読メールを取得し、ターミナル上にテーブル形式で一覧表示するCLIツールです。

## 特徴

- `imapper-profiles.yaml` による複数IMAPアカウントの一括管理
- 標準ログイン（`standard`）に加え、OAuth2認証（`oauth2`）およびMicrosoft Exchange Online（`exchange`：デバイスコードフローによるアカウント登録・トークン自動更新）に対応
- 指定日数以内（デフォルト: 1日前以降）の未読メール（`UNSEEN`）を検索
- MIMEエンコードされた件名や差出人名のデコード（UTF-8 / ISO-2022-JPフォールバック対応）
- [Rich](https://github.com/Textualize/rich) を用いた見やすいテーブル出力（ID・件名・差出人・日時）
- メールIDを指定してメールの詳細（ヘッダーおよび本文）を表示する `read` コマンド

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
  mode: standard  # 省略時は standard
  server: imap.example.com
  user: user@example.com
  password: your_password

oauth_account:
  mode: oauth2
  server: imap.example.org
  user: account@example.org
  password: your_oauth2_access_token

exchange_account:
  mode: exchange
  server: outlook.office365.com
  address: user@contoso.com
  user: user@contoso.com
  password: your_access_token
  refresh_token: your_refresh_token
```

3. 環境変数ファイル（`.env`）の設定（OAuth2利用時など）:

起動時に `.env` が自動で読み込まれます。Microsoft Exchange Online や Gmail の OAuth2 認証を利用する場合は、以下の環境変数を設定してください。

```dotenv
# Microsoft Exchange Online (Office 365) OAuth2
EXCHANGE_CLIENT_ID=your_azure_ad_client_id
EXCHANGE_CLIENT_SECRET=your_azure_ad_client_secret
EXCHANGE_TENANT_ID=common  # 省略時は common

# Google (Gmail) OAuth2
GMAIL_CLIENT_ID=your_google_client_id
GMAIL_CLIENT_SECRET=your_google_client_secret
```

## 使い方

### アカウントの追加 (`add`)

OAuth2 デバイスコードフローを使用して、対話形式で Microsoft Exchange Online アカウントを認証し、`imapper-profiles.yaml` に追加・保存します。

```bash
uv run imapper add exchange
```

### 未読メールのクロール (`crawl`)

登録されているすべてのプロファイルの `INBOX` を巡回し、未読メールの一覧を表示します。

```bash
# デフォルト（過去1日以内の未読メールを取得）
uv run imapper crawl

# 過去7日以内の未読メールを取得
uv run imapper crawl --days-delta 7
```

### メールの閲覧 (`read`)

メールID（`crawl` で表示されたID）を指定してメール詳細（差出人・宛先・件名・本文など）を表示します。

```bash
# メールIDを指定して閲覧（全プロファイルから検索）
uv run imapper read 12345

# プロファイル（アカウント）を指定して閲覧
uv run imapper read 12345 --account example_account
```

### コマンドライン引数

#### `crawl`

| 引数 / オプション | 説明 | デフォルト値 |
| :--- | :--- | :--- |
| `crawl` | 各プロファイルのIMAPサーバーから未読メールを取得して表示するサブコマンド | - |
| `--days-delta <int>` | 今日から何日前以降の未読メールを検索対象とするかを指定 | `1` |

#### `read`

| 引数 / オプション | 説明 | デフォルト値 |
| :--- | :--- | :--- |
| `read` | メールIDを指定してメール詳細を表示するサブコマンド | - |
| `<id>` | 表示するメールのメッセージID | （必須） |
| `--account <str>`, `-a <str>` | 検索対象のプロファイル名 | なし（全プロファイルを検索） |

#### `add`

| 引数 / オプション | 説明 | デフォルト値 |
| :--- | :--- | :--- |
| `add` | 新しいアカウントプロファイルを対話形式で追加するサブコマンド | - |
| `<type>` | 追加するアカウント種別（現在は `exchange` のみ対応） | （必須） |

## 開発

リンター / フォーマッターとして [Ruff](https://docs.astral.sh/ruff/) を使用しています。

```bash
# リントとフォーマット
uv run ruff check .
uv run ruff format .

# ユニットテストの実行
uv run python -m unittest discover -s tests
```
