#!/usr/bin/env python3
"""
import_recent_comments.py
Importar comentarios recientes (≤60 días) con deduplicación.
"""
import os
import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from supabase import create_client, Client
from dotenv import load_dotenv
import pytz
import time

def _int_env(var_name, default):
    """Lee una variable de entorno entera con manejo seguro de errores."""
    value = os.environ.get(var_name)
    if value is None:
        return default
    value = value.strip()
    if value == '':
        return default
    try:
        return int(value)
    except ValueError:
        return default

def load_env():
    load_dotenv()
    
    # Limpieza de variables sensibles
    yt_refresh_token = os.environ["YT_REFRESH_TOKEN"].strip()
    yt_client_id = os.environ["YT_CLIENT_ID"].strip()
    yt_client_secret = os.environ["YT_CLIENT_SECRET"].strip()
    supabase_url = os.environ["SUPABASE_URL"].strip()
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"].strip()
    
    # Validación básica de URL
    if not supabase_url.startswith(('http://', 'https://')):
        raise ValueError("SUPABASE_URL no comienza con http:// o https://")
    if any(c.isspace() for c in supabase_url):
        print("Advertencia: SUPABASE_URL contenía espacios internos (se usó versión limpia)")
    
    creds = Credentials(
        token=None,
        refresh_token=yt_refresh_token,
        client_id=yt_client_id,
        client_secret=yt_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )
    
    max_videos = _int_env("MAX_VIDEOS_PER_RUN", 50)
    max_comments = _int_env("MAX_COMMENTS_PER_VIDEO", 500)
    return creds, supabase_url, supabase_key, max_videos, max_comments

def init_clients(creds, supabase_url, supabase_key):
    yt = build("youtube", "v3", credentials=creds)
    sb: Client = create_client(supabase_url, supabase_key)
    return yt, sb

def get_recent_videos(sb: Client, limit=200):
    # FIX 2025-11-03: Obtener videos por published_at (no imported_at) para obtener videos más recientes
    # que probablemente tengan más comentarios activos
    return sb.table("videos").select("video_id").order("published_at", desc=True).limit(limit).execute()

def parse_iso_datetime(dt_str):
    formats = [
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%dT%H:%M:%SZ'
    ]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(dt_str, fmt).replace(tzinfo=pytz.UTC)
        except ValueError:
            continue
    raise ValueError(f"Invalid datetime format: {dt_str}")

def fetch_comments_for_video(yt, video_id, max_results):
    comments = []
    next_page_token = None
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=60)
    
    while len(comments) < max_results:
        try:
            response = yt.commentThreads().list(
                part="snippet,replies",
                videoId=video_id,
                maxResults=min(100, max_results - len(comments)),
                pageToken=next_page_token,
                order="time",
                textFormat="plainText"
            ).execute()
        except HttpError as e:
            if e.resp.status in [403, 429, 500, 502, 503, 504]:
                print(f"HTTP error {e.resp.status}, skipping video {video_id}: {str(e)}")
                break
            else:
                raise
        except Exception as e:
            print(f"General error fetching comments: {str(e)}")
            break
        
        page_comments = 0
        for item in response.get("items", []):
            if len(comments) >= max_results:
                break
                
            top_comment = item["snippet"]["topLevelComment"]
            top_snippet = top_comment["snippet"]
            try:
                published_at = parse_iso_datetime(top_snippet["publishedAt"])
            except ValueError:
                continue
                
            if published_at < cutoff:
                continue
                
            comment_id = top_comment["id"]
            comments.append(process_comment(top_snippet, comment_id, video_id))
            page_comments += 1
            
            replies = item.get("replies", {}).get("comments", [])
            for reply in replies:
                if len(comments) >= max_results:
                    break
                reply_snippet = reply["snippet"]
                try:
                    reply_published = parse_iso_datetime(reply_snippet["publishedAt"])
                except ValueError:
                    continue
                if reply_published >= cutoff:
                    reply_id = reply["id"]
                    comments.append(process_comment(reply_snippet, reply_id, video_id, top_comment["id"]))
                    page_comments += 1
        
        next_page_token = response.get("nextPageToken")
        if not next_page_token or page_comments == 0:
            break
        
        time.sleep(0.1)  # Quota management
    
    return comments

def process_comment(snippet, comment_id, video_id, parent_id=None):
    published_at = snippet["publishedAt"]
    return {
        "video_id": video_id,
        "comment_id": comment_id,
        "parent_id": parent_id,
        "author_display_name": snippet.get("authorDisplayName"),
        "author_channel_url": snippet.get("authorChannelUrl"),
        "text_original": snippet.get("textOriginal") or snippet.get("textDisplay", ""),
        "like_count": snippet.get("likeCount", 0),
        "published_at": published_at,
        "updated_at": snippet.get("updatedAt", published_at),
        "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat()  # FIX: Sin +Z (ya incluye +00:00)
    }

def upsert_comments(sb: Client, comments):
    if not comments:
        return
    
    for comment in comments:
        try:
            # FORZADO 2025-10-31: on_conflict STRING "comment_id" NO ["comment_id"]
            sb.table("comments").upsert(comment, on_conflict="comment_id").execute()
        except Exception as e:
            print(f"Error upserting comment {comment['comment_id']}: {str(e)}")

def main():
    creds, supabase_url, supabase_key, max_videos, max_comments = load_env()
    yt, sb = init_clients(creds, supabase_url, supabase_key)
    
    recent_videos = get_recent_videos(sb)
    print(f"Found {len(recent_videos.data)} recent videos")
    
    for idx, video in enumerate(recent_videos.data[:max_videos]):
        video_id = video["video_id"]
        print(f"Processing video {idx+1}/{min(len(recent_videos.data), max_videos)}: {video_id}")
        
        try:
            comments = fetch_comments_for_video(yt, video_id, max_comments)
            if comments:
                upsert_comments(sb, comments)
            print(f"  Imported {len(comments)} comments")
        except Exception as e:
            print(f"  Failed to process video {video_id}: {str(e)}")
        
        time.sleep(1)  # Quota management

if __name__ == "__main__":
    main()
