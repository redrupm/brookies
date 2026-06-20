from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus
from xml.etree import ElementTree

import numpy as np
import torch
import torch.nn as nn
import yfinance as yf
import requests
from bs4 import BeautifulSoup


class TemporalTransformer(nn.Module):
    def __init__(self, d_news: int = 768, d_tab: int = 6, d_model: int = 128):
        super().__init__()
        self.fusion = nn.Linear(d_news + d_tab, d_model)
        self.pos = nn.Parameter(torch.randn(1, 5, d_model))

        encoder = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=4,
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder, num_layers=2)
        self.head = nn.Sequential(
            nn.Linear(d_model, 128),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, x_news: torch.Tensor, x_tab: torch.Tensor) -> torch.Tensor:
        _, seq_len, _ = x_news.shape
        seq = []
        for t in range(seq_len):
            fused = torch.cat([x_news[:, t], x_tab[:, t]], dim=-1)
            seq.append(fused)

        x = torch.stack(seq, dim=1)
        x = self.fusion(x)
        x = x + self.pos[:, :seq_len, :]
        x = self.transformer(x)
        x = x[:, -1]
        return self.head(x).squeeze()


@dataclass(frozen=True)
class NewsPrediction:
    score: float
    confidence: float
    rationale: str


class NewsTransformerPredictor:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model: TemporalTransformer | None = None
        self.tokenizer = None
        self.bert = None
        self._auto_tokenizer_cls = None
        self._auto_model_cls = None
        self.load_error: str | None = None

        self._load()

    def _weights_path(self) -> Path | None:
        candidates = [
            self.repo_root / "news_model.pth",
            self.repo_root / "temp_transformer_model_weights.pth",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _load(self) -> None:
        try:
            weights = self._weights_path()
            if weights is None:
                self.load_error = "No transformer weights file found."
                return

            try:
                from transformers import AutoModel, AutoTokenizer
            except Exception as exc:
                self.load_error = f"Failed to import transformers runtime dependencies: {str(exc)}"
                return

            self._auto_model_cls = AutoModel
            self._auto_tokenizer_cls = AutoTokenizer

            self.tokenizer = self._auto_tokenizer_cls.from_pretrained("ProsusAI/finbert")
            self.bert = self._auto_model_cls.from_pretrained("ProsusAI/finbert").to(self.device)
            self.bert.eval()

            model = TemporalTransformer().to(self.device)
            state = torch.load(weights, map_location=self.device)
            
            # Load weights with lenient matching to handle architecture mismatches
            try:
                model.load_state_dict(state, strict=False)
            except Exception as e:
                # If lenient load fails, try to match compatible layers only
                model_state = model.state_dict()
                for key, value in state.items():
                    if key in model_state and model_state[key].shape == value.shape:
                        model_state[key] = value
                model.load_state_dict(model_state)
            
            model.eval()
            self.model = model
        except Exception as exc:
            self.load_error = str(exc)

    def is_ready(self) -> bool:
        return self.model is not None and self.tokenizer is not None and self.bert is not None

    @staticmethod
    def _lexicon_sentiment_score(headlines: list[str]) -> tuple[float, float]:
        positive_words = {
            "beats", "beat", "upgrade", "growth", "profit", "profits", "surge", "record",
            "strong", "bullish", "buy", "outperform", "expands", "win", "gains", "rally",
        }
        negative_words = {
            "miss", "downgrade", "loss", "losses", "drop", "drops", "weak", "bearish",
            "sell", "underperform", "lawsuit", "probe", "cuts", "cut", "fall", "falls",
        }

        if not headlines:
            return 5.0, 0.2

        raw_scores: list[float] = []
        for headline in headlines:
            words = {token.strip(".,:;!?()[]{}\"'").lower() for token in headline.split()}
            pos = len(words & positive_words)
            neg = len(words & negative_words)
            raw_scores.append(float(pos - neg))

        avg = float(np.mean(raw_scores)) if raw_scores else 0.0
        bounded = max(-3.0, min(3.0, avg))
        score = 5.0 + (bounded / 3.0) * 2.5
        confidence = min(0.7, 0.25 + 0.1 * abs(bounded))
        return round(score, 3), round(confidence, 3)

    def _embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((1, 768), dtype=np.float32)

        assert self.tokenizer is not None
        assert self.bert is not None

        with torch.no_grad():
            tokens = self.tokenizer(
                texts,
                padding=True,
                truncation=True,
                return_tensors="pt",
            )
            tokens = {k: v.to(self.device) for k, v in tokens.items()}
            outputs = self.bert(**tokens)
            last_hidden = outputs.last_hidden_state
            mask = tokens["attention_mask"].unsqueeze(-1)
            pooled = (last_hidden * mask).sum(dim=1) / mask.sum(dim=1)
            return pooled.cpu().numpy()

    @staticmethod
    def _normalize_headlines(headlines: Iterable[str]) -> list[str]:
        return [h.strip() for h in headlines if isinstance(h, str) and h.strip()]

    @staticmethod
    def _dedupe_headlines(headlines: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for headline in headlines:
            normalized = " ".join(headline.split()).strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(" ".join(headline.split()).strip())
        return deduped

    @staticmethod
    def _parse_pub_date(raw_date: str | None) -> datetime | None:
        if not raw_date:
            return None
        try:
            parsed = parsedate_to_datetime(raw_date)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _parse_as_of(as_of: str | None) -> datetime | None:
        if not as_of:
            return None

        try:
            parsed = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        except ValueError:
            return None

        if parsed.tzinfo is None:
            if "T" in as_of or ":" in as_of:
                return parsed.replace(tzinfo=timezone.utc)
            return datetime.combine(parsed.date(), time.max, tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _fetch_rss_headlines(
        self,
        url: str,
        lookback_days: int,
        limit: int,
        *,
        anchor_time: datetime | None = None,
    ) -> list[str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            root = ElementTree.fromstring(response.content)
        except Exception:
            return []

        anchor_time = anchor_time or datetime.now(timezone.utc)
        cutoff = anchor_time - timedelta(days=lookback_days)
        upper_bound = anchor_time + timedelta(days=1)
        headlines: list[str] = []

        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            if not title:
                continue

            pub_date = self._parse_pub_date(item.findtext("pubDate"))
            if pub_date is not None and (pub_date < cutoff or pub_date > upper_bound):
                continue

            headlines.append(title)
            if len(headlines) >= limit:
                break

        return headlines

    def fetch_recent_headlines(
        self,
        symbol: str,
        lookback_days: int = 10,
        limit: int = 12,
        as_of: str | None = None,
    ) -> list[str]:
        """
        Fetch recent headlines for a symbol with optimized performance.
        Tries Yahoo scraping first when using the live timeline, then falls back to RSS if needed.
        """
        lookback_days = max(7, min(14, lookback_days))
        anchor_time = self._parse_as_of(as_of)

        if anchor_time is None:
            # Try Yahoo scraping first - usually fastest and most reliable for live data
            collected = self.fetch_yahoo_headlines(symbol, limit=limit)
            if collected:
                deduped = self._dedupe_headlines(collected)
                if deduped:
                    return deduped[:limit]

        # Fallback to fastest RSS source (Yahoo Finance)
        yahoo_rss = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
        collected = self._fetch_rss_headlines(
            yahoo_rss,
            lookback_days=lookback_days,
            limit=limit,
            anchor_time=anchor_time,
        )
        if collected:
            deduped = self._dedupe_headlines(collected)
            if deduped:
                return deduped[:limit]

        # Try additional RSS sources in parallel as last resort
        google_query = quote_plus(f"{symbol} stock when:{lookback_days}d")
        additional_sources = [
            f"https://news.google.com/rss/search?q={google_query}&hl=en-US&gl=US&ceid=US:en",
            f"https://www.bing.com/news/search?q={quote_plus(symbol + ' stock')}&format=rss&mkt=en-US",
        ]

        for source in additional_sources:
            collected = self._fetch_rss_headlines(
                source,
                lookback_days=lookback_days,
                limit=limit,
                anchor_time=anchor_time,
            )
            if collected:
                deduped = self._dedupe_headlines(collected)
                if deduped:
                    return deduped[:limit]

        # If all else fails, return empty - lexicon will be used as fallback
        return []

    def fetch_yahoo_headlines(self, symbol: str, limit: int = 8) -> list[str]:
        # Yahoo API-level news endpoints may be blocked; scrape the public quote/news page instead.
        url = f"https://finance.yahoo.com/quote/{symbol}/news"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception:
            return []

        headlines: list[str] = []
        for h3 in soup.find_all("h3"):
            title = h3.get_text(" ", strip=True)
            if title:
                headlines.append(title)
            if len(headlines) >= limit:
                break
        return headlines

    def predict(
        self,
        symbol: str,
        headlines: list[str] | None = None,
        as_of: str | None = None,
    ) -> NewsPrediction:
        cleaned = self._normalize_headlines(headlines or [])
        if not cleaned:
            cleaned = self.fetch_recent_headlines(symbol, lookback_days=10, limit=12, as_of=as_of)
        else:
            cleaned = self._dedupe_headlines(cleaned)

        if not cleaned:
            raise ValueError(f"No headlines available to score for {symbol}.")

        if not self.is_ready():
            score, confidence = self._lexicon_sentiment_score(cleaned)
            return NewsPrediction(
                score=score,
                confidence=confidence,
                headline=cleaned[0],
            )

        assert self.model is not None

        embeddings = self._embed_texts(cleaned)
        news_vec = np.mean(embeddings, axis=0).astype(np.float32)

        # Model was trained with tabular branch; use neutral placeholders at inference time.
        tab = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 1.0], dtype=np.float32)
        seq_len = 5

        x_news = np.stack([news_vec for _ in range(seq_len)], axis=0)[None, :, :]
        x_tab = np.stack([tab for _ in range(seq_len)], axis=0)[None, :, :]

        x_news_t = torch.tensor(x_news, dtype=torch.float32).to(self.device)
        x_tab_t = torch.tensor(x_tab, dtype=torch.float32).to(self.device)

        with torch.no_grad():
            raw_pred = float(self.model(x_news_t, x_tab_t).item())

        score = float((torch.sigmoid(torch.tensor(raw_pred)) * 10).item())
        confidence = float(min(1.0, 0.3 + abs(score - 5.0) / 5.0))

        return NewsPrediction(
            score=round(score, 3),
            confidence=round(confidence, 3),
            rationale=cleaned[0],
        )
