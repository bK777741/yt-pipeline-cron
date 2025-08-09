#!/usr/bin/env python3
"""
import_recent_comments.py
Importar comentarios recientes (≤60 días) con deduplicación.
"""
import os
import datetime
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from supabase import create_client, Client
from dotenv import load_dotenv
import pytz
import time

def load_env():
    load_dotenv()
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"]
    max_videos = int(os.environ.get("MAX_VIDEOS_PER_RUN", 50))
    max_comments = int(os.environ.get("MAX_COMMENTS_PER_VIDEO", 200))
    return creds, supabase_url, supabase_key, max_videos, max_comments

def init_clients(creds, supabase_url, supabase_key):
    yt = build("youtube", "v3", credentials=creds)
    sb: Client = create_client(supabase_url, supabase_key)
    return yt, sb

def get_recent_videos(sb: Client, days=60):
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    return sb.table("videos").select("video_id").gt("published_at", cutoff.isoformat()).execute()

def fetch_comments_for_video(yt, video_id, max_results):
    comments = []
    next_page_token = None
    
    while True:
        try:
            response = yt.commentThreads().list(
                part="snippet,replies",
                videoId=video_id,
                maxResults=max_results,
                pageToken=next_page_token,
                textFormat="plainText"
            ).execute()
        except Exception as e:
            print(f"Error fetching comments: {str(e)}")
            break
        
        for item in response["items"]:
            top_comment = item["snippet"]["topLevelComment"]
            comments.append(process_comment(top_comment["snippet"], video_id))
            
            if "replies" in item:
                for reply in item["replies"]["comments"]:
                    comments.append(process_comment(reply["snippet"], video_id, top_comment["id"]))
        
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break
    
    return comments

def process_comment(snippet, video_id, parent_id=None):
    return {
        "video_id": video_id,
        "comment_id": snippet["id"],
        "parent_id": parent_id,
        "author_display_name": snippet["authorDisplayName"],
        "author_channel_url": snippet["authorChannelUrl"],
        "text_original": snippet["textOriginal"],
        "like_count": snippet["likeCount"],
        "published_at": snippet["publishedAt"],
        "updated_at": snippet["updatedAt"],
        "checked_at": datetime.datetime.utcnow().isoformat() + "Z"
    }

def upsert_comments(sb: Client, comments):
    if not comments:
        return
    
    for comment in comments:
        sb.table("comments").upsert(comment, on_conflict="comment_id").execute()

def main():
    creds, supabase_url, supabase_key, max_videos, max_comments = load_env()
    yt, sb = init_clients(creds, supabase_url, supabase_key)
    
    recent_videos = get_recent_videos(sb)
    print(f"Found {len(recent_videos.data)} recent videos")
    
    for idx, video in enumerate(recent_videos.data[:max_videos]):
        video_id = video["video_id"]
        print(f"Processing video {idx+1}/{min(len(recent_videos.data), max_videos)}: {video_id}")
        
        comments = fetch_comments_for_video(yt, video_id, max_comments)
        upsert_comments(sb, comments)
        print(f"  Imported {len(comments)} comments")
        
        time.sleep(1)  # Quota management

if __name__ == "__main__":
    main()
