import argparse
from datetime import date, timedelta
from email.header import decode_header

import yaml
from dotenv import load_dotenv
from imapclient import IMAPClient
from rich.console import Console
from rich.table import Table

console = Console()
profiles = {}

def obtain_profiles():
    global profiles
    profile_path = './imapper-profiles.yaml'
    with open(profile_path, 'r', encoding='utf-8') as f:
        profiles = yaml.safe_load(f)

def parse_header_str(data: bytes | str | None) -> str:
    """MIMEエンコードされた文字列をデコードして通常の文字列にする"""
    if not data:
        return ""
    # バイト列なら文字列に変換（未デコードのヘッダー文字列）
    if isinstance(data, bytes):
        text = data.decode("utf-8", errors="replace")
    else:
        text = data

    decoded_fragments = decode_header(text)
    result = []
    for fragment, charset in decoded_fragments:
        if isinstance(fragment, bytes):
            result.append(fragment.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(fragment)
    return "".join(result)

def crawl(days_delta: int):

    for key in profiles:
        console.print(f"Server: {key}")
        server_setting = profiles[key]

        client = IMAPClient(host = server_setting['server'])
        client.login(server_setting['user'], server_setting['password'])
        result = client.select_folder('INBOX')
        messages = client.search(['UNSEEN'])
    
        console.print(f"Unseen messages {len(messages)}")

        since_date = date.today() - timedelta(days=days_delta)
        criteria = ['UNSEEN', 'SINCE', since_date]
        messages = client.search(criteria)
        console.print(f"Unseen messages since {since_date}: {len(messages)}")

        table = Table(title = 'Unreaded mails')

        table.add_column("Subject", style="dim", width=60)
        table.add_column("Sender", style="dim", width=20)
        table.add_column("Date", style="dim", width=10)

        if messages:
            response = client.fetch(messages, ['ENVELOPE']) 

            for msg_id, data in response.items():
                envelope = data[b'ENVELOPE']
                date_str = envelope.date.strftime("%Y-%m-%d %H:%M:%S")
                subject = (
                    envelope.subject.decode(errors="replace")
                    if envelope.subject
                    else "(No Subject)"
                ) 
                if envelope.from_:
                    sender = envelope.from_[0]
                    # 1. 差出人名 (表示名)
                    sender_name = parse_header_str(sender.name)

                    # 2. メールアドレス (mailbox @ host)
                    mailbox = sender.mailbox.decode(errors="replace") if sender.mailbox else ""
                    host = sender.host.decode(errors="replace") if sender.host else ""
                    sender_email = f"{mailbox}@{host}" if mailbox and host else ""

                    # 表示名があれば「名前 <アドレス>」、なければアドレスのみ
                    display_sender = (
                        f"{sender_name} <{sender_email}>" if sender_name else sender_email
                    )
                else:
                    display_sender = '(No sender)'                
 
                hed_date = date_str
                table.add_row(subject, display_sender, hed_date)

        console.print(table)        

def main() -> None:
    load_dotenv()

    obtain_profiles()

    parser = argparse.ArgumentParser()
    parser.add_argument('command', type=str, choices=['crawl'], help='')
    parser.add_argument('--days-delta', type=int, default=1, help='')
    args = parser.parse_args()

    if args.command == 'crawl':
        days_delta = args.days_delta
        crawl(days_delta)

if __name__ == "__main__":
    main()
