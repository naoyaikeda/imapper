import argparse
import email
from datetime import date, timedelta
from email import policy
from email.header import decode_header

import yaml
from dotenv import load_dotenv
from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from auth import exauth
from auth import gauth

console = Console()
profiles = {}


def obtain_profiles():
    global profiles
    profile_path = "./imapper-profiles.yaml"
    with open(profile_path, "r", encoding="utf-8") as f:
        profiles = yaml.safe_load(f) or {}


def save_profiles():
    profile_path = "./imapper-profiles.yaml"
    with open(profile_path, "w", encoding="utf-8") as f:
        yaml.dump(profiles, f, allow_unicode=True)


def add_exchange_account():
    exchange_auth = exauth.ExchangeAuth()

    account_info = {}
    profile_name = input("Profile name: ")
    account_info["mode"] = "exchange"
    account_info["address"] = input("Enter email address: ")
    account_info["user"] = account_info["address"]
    account_info["server"] = "outlook.office365.com"

    device_flow = exchange_auth.request_device_code()
    message = device_flow.get(
        "message",
        f"Open {device_flow.get('verification_uri')} and enter code: {device_flow.get('user_code')}",
    )
    console.print(Panel(message, title="Exchange OAuth2 Device Login", expand=False))
    console.print("Waiting for authorization in browser...")

    access_token_response = exchange_auth.poll_for_token(device_flow)
    account_info["password"] = access_token_response["access_token"]
    account_info["refresh_token"] = access_token_response.get("refresh_token", "")

    profiles[profile_name] = account_info
    save_profiles()
    console.print(
        f"[bold green]Successfully added Exchange profile '{profile_name}'.[/]"
    )


def _authenticate_client(client: IMAPClient, server_setting: dict) -> bool:
    login_mode = server_setting.get("mode", "standard")
    if login_mode == "standard":
        client.login(server_setting["user"], server_setting["password"])
        return True
    elif login_mode == "oauth2":
        client.oauth2_login(server_setting["user"], server_setting["password"])
        return True
    elif login_mode == "exchange":
        try:
            client.oauth2_login(server_setting["user"], server_setting["password"])
        except IMAPClientError:
            refresh_token = server_setting.get("refresh_token")
            if not refresh_token:
                raise
            exchange_auth = exauth.ExchangeAuth()
            token_resp = exchange_auth.refresh_access_token(refresh_token)
            server_setting["password"] = token_resp["access_token"]
            if "refresh_token" in token_resp:
                server_setting["refresh_token"] = token_resp["refresh_token"]
            save_profiles()
            client.oauth2_login(server_setting["user"], server_setting["password"])
        return True
    else:
        console.print("Illegal login mode")
        return False


def _decode_bytes(raw: bytes, charset: str | None = None) -> str:
    """バイト列を指定文字コードまたはISO-2022-JP/UTF-8でデコードする"""
    if charset:
        try:
            return raw.decode(charset, errors="replace")
        except LookupError:
            pass
    for encoding in ("iso-2022-jp", "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_header_str(data: bytes | str | None) -> str:
    """MIMEエンコードされた文字列やバイト列をデコードして通常の文字列にする"""
    if not data:
        return ""
    # バイト列なら文字列に変換（未デコードのヘッダー文字列）
    if isinstance(data, bytes):
        text = _decode_bytes(data)
    else:
        text = data

    decoded_fragments = decode_header(text)
    result = []
    for fragment, charset in decoded_fragments:
        if isinstance(fragment, bytes):
            result.append(_decode_bytes(fragment, charset))
        else:
            result.append(fragment)
    return "".join(result)


def crawl(days_delta: int):
    for key, server_setting in profiles.items():
        console.print(f"Server: {key}")

        client = IMAPClient(host=server_setting["server"])

        if not _authenticate_client(client, server_setting):
            break

        client.select_folder("INBOX")
        status = client.folder_status("INBOX", ["UNSEEN"])
        unseen_count = status.get(b"UNSEEN", 0)

        console.print(f"Unseen messages {unseen_count}")

        since_date = date.today() - timedelta(days=days_delta)
        criteria = ["UNSEEN", "SINCE", since_date]
        messages = client.search(criteria)
        console.print(f"Unseen messages since {since_date}: {len(messages)}")

        table = Table(title="Unreaded mails")

        table.add_column("ID", style="bold cyan", width=10)
        table.add_column("Subject", style="dim", width=60)
        table.add_column("Sender", style="dim", width=20)
        table.add_column("Date", style="dim", width=10)

        if messages:
            response = client.fetch(messages, ["ENVELOPE"])

            for msg_id, data in response.items():
                envelope = data[b"ENVELOPE"]
                date_str = envelope.date.strftime("%Y-%m-%d %H:%M:%S")
                subject = (
                    parse_header_str(envelope.subject)
                    if envelope.subject
                    else "(No Subject)"
                )
                if envelope.from_:
                    sender = envelope.from_[0]
                    # 1. 差出人名 (表示名)
                    sender_name = parse_header_str(sender.name)

                    # 2. メールアドレス (mailbox @ host)
                    mailbox = (
                        sender.mailbox.decode(errors="replace")
                        if sender.mailbox
                        else ""
                    )
                    host = sender.host.decode(errors="replace") if sender.host else ""
                    sender_email = f"{mailbox}@{host}" if mailbox and host else ""

                    # 表示名があれば「名前 <アドレス>」、なければアドレスのみ
                    display_sender = (
                        f"{sender_name} <{sender_email}>"
                        if sender_name
                        else sender_email
                    )
                else:
                    display_sender = "(No sender)"

                hed_date = date_str
                table.add_row(str(msg_id), subject, display_sender, hed_date)

        console.print(table)


def extract_body(msg: email.message.EmailMessage) -> str:
    """メールメッセージから本文テキストを抽出する"""
    body_part = msg.get_body(preferencelist=("plain", "html"))
    if body_part:
        try:
            return body_part.get_content()
        except (LookupError, UnicodeError, AttributeError, ValueError):
            return str(body_part.get_payload(decode=True) or "")

    # プレーンテキスト/HTMLパートが見つからない場合のフォールバック
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" not in content_disposition and content_type in [
                "text/plain",
                "text/html",
            ]:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    parts.append(payload.decode(charset, errors="replace"))
        if parts:
            return "\n\n".join(parts)
        return "(No readable body)"
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
        return str(msg.get_payload() or "")


def read_mail(msg_id_str: str, account: str | None = None) -> bool:
    """指定されたIDのメールを取得して表示する"""
    try:
        msg_id = int(msg_id_str)
    except ValueError:
        console.print(f"[bold red]Error:[/] Invalid message ID: {msg_id_str}")
        return False

    targets = {}
    if account:
        if account not in profiles:
            console.print(f"[bold red]Error:[/] Profile '{account}' not found.")
            return False
        targets[account] = profiles[account]
    else:
        targets = profiles

    for key, server_setting in targets.items():
        try:
            client = IMAPClient(host=server_setting["server"])
            if not _authenticate_client(client, server_setting):
                break

            client.select_folder("INBOX")

            fetch_data = client.fetch([msg_id], ["BODY[]", "RFC822", "FLAGS"])
            if msg_id in fetch_data:
                raw_bytes = fetch_data[msg_id].get(b"BODY[]") or fetch_data[msg_id].get(
                    b"RFC822"
                )
                if raw_bytes:
                    msg = email.message_from_bytes(raw_bytes, policy=policy.default)
                    subject = str(msg["subject"] or "(No Subject)")
                    from_addr = str(msg["from"] or "(No sender)")
                    to_addr = str(msg["to"] or "(No recipient)")
                    date_header = str(msg["date"] or "(No date)")

                    body = extract_body(msg)

                    header_info = (
                        f"[bold]Account:[/] {key}\n"
                        f"[bold]ID:[/] {msg_id}\n"
                        f"[bold]Date:[/] {date_header}\n"
                        f"[bold]From:[/] {from_addr}\n"
                        f"[bold]To:[/] {to_addr}\n"
                        f"[bold]Subject:[/] {subject}"
                    )
                    console.print(
                        Panel(header_info, title="Message Info", expand=False)
                    )
                    console.print(Panel(body, title="Body", expand=False))
                    return True
        except (IMAPClientError, OSError) as e:
            console.print(f"[dim]Failed to query server '{key}': {e}[/]")

    console.print(f"[bold red]Message with ID {msg_id} not found.[/]")
    return False


def main() -> None:
    load_dotenv()

    obtain_profiles()

    parser = argparse.ArgumentParser(prog="imapper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl_parser = subparsers.add_parser("crawl", help="Crawl unread emails")
    crawl_parser.add_argument(
        "--days-delta", type=int, default=1, help="Number of days delta"
    )

    read_parser = subparsers.add_parser("read", help="Read email by ID")
    read_parser.add_argument("id", type=str, help="Message ID")
    read_parser.add_argument(
        "--account", "-a", type=str, default=None, help="Account profile name"
    )

    add_account_parser = subparsers.add_parser("add", help="Add account")
    add_account_parser.add_argument(
        "type", type=str, choices=["exchange"], help="Account type"
    )

    args = parser.parse_args()

    if args.command == "crawl":
        days_delta = args.days_delta
        crawl(days_delta)
    elif args.command == "add":
        account_type = args.type
        if account_type == "exchange":
            add_exchange_account()
    elif args.command == "read":
        read_mail(args.id, args.account)


if __name__ == "__main__":
    main()
