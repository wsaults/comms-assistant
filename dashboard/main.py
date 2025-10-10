#!/usr/bin/env python3
"""
Slack Monitor Dashboard
Textual TUI that displays real-time Slack activity

Run with: python dashboard/main.py
"""

import asyncio
import os
import json
import socket
from datetime import datetime
from typing import Dict, List

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, DataTable, Label
from textual.reactive import reactive
from textual import work
import httpx
import websockets
from dotenv import load_dotenv

load_dotenv()

SERVER_URL = os.getenv("MONITOR_SERVER_URL", "http://localhost:8000")
WS_URL = SERVER_URL.replace("http://", "ws://").replace("https://", "wss://") + "/ws"


def get_local_ip():
    """Get local network IP address"""
    try:
        # Create a socket to determine the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Connect to an external address (doesn't actually send data)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


def get_ngrok_url():
    """Get ngrok public URL if available"""
    try:
        with httpx.Client(timeout=1.0) as client:
            response = client.get("http://localhost:4040/api/tunnels")
            if response.status_code == 200:
                tunnels = response.json().get("tunnels", [])
                for tunnel in tunnels:
                    if tunnel.get("proto") == "https":
                        return tunnel.get("public_url")
                # Fallback to first tunnel if no https
                if tunnels:
                    return tunnels[0].get("public_url")
    except Exception:
        pass
    return None


class StatsWidget(Static):
    """Widget displaying statistics overview"""

    unread_count = reactive(0)
    last_hour_count = reactive(0)
    active_channels = reactive(0)
    connected_clients = reactive(0)
    total_mentions = reactive(0)
    last_update = reactive("")
    ngrok_url = reactive("")

    def render(self) -> str:
        stats = f"""[bold cyan]📊 Stats Overview[/bold cyan]

[yellow]🔔 Unread Mentions:[/yellow]   {self.unread_count:>6}
[yellow]💬 Last Hour:[/yellow]        {self.last_hour_count:>6}
[yellow]📺 Active Channels:[/yellow]  {self.active_channels:>6}
[yellow]💻 Connected Clients:[/yellow] {self.connected_clients:>6}
[yellow]📝 Total Mentions:[/yellow]   {self.total_mentions:>6}
[yellow]🕐 Last Update:[/yellow]      {self.last_update:>12}"""

        if self.ngrok_url:
            stats += f"\n\n[bold cyan]🌐 Public URL[/bold cyan]"
            stats += f"\n[green]🔗 {self.ngrok_url}[/green]"

        return stats


class MentionsTable(Static):
    """Widget displaying recent mentions"""

    mentions = reactive([])

    @staticmethod
    def clean_slack_mentions(text):
        """Remove Slack user ID format from text"""
        import re
        # Replace <@USER_ID|username> with username
        # Replace <@USER_ID> with @USER_ID
        text = re.sub(r'<@[A-Z0-9]+\|([^>]+)>', r'\1', text)
        text = re.sub(r'<@([A-Z0-9]+)>', r'@\1', text)
        return text

    def render(self) -> str:
        lines = ["[bold magenta]💬 Recent Mentions[/bold magenta]\n"]

        if not self.mentions:
            lines.append("[dim]No mentions yet...[/dim]")
            return "\n".join(lines)

        # Show last 10 mentions
        recent = sorted(self.mentions, key=lambda x: x.get("timestamp", ""), reverse=True)[:10]

        for mention in recent:
            try:
                timestamp = datetime.fromisoformat(mention["timestamp"]).strftime("%I:%M %p")
            except:
                timestamp = "--:--"

            channel = mention.get("channel", "?")[:15]
            user = mention.get("user", "?")[:12]
            raw_text = mention.get("text", "")

            # Clean Slack user ID format
            text = self.clean_slack_mentions(raw_text)

            if len(text) > 50:
                text = text[:47] + "..."

            # Status indicator
            if mention.get("responded"):
                status = "[green]✓[/green]"
            elif mention.get("is_question"):
                status = "[yellow]?[/yellow]"
            else:
                status = "[dim]•[/dim]"

            lines.append(f"{timestamp} │ [cyan]{channel:<15}[/cyan] │ [yellow]{user:<12}[/yellow] │ {text} {status}")

        return "\n".join(lines)


class MentionsLineGraph(Static):
    """Widget displaying mentions per client as a line graph"""

    mentions_by_client = reactive({})
    all_mentions = reactive([])

    def render(self) -> str:
        lines = ["[bold green]📈 Mentions Per Client (Today)[/bold green]\n"]

        if not self.all_mentions:
            lines.append("[dim]No data yet...[/dim]")
            return "\n".join(lines)

        # Group mentions by client and hour
        from collections import defaultdict
        client_hourly = defaultdict(lambda: defaultdict(int))

        for mention in self.all_mentions:
            try:
                timestamp = datetime.fromisoformat(mention["timestamp"])
                hour = timestamp.hour
                client_id = mention.get("client_id", "unknown")
                client_hourly[client_id][hour] += 1
            except:
                continue

        if not client_hourly:
            lines.append("[dim]No data yet...[/dim]")
            return "\n".join(lines)

        # Get all unique clients
        clients = list(client_hourly.keys())
        colors = ["cyan", "magenta", "yellow", "green", "blue", "red"]

        # Calculate max for scaling
        max_count = 0
        for client_data in client_hourly.values():
            max_count = max(max_count, max(client_data.values()) if client_data else 0)

        if max_count == 0:
            max_count = 1

        # Display graph (last 12 hours)
        current_hour = datetime.now().hour
        hours_to_show = 12
        start_hour = (current_hour - hours_to_show + 1) % 24

        # Build the graph
        graph_height = 8
        for row in range(graph_height, 0, -1):
            line_parts = [f"{row:2d} │"]

            for h in range(hours_to_show):
                hour = (start_hour + h) % 24

                # Check if any client has data at this hour/height
                char = " "
                for i, client_id in enumerate(clients):
                    count = client_hourly[client_id].get(hour, 0)
                    scaled = int((count / max_count) * graph_height) if max_count > 0 else 0

                    if scaled >= row:
                        color = colors[i % len(colors)]
                        char = f"[{color}]●[/{color}]"
                        break

                line_parts.append(char)

            lines.append("".join(line_parts))

        # X-axis
        axis = "   └" + "─" * hours_to_show
        lines.append(axis)

        # Hour labels (12-hour format)
        hour_labels = "    "
        for h in range(hours_to_show):
            hour = (start_hour + h) % 24
            if h % 2 == 0:  # Show every other hour
                # Convert to 12-hour format
                hour_12 = hour % 12
                if hour_12 == 0:
                    hour_12 = 12
                am_pm = "a" if hour < 12 else "p"
                hour_labels += f"{hour_12}{am_pm}"
            else:
                hour_labels += "  "
        lines.append(hour_labels)

        # Legend
        lines.append("")
        lines.append("[bold]Clients:[/bold]")
        for i, client_id in enumerate(clients[:5]):  # Show up to 5 clients
            color = colors[i % len(colors)]
            display_name = client_id[:20] if len(client_id) <= 20 else client_id[:17] + "..."
            total = sum(client_hourly[client_id].values())
            lines.append(f"[{color}]●[/{color}] {display_name} ({total} mentions)")

        return "\n".join(lines)


class ClientsPanel(Static):
    """Widget displaying connected clients"""

    stats = reactive({})

    def render(self) -> str:
        lines = ["[bold cyan]💻 Connected Clients[/bold cyan]\n"]

        if not self.stats:
            lines.append("[dim]No clients connected...[/dim]")
            return "\n".join(lines)

        for client_id, client_stats in self.stats.items():
            display_id = client_id if len(client_id) <= 25 else client_id[:22] + "..."
            unread = client_stats.get("unread_count", 0)
            last_hr = client_stats.get("messages_last_hour", 0)

            lines.append(f"[yellow]{display_id}[/yellow]")
            lines.append(f"  Unread: {unread} │ Last Hr: {last_hr}")

        return "\n".join(lines)


class ConnectionStatus(Static):
    """Widget displaying connection status"""

    status = reactive("Connecting...")
    status_color = reactive("yellow")

    def render(self) -> str:
        return f"[{self.status_color}]● {self.status}[/{self.status_color}]"


class SlackMonitorApp(App):
    """Textual application for Slack monitoring"""

    CSS = """
    Screen {
        background: $surface;
    }

    #header-container {
        height: 3;
        background: $primary;
        border: solid $primary;
    }

    #main-container {
        height: 1fr;
        layout: horizontal;
    }

    #left-panel {
        width: 35;
        height: 1fr;
        layout: vertical;
    }

    #right-panel {
        width: 1fr;
        height: 1fr;
        layout: vertical;
    }

    #stats-widget {
        height: 16;
        border: solid cyan;
        padding: 1;
    }

    #clients-panel {
        height: 1fr;
        border: solid cyan;
        padding: 1;
    }

    #mentions-table {
        height: 2fr;
        border: solid magenta;
        padding: 1;
    }

    #chart-widget {
        height: 1fr;
        border: solid green;
        padding: 1;
    }

    #status-bar {
        height: 1;
        background: $panel;
        padding: 0 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
    ]

    def __init__(self):
        super().__init__()
        self.data = {
            "mentions": [],
            "stats": {},
            "messages_per_hour": {},
            "active_clients": []
        }

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        yield Header()

        with Container(id="main-container"):
            with Vertical(id="left-panel"):
                yield StatsWidget(id="stats-widget")
                yield ClientsPanel(id="clients-panel")

            with Vertical(id="right-panel"):
                yield MentionsTable(id="mentions-table")
                yield MentionsLineGraph(id="chart-widget")

        with Container(id="status-bar"):
            yield ConnectionStatus()

        yield Footer()

    async def on_mount(self) -> None:
        """Called when app starts"""
        self.title = "Slack Activity Monitor"

        # Extract port from SERVER_URL
        port = "8000"
        if ":" in SERVER_URL:
            port = SERVER_URL.split(":")[-1].rstrip("/")

        # Check for ngrok URL first
        ngrok_url = get_ngrok_url()
        if ngrok_url:
            self.sub_title = f"ngrok: {ngrok_url} | Local: http://{get_local_ip()}:{port}"
        else:
            # Show actual network IP that clients can connect to
            local_ip = get_local_ip()
            self.sub_title = f"Server: http://{local_ip}:{port}"

        # Start data fetching
        self.fetch_initial_data()
        self.listen_to_websocket()

    @work(exclusive=True)
    async def fetch_initial_data(self) -> None:
        """Fetch initial data from server"""
        status_widget = self.query_one(ConnectionStatus)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Get mentions
                response = await client.get(f"{SERVER_URL}/api/mentions?hours=24")
                self.data["mentions"] = response.json()

                # Get stats
                response = await client.get(f"{SERVER_URL}/api/stats")
                self.data["stats"] = response.json()

                # Get messages per hour
                response = await client.get(f"{SERVER_URL}/api/messages-per-hour")
                self.data["messages_per_hour"] = response.json()

                self.update_widgets()

                status_widget.status = "Connected"
                status_widget.status_color = "green"

        except Exception as e:
            status_widget.status = f"Error: {str(e)[:30]}"
            status_widget.status_color = "red"

    @work(exclusive=True)
    async def listen_to_websocket(self) -> None:
        """Listen for real-time updates via WebSocket"""
        status_widget = self.query_one(ConnectionStatus)

        while True:
            try:
                self.log(f"Attempting to connect to WebSocket at {WS_URL}")
                async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=10) as websocket:
                    status_widget.status = "Connected (Live)"
                    status_widget.status_color = "green"
                    self.log("WebSocket connected successfully")

                    async for message in websocket:
                        msg_data = json.loads(message)
                        self.log(f"Received message: {msg_data['type']}")

                        if msg_data["type"] == "initial_data":
                            payload = msg_data["data"]
                            self.data["mentions"] = payload.get("mentions", [])
                            self.data["stats"] = payload.get("stats", {})
                            self.data["messages_per_hour"] = payload.get("messages_per_hour", {})
                            self.data["active_clients"] = payload.get("active_clients", [])
                            self.update_widgets()

                        elif msg_data["type"] == "new_mention":
                            self.data["mentions"].append(msg_data["data"])
                            self.update_widgets()

                        elif msg_data["type"] == "stats_update":
                            stats = msg_data["data"]
                            self.data["stats"][stats["client_id"]] = stats
                            self.update_widgets()

            except websockets.exceptions.WebSocketException as e:
                status_widget.status = f"WS Error - Reconnecting..."
                status_widget.status_color = "yellow"
                self.log(f"WebSocket error: {e}")
                await asyncio.sleep(5)
            except Exception as e:
                status_widget.status = f"Error - Reconnecting..."
                status_widget.status_color = "yellow"
                self.log(f"Unexpected error: {type(e).__name__}: {e}")
                await asyncio.sleep(5)

    def update_widgets(self) -> None:
        """Update all widgets with current data"""
        # Update stats widget
        stats_widget = self.query_one(StatsWidget)
        total_unread = sum(s.get("unread_count", 0) for s in self.data["stats"].values())
        total_last_hour = sum(s.get("messages_last_hour", 0) for s in self.data["stats"].values())

        all_channels = set()
        for s in self.data["stats"].values():
            all_channels.update(s.get("active_channels", []))

        stats_widget.unread_count = total_unread
        stats_widget.last_hour_count = total_last_hour
        stats_widget.active_channels = len(all_channels)
        stats_widget.connected_clients = len(self.data["stats"])
        stats_widget.total_mentions = len(self.data["mentions"])
        stats_widget.last_update = datetime.now().strftime("%I:%M:%S %p")

        # Update ngrok URL (check for ngrok each time)
        ngrok_url = get_ngrok_url()
        if ngrok_url:
            stats_widget.ngrok_url = ngrok_url

        # Update mentions table
        mentions_widget = self.query_one(MentionsTable)
        mentions_widget.mentions = self.data["mentions"]

        # Update chart
        chart_widget = self.query_one(MentionsLineGraph)
        chart_widget.all_mentions = self.data["mentions"]

        # Update clients panel
        clients_widget = self.query_one(ClientsPanel)
        clients_widget.stats = self.data["stats"]

    def action_refresh(self) -> None:
        """Refresh data"""
        self.fetch_initial_data()

    def action_quit(self) -> None:
        """Quit the app"""
        self.exit()


def main():
    """Run the dashboard"""
    app = SlackMonitorApp()
    app.run()


if __name__ == "__main__":
    main()
