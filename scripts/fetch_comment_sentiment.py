#!/usr/bin/env python3
"""
fetch_comment_sentiment.py
Realiza análisis de sentimiento en comentarios usando VADER.
"""
import os
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from supabase import create_client, Client
from datetime import datetime, timezone

# Descargar recursos necesarios para VADER
nltk.download('vader_lexicon', quiet=True)

def init_supabase():
    supabase_url = os.environ["SUPABASE_URL"].strip()
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"].strip()
    return create_client(supabase_url, supabase_key)

def analyze_sentiment(text):
    """Analiza el sentimiento del texto usando VADER"""
    analyzer = SentimentIntensityAnalyzer()
    scores = analyzer.polarity_scores(text)
    compound = scores['compound']
    
    if compound >= 0.05:
        sentiment = 'positive'
    elif compound <= -0.05:
        sentiment = 'negative'
    else:
        sentiment = 'neutral'
    
    return sentiment, compound

def main():
    sb = init_supabase()
    
    # Obtener comentarios no spam sin análisis de sentimiento
    response = sb.table('comments') \
        .select('comment_id, text_original') \
        .eq('is_spam', False) \
        .is_('sentiment', None) \
        .execute()
    
    comments = response.data
    if not comments:
        print("[fetch_comment_sentiment] No hay comentarios nuevos para analizar")
        return

    # Procesar cada comentario
    for comment in comments:
        text = comment['text_original']
        if not text:
            continue
            
        sentiment, score = analyze_sentiment(text)
        
        # Actualizar comentario en la base de datos
        sb.table('comments').update({
            'sentiment': sentiment,
            'sentiment_score': score,
            'analyzed_at': datetime.now(timezone.utc).isoformat()
        }).eq('comment_id', comment['comment_id']).execute()

    print(f"[fetch_comment_sentiment] Comentarios analizados: {len(comments)}")

if __name__ == "__main__":
    main()
