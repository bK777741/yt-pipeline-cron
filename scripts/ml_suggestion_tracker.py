#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRACKER DE SUGERENCIAS DEL MODELO
==================================

Helper para registrar sugerencias del modelo y facilitar el aprendizaje

USO:
```python
from ml_suggestion_tracker import SuggestionTracker

tracker = SuggestionTracker(supabase_client)

# Cuando el modelo hace una sugerencia
suggestion_id = tracker.record_suggestion(
    suggestion_type="title",
    original_suggestion="Truco SECRETO de WhatsApp",
    model_version="v2.0",
    model_confidence=0.85,
    predicted_vph=150.0
)

# Cuando el usuario publica (con o sin modificación)
tracker.record_publication(
    suggestion_id=suggestion_id,
    video_id="abc123",
    final_version="El Truco OCULTO de WhatsApp que cambió mi vida",
    was_modified=True
)

# Cuando hay métricas (después de 24h)
tracker.record_feedback(
    suggestion_id=suggestion_id,
    video_id="abc123",
    views_24h=15000,
    likes=850,
    retention_percent=75.5,
    vph_24h=625.0
)
```
"""

import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from supabase import Client


class SuggestionTracker:
    """Helper para trackear sugerencias y feedback"""

    def __init__(self, supabase_client: Client):
        self.sb = supabase_client

    def record_suggestion(
        self,
        suggestion_type: str,
        original_suggestion: str,
        model_version: str,
        model_confidence: Optional[float] = None,
        predicted_vph: Optional[float] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Registra una sugerencia del modelo

        Args:
            suggestion_type: 'title', 'script', 'thumbnail', 'tags'
            original_suggestion: Lo que el modelo sugirió
            model_version: Versión del modelo (v2.0, v2.1, etc.)
            model_confidence: Confianza del modelo (0-1)
            predicted_vph: VPH predicho
            metadata: Datos adicionales

        Returns:
            str: ID de la sugerencia
        """
        data = {
            "suggestion_type": suggestion_type,
            "original_suggestion": original_suggestion,
            "model_version": model_version,
            "model_confidence": model_confidence,
            "predicted_vph": predicted_vph,
            "suggested_at": datetime.now(timezone.utc).isoformat()
        }

        if metadata:
            data["changes_summary"] = metadata

        try:
            result = self.sb.table("ml_suggestions").insert(data).execute()
            suggestion_id = result.data[0]["id"]
            print(f"[TRACKER] Sugerencia registrada: {suggestion_id}")
            return suggestion_id
        except Exception as e:
            print(f"[TRACKER ERROR] No se pudo registrar sugerencia: {e}")
            return None

    def record_publication(
        self,
        suggestion_id: str,
        video_id: str,
        final_version: str,
        was_modified: bool = False,
        modification_type: Optional[str] = None,
        changes: Optional[Dict] = None
    ):
        """
        Registra la publicación final (con o sin modificación)

        Args:
            suggestion_id: ID de la sugerencia original
            video_id: ID del video publicado
            final_version: Versión final publicada
            was_modified: ¿Se modificó la sugerencia?
            modification_type: 'accepted', 'minor_edit', 'major_rewrite', 'rejected'
            changes: Qué cambió exactamente
        """
        update_data = {
            "video_id": video_id,
            "final_version": final_version,
            "was_modified": was_modified,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        if modification_type:
            update_data["modification_type"] = modification_type

        if changes:
            update_data["changes_summary"] = changes

        try:
            self.sb.table("ml_suggestions") \
                .update(update_data) \
                .eq("id", suggestion_id) \
                .execute()

            status = "MODIFICADO" if was_modified else "ACEPTADO"
            print(f"[TRACKER] Publicación registrada: {video_id} ({status})")
        except Exception as e:
            print(f"[TRACKER ERROR] No se pudo registrar publicación: {e}")

    def record_feedback(
        self,
        suggestion_id: str,
        video_id: str,
        views_24h: Optional[int] = None,
        views_7d: Optional[int] = None,
        views_30d: Optional[int] = None,
        likes: Optional[int] = None,
        comments: Optional[int] = None,
        shares: Optional[int] = None,
        ctr_percent: Optional[float] = None,
        retention_percent: Optional[float] = None,
        vph_24h: Optional[float] = None,
        vph_7d: Optional[float] = None,
        vs_channel_average_percent: Optional[float] = None
    ):
        """
        Registra feedback de métricas reales

        Args:
            suggestion_id: ID de la sugerencia
            video_id: ID del video
            views_24h, views_7d, views_30d: Views en diferentes períodos
            likes, comments, shares: Métricas de engagement
            ctr_percent: Click-through rate
            retention_percent: Retención promedio
            vph_24h, vph_7d: Views per hour
            vs_channel_average_percent: Comparación con promedio del canal
        """
        # Calcular scores
        engagement_score = None
        if views_24h and likes and comments:
            engagement_score = ((likes + comments * 2 + (shares or 0) * 3) / views_24h) * 100

        # Clasificar resultado
        result_quality = "average"
        if vs_channel_average_percent:
            if vs_channel_average_percent > 50:
                result_quality = "excellent"
            elif vs_channel_average_percent > 20:
                result_quality = "good"
            elif vs_channel_average_percent < -20:
                result_quality = "poor"

        # Obtener predicción original
        try:
            sug_resp = self.sb.table("ml_suggestions") \
                .select("predicted_vph") \
                .eq("id", suggestion_id) \
                .execute()

            predicted_vph = sug_resp.data[0]["predicted_vph"] if sug_resp.data else None

            vs_predicted_vph_percent = None
            if predicted_vph and vph_24h:
                vs_predicted_vph_percent = ((vph_24h - predicted_vph) / predicted_vph) * 100

        except:
            vs_predicted_vph_percent = None

        # Insertar feedback
        data = {
            "suggestion_id": suggestion_id,
            "video_id": video_id,
            "views_24h": views_24h,
            "views_7d": views_7d,
            "views_30d": views_30d,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "ctr_percent": ctr_percent,
            "retention_percent": retention_percent,
            "vph_24h": vph_24h,
            "vph_7d": vph_7d,
            "engagement_score": engagement_score,
            "vs_channel_average_percent": vs_channel_average_percent,
            "vs_predicted_vph_percent": vs_predicted_vph_percent,
            "result_quality": result_quality,
            "measured_at": datetime.now(timezone.utc).isoformat()
        }

        try:
            self.sb.table("ml_feedback").insert(data).execute()
            print(f"[TRACKER] Feedback registrado: {video_id} ({result_quality.upper()})")
        except Exception as e:
            print(f"[TRACKER ERROR] No se pudo registrar feedback: {e}")

    def analyze_text_diff(self, original: str, final: str) -> Dict:
        """
        Analiza diferencias entre texto original y final

        Returns:
            dict: Cambios detectados
        """
        original_words = set(original.lower().split())
        final_words = set(final.lower().split())

        added = final_words - original_words
        removed = original_words - final_words

        return {
            "added_words": list(added),
            "removed_words": list(removed),
            "length_change": len(final) - len(original),
            "word_count_change": len(final.split()) - len(original.split())
        }

    def get_acceptance_rate(self, model_version: str, days: int = 30) -> float:
        """
        Calcula tasa de aceptación del modelo

        Args:
            model_version: Versión del modelo
            days: Días hacia atrás

        Returns:
            float: Porcentaje de aceptación (0-100)
        """
        from datetime import timedelta

        fecha_limite = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        try:
            # Total de sugerencias
            total_resp = self.sb.table("ml_suggestions") \
                .select("*", count="exact") \
                .eq("model_version", model_version) \
                .gte("suggested_at", fecha_limite) \
                .execute()

            total = total_resp.count if hasattr(total_resp, 'count') else 0

            if total == 0:
                return 0

            # Sugerencias aceptadas (no modificadas)
            accepted_resp = self.sb.table("ml_suggestions") \
                .select("*", count="exact") \
                .eq("model_version", model_version) \
                .eq("was_modified", False) \
                .gte("suggested_at", fecha_limite) \
                .execute()

            accepted = accepted_resp.count if hasattr(accepted_resp, 'count') else 0

            return (accepted / total) * 100

        except Exception as e:
            print(f"[TRACKER ERROR] No se pudo calcular acceptance rate: {e}")
            return 0
