#!/usr/bin/env python3
"""
Slack Monitor Server
FastAPI server that receives mention data and broadcasts to dashboards

Run with:
    uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import asyncio
from collections import defaultdict, deque

# Import database and mock data modules
from server import database as db
from server import mock_data

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
    workspace: str = "unknown"  # Slack workspace or Teams org name

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
async def report_mention(mention: Mention, background_tasks: BackgroundTasks):
    """Receive mention from client"""
    # Add to in-memory store for real-time updates
    store.add_mention(mention)

    # Save to database in background
    background_tasks.add_task(save_mention_to_db, mention)

    # Broadcast to dashboards
    await manager.broadcast({
        "type": "new_mention",
        "data": mention.dict()
    })

    return {"status": "received", "mention_id": mention.timestamp}


def save_mention_to_db(mention: Mention):
    """Background task to save mention to database"""
    session = db.get_db()
    try:
        db.add_mention(
            session,
            timestamp=datetime.fromisoformat(mention.timestamp),
            channel=mention.channel,
            user=mention.user,
            text=mention.text,
            is_question=mention.is_question,
            responded=mention.responded,
            client_id=mention.client_id,
            workspace=mention.workspace
        )
    finally:
        session.close()

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
async def report_stats(stats: Stats, background_tasks: BackgroundTasks):
    """Receive stats update from client"""
    store.update_stats(stats)

    # Update client in database
    background_tasks.add_task(save_client_to_db, stats.client_id)

    await manager.broadcast({
        "type": "stats_update",
        "data": stats.dict()
    })

    return {"status": "received"}


def save_client_to_db(client_id: str):
    """Background task to update client in database"""
    session = db.get_db()
    try:
        db.update_client(session, client_id=client_id)
    finally:
        session.close()

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

# =============================================================================
# DEBUG / DEVELOPMENT ENDPOINTS
# =============================================================================

@app.post("/api/debug/seed")
async def seed_mock_data(scenario: str = "default", clear_old: bool = True):
    """
    Seed database with mock data for testing - ALL DATA FROM TODAY

    Scenarios: default, high_activity, multi_job
    Args:
        scenario: Which mock scenario to load
        clear_old: Clear old data before seeding (default: True)
    """
    session = db.get_db()
    try:
        # Clear old data if requested
        if clear_old:
            print("Clearing old data...")
            store.mentions.clear()
            store.stats.clear()
            db.cleanup_old_data(session, days=0)  # Clear all
            print("✓ Old data cleared")

        # Get fresh mock data (all from today)
        print(f"Generating mock data for scenario: {scenario}")
        mock_dataset = mock_data.get_mock_scenario(scenario)
        print(f"✓ Generated {len(mock_dataset.get('mentions', []))} mentions from today")
        # Add mentions to database
        for mention in mock_dataset.get("mentions", []):
            db.add_mention(
                session,
                timestamp=datetime.fromisoformat(mention.timestamp),
                channel=mention.channel,
                user=mention.user,
                text=mention.text,
                is_question=mention.is_question,
                responded=mention.responded,
                client_id=mention.client_id
            )
            # Also add to in-memory store
            store.add_mention(Mention(**mention.dict()))

        # Add stats
        for stat in mock_dataset.get("stats", []):
            store.update_stats(Stats(**stat.dict()))
            db.update_client(session, client_id=stat.client_id)

        # Add channel activity if present
        for activity in mock_dataset.get("channel_activity", []):
            db.add_channel_activity(
                session,
                channel=activity["channel"],
                message_count=activity["message_count"],
                hour=activity["hour"],
                date=activity["date"],
                client_id=activity["client_id"]
            )

        # Broadcast update to dashboards
        await manager.broadcast({
            "type": "data_seeded",
            "data": {
                "scenario": scenario,
                "mentions_added": len(mock_dataset.get("mentions", [])),
                "stats_added": len(mock_dataset.get("stats", []))
            }
        })

        today = datetime.now().strftime("%Y-%m-%d")
        return {
            "status": "success",
            "scenario": scenario,
            "date": today,
            "mentions_added": len(mock_dataset.get("mentions", [])),
            "stats_added": len(mock_dataset.get("stats", [])),
            "message": f"Mock data from {today} loaded. Refresh dashboard to see changes."
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
    finally:
        session.close()


@app.delete("/api/debug/clear")
async def clear_all_data():
    """Clear all data from in-memory store and database"""
    # Clear in-memory
    store.mentions.clear()
    store.stats.clear()
    store.connected_clients.clear()

    # Clear database (keep last 0 days = delete all)
    session = db.get_db()
    try:
        result = db.cleanup_old_data(session, days=0)
        return {
            "status": "success",
            "cleared": result
        }
    finally:
        session.close()


@app.get("/api/debug/stats")
async def get_debug_stats():
    """Get database statistics"""
    session = db.get_db()
    try:
        stats = db.get_stats(session)
        return stats
    finally:
        session.close()


# =============================================================================
# STARTUP / SHUTDOWN EVENTS
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Load recent data from database on startup"""
    print("🚀 Starting Slack Monitor Server...")
    print(f"📂 Database: {db.DB_FILE}")

    # Load recent mentions from database to in-memory store
    session = db.get_db()
    try:
        recent_mentions = db.get_recent_mentions(session, hours=24, limit=100)
        for db_mention in recent_mentions:
            mention = Mention(
                timestamp=db_mention.timestamp.isoformat(),
                channel=db_mention.channel,
                user=db_mention.user,
                text=db_mention.text,
                is_question=db_mention.is_question,
                responded=db_mention.responded,
                client_id=db_mention.client_id,
                workspace=getattr(db_mention, 'workspace', 'unknown')  # Handle old DB records
            )
            store.mentions.append(mention)

        print(f"✓ Loaded {len(recent_mentions)} recent mentions from database")

        # Load active clients
        active_clients = db.get_active_clients(session)
        for client in active_clients:
            store.connected_clients[client.client_id] = client.last_seen

        print(f"✓ Loaded {len(active_clients)} active clients")
        print("✓ Server ready!")
    finally:
        session.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
