#!/usr/bin/env python3
"""
reconcile_comments.py
Filtra comentarios spam y actualiza estado.
"""
import os
import re
from datetime import datetime, timedelta, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client

BLACKLIST = ["http", "www", "promo", "oferta", "gratis", "click", "visita", "comprar", "descuento", "spam"]

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

def is_spam(text, author_created_at):
    if not text:
        return False, ""
    
    # Detectar URLs
    if re.search(r"http\S+|www\.\S+", text, re.IGNORECASE):
        return True, "Contiene URL"
    
    # Detectar palabras prohibidas
    if any(word in text.lower() for word in BLACKLIST):
        return True, "Palabra prohibida"
    
    # Detectar canales nuevos (<30 días)
    # FIX 2025-11-20: Validar que author_created_at no sea None antes de comparar
    if author_created_at is not None and author_created_at > (datetime.now(timezone.utc) - timedelta(days=30)).isoformat():
        return True, "Canal nuevo"
    
    return False, ""

def fetch_author_info(yt, author_channel_id):
    try:
        channel = yt.channels().list(
            part="snippet",
            id=author_channel_id
        ).execute()
        if channel.get("items"):
            return channel["items"][0]["snippet"]["publishedAt"]
    except Exception:
        pass
    return None

def check_comment(yt, comment_id):
    try:
        comment = yt.comments().list(
            part="snippet",
            id=comment_id
        ).execute().get("items", [])
        if comment:
            snippet = comment[0]["snippet"]
            return {
                "text": snippet["textOriginal"],
                "author_channel_id": snippet["authorChannelId"]["value"],
                "is_public": True
            }
    except Exception:
        pass
    return None

def process_comments(yt, sb, comment_ids):
    for cid in comment_ids:
        data = check_comment(yt, cid)
        if not data:
            sb.table("comments").delete().eq("comment_id", cid).execute()
            continue
        
        author_created_at = fetch_author_info(yt, data["author_channel_id"])
        spam, reason = is_spam(data["text"], author_created_at)
        
        # Borrar si es spam
        if spam:
            sb.table("comments").delete().eq("comment_id", cid).execute()
        else:
            sb.table("comments").upsert({
                "comment_id": cid,
                "is_public": data["is_public"],
                "author_created_at": author_created_at,
                "is_spam": spam,
                "spam_reason": reason,
                "checked_at": "now()"
            }).execute()

def main():
    creds, supabase_url, supabase_key = load_env()
    yt, sb = init_clients(creds, supabase_url, supabase_key)
    
    # Obtener todos los comentarios
    resp = sb.table("comments").select("comment_id").execute()
    comment_ids = [row["comment_id"] for row in resp.data]
    
    process_comments(yt, sb, comment_ids)
    print(f"[reconcile_comments] Comentarios procesados: {len(comment_ids)}")

if __name__ == "__main__":
    main()
