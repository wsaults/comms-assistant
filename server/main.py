#!/usr/bin/env python3
"""
Slack Monitor Server
FastAPI server that receives mention data and broadcasts to dashboards

Run with:
    uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import asyncio
from collections import defaultdict, deque

app = FastAPI(
    title="Slack Monitor Server",
    description="Centralized monitoring for Slack mentions and activity",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# DATA MODELS
# =============================================================================

class Mention(BaseModel):
    timestamp: str
    channel: str
    user: str
    text: str
    is_question: bool
    responded: bool
    client_id: str

class ConversationSummary(BaseModel):
    channel: str
    participant_count: int
    message_count: int
    topics: List[str]
    start_time: str
    end_time: str
    client_id: str

class Stats(BaseModel):
    client_id: str
    unread_count: int
    messages_last_hour: int
    active_channels: List[str]
    timestamp: str

# =============================================================================
# DATA STORE
# =============================================================================

class DataStore:
    def __init__(self):
        self.mentions: deque = deque(maxlen=1000)
        self.conversations: deque = deque(maxlen=100)
        self.stats: Dict[str, Stats] = {}
        self.hourly_message_counts: Dict[str, List[int]] = defaultdict(lambda: [0] * 24)
        self.connected_clients: Dict[str, datetime] = {}

    def add_mention(self, mention: Mention):
        self.mentions.append(mention)
        # Update hourly counts
        hour = datetime.fromisoformat(mention.timestamp).hour
        self.hourly_message_counts[mention.client_id][hour] += 1

    def add_conversation(self, conv: ConversationSummary):
        self.conversations.append(conv)

    def update_stats(self, stats: Stats):
        self.stats[stats.client_id] = stats
        self.connected_clients[stats.client_id] = datetime.now()

    def get_unread_mentions(self, client_id: Optional[str] = None) -> List[Mention]:
        if client_id:
            return [m for m in self.mentions if not m.responded and m.client_id == client_id]
        return [m for m in self.mentions if not m.responded]

    def get_recent_mentions(self, hours: int = 24, client_id: Optional[str] = None) -> List[Mention]:
        cutoff = datetime.now() - timedelta(hours=hours)
        mentions = [
            m for m in self.mentions
            if datetime.fromisoformat(m.timestamp) > cutoff
        ]
        if client_id:
            mentions = [m for m in mentions if m.client_id == client_id]
        return mentions

    def get_messages_per_hour(self, client_id: Optional[str] = None) -> Dict[int, int]:
        if client_id:
            return dict(enumerate(self.hourly_message_counts.get(client_id, [0]*24)))

        # Aggregate across all clients
        total = [0] * 24
        for counts in self.hourly_message_counts.values():
            for i, count in enumerate(counts):
                total[i] += count
        return dict(enumerate(total))

    def get_active_clients(self) -> List[str]:
        cutoff = datetime.now() - timedelta(minutes=10)
        return [
            client_id for client_id, last_seen in self.connected_clients.items()
            if last_seen > cutoff
        ]

store = DataStore()

# =============================================================================
# WEBSOCKET MANAGER
# =============================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Dashboard connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"Dashboard disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        for connection in self.active_connections[:]:  # Copy list to avoid modification during iteration
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error broadcasting to connection: {e}")
                try:
                    self.active_connections.remove(connection)
                except:
                    pass

manager = ConnectionManager()

# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/")
async def root():
    return {
        "service": "Slack Monitor Server",
        "version": "1.0.0",
        "active_clients": store.get_active_clients(),
        "total_mentions": len(store.mentions),
        "unread_mentions": len(store.get_unread_mentions()),
        "connected_dashboards": len(manager.active_connections)
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/mention")
async def report_mention(mention: Mention):
    """Receive mention from client"""
    store.add_mention(mention)

    # Broadcast to dashboards
    await manager.broadcast({
        "type": "new_mention",
        "data": mention.dict()
    })

    return {"status": "received", "mention_id": mention.timestamp}

@app.post("/api/conversation")
async def report_conversation(conv: ConversationSummary):
    """Receive conversation summary from client"""
    store.add_conversation(conv)

    await manager.broadcast({
        "type": "new_conversation",
        "data": conv.dict()
    })

    return {"status": "received"}

@app.post("/api/stats")
async def report_stats(stats: Stats):
    """Receive stats update from client"""
    store.update_stats(stats)

    await manager.broadcast({
        "type": "stats_update",
        "data": stats.dict()
    })

    return {"status": "received"}

@app.get("/api/mentions")
async def get_mentions(hours: int = 24, client_id: Optional[str] = None):
    """Get recent mentions"""
    mentions = store.get_recent_mentions(hours, client_id)
    return [m.dict() for m in mentions]

@app.get("/api/mentions/unread")
async def get_unread_mentions(client_id: Optional[str] = None):
    """Get unread mentions"""
    mentions = store.get_unread_mentions(client_id)
    return [m.dict() for m in mentions]

@app.get("/api/stats")
async def get_stats(client_id: Optional[str] = None):
    """Get current stats"""
    if client_id:
        return store.stats.get(client_id, {})
    return store.stats

@app.get("/api/messages-per-hour")
async def get_messages_per_hour(client_id: Optional[str] = None):
    """Get messages per hour for chart"""
    return store.get_messages_per_hour(client_id)

@app.get("/api/conversations")
async def get_conversations(limit: int = 10):
    """Get recent conversation summaries"""
    convs = list(store.conversations)[-limit:]
    return [c.dict() for c in reversed(convs)]

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time dashboard updates"""
    await manager.connect(websocket)
    try:
        # Send initial data
        await websocket.send_json({
            "type": "initial_data",
            "data": {
                "mentions": [m.dict() for m in store.get_recent_mentions(24)],
                "stats": {k: v.dict() for k, v in store.stats.items()},
                "messages_per_hour": store.get_messages_per_hour(),
                "active_clients": store.get_active_clients()
            }
        })

        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Echo back (keepalive)
            await websocket.send_text(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
