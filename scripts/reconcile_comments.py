#!/usr/bin/env python3
"""
reconcile_comments.py
Sincroniza el estado de los comentarios borrados o moderados de YouTube (marca is_public=False).
"""

import os
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client

def load_env():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"].strip(),
        client_id=os.environ["YT_CLIENT_ID"].strip(),
        client_secret=os.environ["YT_CLIENT_SECRET"].strip(),
        token_uri="https://oauth2.googleapis.com/token",
    )
    supabase_url = os.environ["SUPABASE_URL"].strip()
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"].strip()
    return creds, supabase_url, supabase_key

def init_clients(creds, supabase_url, supabase_key):
    yt = build("youtube", "v3", credentials=creds)
    sb: Client = create_client(supabase_url, supabase_key)
    return yt, sb

def fetch_buffered_comments(sb: Client):
    resp = sb.table("comments").select("comment_id").execute()
    return [row["comment_id"] for row in resp.data]

def check_comment_status(yt, comment_id):
    req = yt.comments().list(part="id,snippet", id=comment_id)
    resp = req.execute()
    if not resp.get("items"):
        return False
    return True

def upsert_comment_status(sb: Client, comment_id, is_public: bool):
    sb.table("comments").upsert({
        "comment_id": comment_id,
        "is_public": is_public,
        "checked_at": "now()"
    }, on_conflict=["comment_id"]).execute()

def main():
    creds, supabase_url, supabase_key = load_env()
    yt, sb = init_clients(creds, supabase_url, supabase_key)

    all_comments = fetch_buffered_comments(sb)
    for cid in all_comments:
        public = check_comment_status(yt, cid)
        upsert_comment_status(sb, cid, public)

    print(f"[reconcile_comments] Comentarios verificados: {len(all_comments)}")

if __name__ == "__main__":
    main()
