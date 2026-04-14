import random
import time
from typing import Dict, List, Any
from datetime import datetime, timedelta

class DemoDataGenerator:
    def __init__(self):
        # Initial data bank for finance
        self.finance_tickers = [
            {"id": "PBR", "name": "Petrobras", "symbol": "PBR", "sector": "Energy", "base_price": 14.50},
            {"id": "JNJ", "name": "Johnson & Johnson", "symbol": "JNJ", "sector": "Healthcare", "base_price": 158.20},
            {"id": "V", "name": "Visa Inc.", "symbol": "V", "sector": "Technology", "base_price": 275.40},
            {"id": "PEP", "name": "PepsiCo Inc.", "symbol": "PEP", "sector": "Consumer", "base_price": 167.30},
            {"id": "UBER", "name": "Uber Technologies", "symbol": "UBER", "sector": "Technology", "base_price": 78.10},
            {"id": "GOOGL", "name": "Alphabet Inc.", "symbol": "GOOGL", "sector": "Technology", "base_price": 142.20},
            {"id": "MSFT", "name": "Microsoft Corp.", "symbol": "MSFT", "sector": "Technology", "base_price": 415.50},
            {"id": "AAPL", "name": "Apple Inc.", "symbol": "AAPL", "sector": "Technology", "base_price": 185.30},
            {"id": "KO", "name": "Coca-Cola Co.", "symbol": "KO", "sector": "Consumer", "base_price": 59.80},
            {"id": "TSLA", "name": "Tesla Inc.", "symbol": "TSLA", "sector": "Automotive", "base_price": 175.40},
        ]
        
        # State tracking for real-time updates
        self.state = {t["id"]: {"price": t["base_price"], "history": [t["base_price"] * (1 + random.uniform(-0.02, 0.02)) for _ in range(20)]} for t in self.finance_tickers}

    def generate_update(self, category: str = "finance") -> Dict[str, Any]:
        """Generates a single tick update for a random subset of items."""
        if category == "finance":
            updates = []
            # Update 30% of tickers per tick
            targets = random.sample(self.finance_tickers, k=max(1, int(len(self.finance_tickers) * 0.3)))
            
            for ticker in targets:
                tid = ticker["id"]
                current = self.state[tid]["price"]
                change_pct = random.uniform(-0.015, 0.015)
                new_price = current * (1 + change_pct)
                
                # Update state
                self.state[tid]["price"] = new_price
                self.state[tid]["history"].append(new_price)
                if len(self.state[tid]["history"]) > 30:
                    self.state[tid]["history"].pop(0)
                
                updates.append({
                    "id": tid,
                    "symbol": ticker["symbol"],
                    "name": ticker["name"],
                    "price": round(new_price, 2),
                    "change": round(new_price - ticker["base_price"], 2),
                    "changePct": round((new_price - ticker["base_price"]) / ticker["base_price"] * 100, 2),
                    "history": self.state[tid]["history"],
                    "lastUpdate": datetime.now().isoformat()
                })
            return {"type": "finance", "data": updates}
        
        return {"type": "generic", "data": []}

    async def stream_updates(self, category: str = "finance", interval: float = 0.5):
        """Async generator for SSE streaming."""
        while True:
            update = self.generate_update(category)
            yield update
            time.sleep(interval)
