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
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, DataTable, Label, ListView, ListItem,
    LoadingIndicator, Collapsible, TabbedContent, TabPane,
    Input, Button, Switch
)
from textual.reactive import reactive
from textual import work, on
from textual.message import Message
from textual.command import Provider, Hit, Hits
from textual.types import IgnoreReturnCallbackType
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
        stats = f"""[yellow]🔔 Unread Mentions:[/yellow]   {self.unread_count:>6}
[yellow]💬 Last Hour:[/yellow]        {self.last_hour_count:>6}
[yellow]📺 Active Channels:[/yellow]  {self.active_channels:>6}
[yellow]💻 Connected Clients:[/yellow] {self.connected_clients:>6}
[yellow]📝 Total Mentions:[/yellow]   {self.total_mentions:>6}
[yellow]🕐 Last Update:[/yellow]      {self.last_update:>12}"""

        return stats


class MentionsTable(DataTable):
    """Widget displaying recent mentions using DataTable"""

    mentions = reactive([])
    search_filter = reactive("")

    def on_mount(self) -> None:
        """Set up the table structure"""
        self.cursor_type = "row"
        self.zebra_stripes = True

        # Add columns
        self.add_column("Time", key="time", width=10)
        self.add_column("Channel", key="channel", width=15)
        self.add_column("User", key="user", width=12)
        self.add_column("Message", key="message")
        self.add_column("S", key="status", width=3)  # Status

    @staticmethod
    def clean_slack_mentions(text):
        """Remove Slack user ID format from text"""
        import re
        # Replace <@USER_ID|username> with username
        # Replace <@USER_ID> with @USER_ID
        text = re.sub(r'<@[A-Z0-9]+\|([^>]+)>', r'\1', text)
        text = re.sub(r'<@([A-Z0-9]+)>', r'@\1', text)
        return text

    def watch_mentions(self, mentions: list) -> None:
        """Update table when mentions change"""
        # Clear existing rows
        self.clear()

        if not mentions:
            return

        # Apply search filter if set
        if self.search_filter:
            filtered = []
            for mention in mentions:
                text = mention.get("text", "").lower()
                channel = mention.get("channel", "").lower()
                user = mention.get("user", "").lower()
                if (self.search_filter in text or
                    self.search_filter in channel or
                    self.search_filter in user):
                    filtered.append(mention)
            mentions = filtered

        # Sort mentions by timestamp (most recent first) and show last 20
        recent = sorted(mentions, key=lambda x: x.get("timestamp", ""), reverse=True)[:20]

        for mention in recent:
            # Format timestamp
            try:
                timestamp = datetime.fromisoformat(mention["timestamp"]).strftime("%I:%M %p")
            except:
                timestamp = "--:--"

            # Format channel and user
            channel = mention.get("channel", "?")[:15]
            user = mention.get("user", "?")[:12]

            # Clean and truncate message text
            raw_text = mention.get("text", "")
            text = self.clean_slack_mentions(raw_text)
            if len(text) > 45:
                text = text[:42] + "..."

            # Status indicator
            from rich.text import Text
            if mention.get("responded"):
                status = Text("✓", style="green")
            elif mention.get("is_question"):
                status = Text("?", style="yellow")
            else:
                status = Text("•", style="dim")

            # Add row with Rich text formatting
            self.add_row(
                timestamp,
                Text(channel, style="cyan"),
                Text(user, style="yellow"),
                text,
                status
            )


class MentionsGraphWidget(Static):
    """Widget displaying mentions per client as a simple graph"""

    all_mentions = reactive([])

    def render(self) -> str:
        lines = ["[bold green]📈 Mentions Per Client (8am-8pm Today)[/bold green]\n"]

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

        # Display graph (8am to 8pm = 13 hours)
        start_hour = 8
        end_hour = 20
        hours_to_show = end_hour - start_hour + 1
        chars_per_hour = 3

        # Build the graph
        graph_height = 8
        for row in range(graph_height, 0, -1):
            line_parts = [f"{row:2d} │"]

            for h in range(hours_to_show):
                hour = start_hour + h

                # Check if any client has data at this hour/height
                char = " "
                for i, client_id in enumerate(clients):
                    count = client_hourly[client_id].get(hour, 0)
                    scaled = int((count / max_count) * graph_height) if max_count > 0 else 0

                    if scaled >= row:
                        color = colors[i % len(colors)]
                        char = f"[{color}]●[/{color}]"
                        break

                # Add the character and spacing
                line_parts.append(char)
                if h < hours_to_show - 1:
                    line_parts.append(" " * (chars_per_hour - 1))

            lines.append("".join(line_parts))

        # X-axis
        axis_length = hours_to_show * chars_per_hour - (chars_per_hour - 1)
        axis = "   └" + "─" * axis_length
        lines.append(axis)

        # Hour labels with spacing (just numbers)
        hour_labels = "    "
        for h in range(hours_to_show):
            hour = start_hour + h
            hour_12 = hour % 12
            if hour_12 == 0:
                hour_12 = 12

            label = str(hour_12)
            padding = chars_per_hour - len(label)
            hour_labels += (" " * padding) + label

        lines.append(hour_labels)

        # Legend
        lines.append("")
        lines.append("[bold]Clients:[/bold]")
        for i, client_id in enumerate(clients[:5]):
            color = colors[i % len(colors)]
            display_name = client_id[:20] if len(client_id) <= 20 else client_id[:17] + "..."
            total = sum(client_hourly[client_id].values())
            lines.append(f"[{color}]●[/{color}] {display_name} ({total} mentions)")

        return "\n".join(lines)


class ConnectionStatus(Static):
    """Widget displaying connection status"""

    status = reactive("Connecting...")
    status_color = reactive("yellow")

    def render(self) -> str:
        return f"[{self.status_color}]● {self.status}[/{self.status_color}]"


class PriorityAlertsWidget(Static):
    """Widget displaying priority alerts - direct mentions, questions, high activity"""

    mentions = reactive([])
    stats = reactive({})

    def render(self) -> str:
        lines = ["[bold red]🚨 Priority Alerts[/bold red]\n"]

        if not self.mentions:
            lines.append("[dim]No priority alerts[/dim]")
            return "\n".join(lines)

        # Find direct mentions (contains @)
        direct_mentions = []
        questions = []
        for mention in self.mentions:
            text = mention.get("text", "")
            # Check if it's a direct mention by looking for @ in the text
            if "@" in text and not mention.get("responded"):
                direct_mentions.append(mention)
            elif mention.get("is_question") and not mention.get("responded"):
                questions.append(mention)

        # Show direct mentions first
        if direct_mentions:
            lines.append("[bold red on white]🔴 DIRECT MENTIONS[/bold red on white]")
            for mention in direct_mentions[:3]:
                try:
                    timestamp = datetime.fromisoformat(mention["timestamp"]).strftime("%I:%M %p")
                except:
                    timestamp = "--:--"
                channel = mention.get("channel", "?")[:15]
                user = mention.get("user", "?")[:12]
                text = mention.get("text", "")[:60]
                lines.append(f"  [red]⚠[/red] {timestamp} | [cyan]{channel}[/cyan] | [yellow]{user}[/yellow]")
                lines.append(f"    {text}")
            lines.append("")

        # Show unanswered questions
        if questions:
            lines.append("[bold yellow]❓ UNANSWERED QUESTIONS[/bold yellow]")
            for mention in questions[:3]:
                try:
                    timestamp = datetime.fromisoformat(mention["timestamp"]).strftime("%I:%M %p")
                except:
                    timestamp = "--:--"
                channel = mention.get("channel", "?")[:15]
                user = mention.get("user", "?")[:12]
                text = mention.get("text", "")[:60]
                lines.append(f"  [yellow]?[/yellow] {timestamp} | [cyan]{channel}[/cyan] | [yellow]{user}[/yellow]")
                lines.append(f"    {text}")
            lines.append("")

        # Show high-activity channels (>10 messages/hour)
        high_activity_channels = []
        for client_id, client_stats in self.stats.items():
            last_hour = client_stats.get("messages_last_hour", 0)
            if last_hour > 10:
                channels = client_stats.get("active_channels", [])
                for channel in channels:
                    high_activity_channels.append((channel, last_hour, client_id))

        if high_activity_channels:
            lines.append("[bold yellow on black]⚡ HIGH ACTIVITY CHANNELS[/bold yellow on black]")
            for channel, count, client_id in high_activity_channels[:3]:
                client_display = client_id[:15] if len(client_id) <= 15 else client_id[:12] + "..."
                lines.append(f"  [yellow]⚡[/yellow] [cyan]{channel}[/cyan] - {count} msgs/hr ([dim]{client_display}[/dim])")

        if not direct_mentions and not questions and not high_activity_channels:
            lines.append("[dim]All clear - no urgent items[/dim]")

        return "\n".join(lines)


class ChannelActivityWidget(Static):
    """Widget displaying channel activity across all clients"""

    mentions = reactive([])
    stats = reactive({})

    def render(self) -> str:
        lines = []

        if not self.mentions:
            lines.append("[dim]No channel activity yet...[/dim]")
            return "\n".join(lines)

        # Count messages per channel in last hour
        from collections import defaultdict
        channel_counts = defaultdict(int)
        now = datetime.now()

        for mention in self.mentions:
            try:
                timestamp = datetime.fromisoformat(mention["timestamp"])
                hours_ago = (now - timestamp).total_seconds() / 3600
                if hours_ago <= 1:
                    channel = mention.get("channel", "unknown")
                    channel_counts[channel] += 1
            except:
                continue

        if not channel_counts:
            lines.append("[dim]No recent channel activity[/dim]")
            return "\n".join(lines)

        # Sort by activity level
        sorted_channels = sorted(channel_counts.items(), key=lambda x: x[1], reverse=True)

        for channel, count in sorted_channels[:10]:
            # Color code by activity level
            if count > 10:
                indicator = "[red]🔥[/red]"
                bar = "[red]" + "█" * min(count, 20) + "[/red]"
            elif count > 5:
                indicator = "[yellow]⚡[/yellow]"
                bar = "[yellow]" + "█" * min(count, 20) + "[/yellow]"
            else:
                indicator = "[green]•[/green]"
                bar = "[green]" + "█" * count + "[/green]"

            channel_display = channel[:20] if len(channel) <= 20 else channel[:17] + "..."
            lines.append(f"{indicator} [cyan]{channel_display:<20}[/cyan] │ {bar} {count}")

        return "\n".join(lines)


class TopActivityWidget(Static):
    """Widget displaying top channels and top users by activity"""

    mentions = reactive([])

    def render(self) -> str:
        lines = ["[bold yellow]🏆 Top Activity (Today)[/bold yellow]\n"]

        if not self.mentions:
            lines.append("[dim]No activity data yet...[/dim]")
            return "\n".join(lines)

        # Count mentions by channel and user
        from collections import Counter

        channel_counts = Counter()
        user_counts = Counter()

        for mention in self.mentions:
            channel_counts[mention.get("channel", "unknown")] += 1
            user_counts[mention.get("user", "unknown")] += 1

        if not channel_counts and not user_counts:
            lines.append("[dim]No activity data yet...[/dim]")
            return "\n".join(lines)

        # Get top 5 channels
        top_channels = channel_counts.most_common(5)
        total_mentions = sum(channel_counts.values())

        # Display top channels
        lines.append("[bold cyan]Top Channels:[/bold cyan]")
        max_channel_count = top_channels[0][1] if top_channels else 1

        for i, (channel, count) in enumerate(top_channels, 1):
            # Calculate percentage
            percentage = int((count / total_mentions) * 100) if total_mentions > 0 else 0

            # Create visual bar (max 12 chars)
            bar_length = int((count / max_channel_count) * 12) if max_channel_count > 0 else 0

            # Color code by activity level
            if count > 20:
                bar_color = "red"
            elif count > 10:
                bar_color = "yellow"
            else:
                bar_color = "green"

            bar = f"[{bar_color}]" + "█" * bar_length + f"[/{bar_color}]"

            # Format channel name (max 15 chars)
            channel_display = channel[:15] if len(channel) <= 15 else channel[:12] + "..."

            lines.append(f"{i}. [cyan]{channel_display:<15}[/cyan] {bar} {count} ({percentage}%)")

        # Add spacing
        lines.append("")

        # Get top 5 users
        top_users = user_counts.most_common(5)

        # Display top users
        lines.append("[bold magenta]Top Users:[/bold magenta]")
        max_user_count = top_users[0][1] if top_users else 1

        for i, (user, count) in enumerate(top_users, 1):
            # Calculate percentage
            percentage = int((count / total_mentions) * 100) if total_mentions > 0 else 0

            # Create visual bar (max 12 chars)
            bar_length = int((count / max_user_count) * 12) if max_user_count > 0 else 0

            # Color code by activity level
            if count > 20:
                bar_color = "red"
            elif count > 10:
                bar_color = "yellow"
            else:
                bar_color = "green"

            bar = f"[{bar_color}]" + "█" * bar_length + f"[/{bar_color}]"

            # Format user name (max 15 chars)
            user_display = user[:15] if len(user) <= 15 else user[:12] + "..."

            lines.append(f"{i}. [magenta]{user_display:<15}[/magenta] {bar} {count} ({percentage}%)")

        return "\n".join(lines)


class ClientHealthWidget(Static):
    """Widget displaying client health status with last check-in times"""

    stats = reactive({})
    connected_clients = reactive({})

    def render(self) -> str:
        lines = []

        if not self.stats:
            lines.append("[dim]No clients connected...[/dim]")
            return "\n".join(lines)

        now = datetime.now()
        active_count = 0
        idle_count = 0
        stale_count = 0

        # Sort clients by status (active first, then idle, then stale)
        client_status = []

        for client_id, client_stats in self.stats.items():
            # Get last seen timestamp from connected_clients or use current time
            last_seen = self.connected_clients.get(client_id)

            if not last_seen:
                # No last_seen data, assume stale
                status = "stale"
                status_icon = "🔴"
                status_color = "red"
                time_ago = "unknown"
                stale_count += 1
            else:
                # Calculate time since last check-in
                if isinstance(last_seen, str):
                    try:
                        last_seen = datetime.fromisoformat(last_seen)
                    except:
                        last_seen = now

                time_diff = (now - last_seen).total_seconds()

                # Categorize by time since last check-in
                if time_diff < 300:  # < 5 minutes
                    status = "active"
                    status_icon = "🟢"
                    status_color = "green"
                    active_count += 1
                    if time_diff < 60:
                        time_ago = f"{int(time_diff)}s ago"
                    else:
                        time_ago = f"{int(time_diff / 60)}m ago"
                elif time_diff < 3600:  # < 1 hour
                    status = "idle"
                    status_icon = "🟡"
                    status_color = "yellow"
                    idle_count += 1
                    time_ago = f"{int(time_diff / 60)}m ago"
                else:  # > 1 hour
                    status = "stale"
                    status_icon = "🔴"
                    status_color = "red"
                    stale_count += 1
                    hours = int(time_diff / 3600)
                    time_ago = f"{hours}h ago"

            client_status.append((client_id, status, status_icon, status_color, time_ago))

        # Sort by status priority (active, idle, stale)
        status_priority = {"active": 0, "idle": 1, "stale": 2}
        client_status.sort(key=lambda x: status_priority[x[1]])

        # Add summary line
        lines.append(f"[green]Active: {active_count}[/green] │ [yellow]Idle: {idle_count}[/yellow] │ [red]Stale: {stale_count}[/red]\n")

        # Show warning if any clients are stale
        if stale_count > 0:
            lines.append("[red]⚠ Warning: Some clients haven't checked in recently[/red]\n")

        # List each client with status
        for client_id, status, icon, color, time_ago in client_status[:6]:  # Show up to 6 clients
            display_id = client_id[:18] if len(client_id) <= 18 else client_id[:15] + "..."
            lines.append(f"{icon} [{color}]{display_id:<18}[/{color}] │ {time_ago}")

        return "\n".join(lines)


class PeakHoursWidget(Static):
    """Widget displaying peak hours summary and current activity comparison"""

    mentions = reactive([])

    def render(self) -> str:
        lines = []

        if not self.mentions:
            lines.append("[dim]No activity data yet...[/dim]")
            return "\n".join(lines)

        # Count mentions per hour (for today only)
        from collections import defaultdict
        hourly_counts = defaultdict(int)
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        for mention in self.mentions:
            try:
                timestamp = datetime.fromisoformat(mention["timestamp"])
                # Only count today's mentions
                if timestamp >= today_start:
                    hour = timestamp.hour
                    hourly_counts[hour] += 1
            except:
                continue

        if not hourly_counts:
            lines.append("[dim]No activity data for today[/dim]")
            return "\n".join(lines)

        # Find peak hours (top 2-3 hours)
        sorted_hours = sorted(hourly_counts.items(), key=lambda x: x[1], reverse=True)
        peak_hours = sorted_hours[:3]  # Top 3 hours

        # Format peak hours
        peak_hour_ranges = []
        for hour, count in peak_hours:
            if count > 0:
                # Convert to 12-hour format
                hour_12 = hour % 12
                if hour_12 == 0:
                    hour_12 = 12
                am_pm = "am" if hour < 12 else "pm"
                peak_hour_ranges.append(f"{hour_12}{am_pm}")

        if peak_hour_ranges:
            lines.append(f"[bold]Busiest hours:[/bold] {', '.join(peak_hour_ranges[:3])}")

        # Current hour status
        current_hour = now.hour
        current_count = hourly_counts.get(current_hour, 0)
        avg_count = sum(hourly_counts.values()) / len(hourly_counts) if hourly_counts else 0

        # Check if we're in peak time
        is_peak = current_hour in [h for h, c in peak_hours]

        if is_peak:
            lines.append("[yellow]⚡ You're in a peak activity period[/yellow]")
        else:
            lines.append("[green]☀ Light activity period[/green]")

        # Total mentions today
        total_today = sum(hourly_counts.values())
        lines.append(f"\n[bold]Today:[/bold] {total_today} mentions")

        # Compare to average
        if avg_count > 0:
            if current_count > avg_count * 1.5:
                lines.append("[red]📈 +50% above average[/red]")
            elif current_count > avg_count * 1.2:
                lines.append("[yellow]📈 +20% above average[/yellow]")
            elif current_count < avg_count * 0.5:
                lines.append("[green]📉 -50% below average[/green]")
            else:
                lines.append("[dim]≈ Normal activity level[/dim]")

        # Show current hour activity
        current_hour_12 = current_hour % 12
        if current_hour_12 == 0:
            current_hour_12 = 12
        am_pm = "am" if current_hour < 12 else "pm"
        lines.append(f"\n[bold]Current hour ({current_hour_12}{am_pm}):[/bold] {current_count} mentions")

        return "\n".join(lines)


class MetricCard(Static):
    """Reusable metric card widget for analytics"""

    title = reactive("")
    value = reactive("")
    subtitle = reactive("")
    color = reactive("cyan")

    def render(self) -> str:
        return f"""[bold {self.color}]{self.title}[/bold {self.color}]
[bold white]{self.value}[/bold white]
[dim]{self.subtitle}[/dim]"""


class ChannelBreakdownTable(DataTable):
    """Table showing channel breakdown statistics"""

    mentions = reactive([])

    def on_mount(self) -> None:
        """Set up the table structure"""
        self.cursor_type = "row"
        self.zebra_stripes = True

        # Add columns
        self.add_column("Channel", key="channel", width=20)
        self.add_column("Mentions", key="mentions", width=10)
        self.add_column("Questions", key="questions", width=12)
        self.add_column("Response Rate", key="response_rate", width=15)
        self.add_column("Avg Response Time", key="avg_time", width=18)

    def watch_mentions(self, mentions: list) -> None:
        """Update table when mentions change"""
        self.clear()

        if not mentions:
            return

        # Group by channel
        from collections import defaultdict
        channel_data = defaultdict(lambda: {
            "total": 0,
            "questions": 0,
            "responded": 0,
            "response_times": []
        })

        for mention in mentions:
            channel = mention.get("channel", "unknown")
            channel_data[channel]["total"] += 1

            if mention.get("is_question"):
                channel_data[channel]["questions"] += 1

            if mention.get("responded"):
                channel_data[channel]["responded"] += 1

        # Sort by total mentions
        sorted_channels = sorted(
            channel_data.items(),
            key=lambda x: x[1]["total"],
            reverse=True
        )[:15]  # Show top 15 channels

        from rich.text import Text
        for channel, data in sorted_channels:
            # Format channel name
            channel_display = channel[:20] if len(channel) <= 20 else channel[:17] + "..."

            # Calculate response rate
            if data["total"] > 0:
                response_rate = int((data["responded"] / data["total"]) * 100)
            else:
                response_rate = 0

            # Color code response rate
            if response_rate >= 80:
                rate_color = "green"
            elif response_rate >= 50:
                rate_color = "yellow"
            else:
                rate_color = "red"

            self.add_row(
                Text(channel_display, style="cyan"),
                str(data["total"]),
                str(data["questions"]),
                Text(f"{response_rate}%", style=rate_color),
                Text("~2h", style="dim")  # Placeholder for now
            )


class ResponseTimeWidget(Static):
    """Widget showing response time statistics"""

    mentions = reactive([])

    def render(self) -> str:
        lines = ["[bold yellow]⏱ Response Time Analysis[/bold yellow]\n"]

        if not self.mentions:
            lines.append("[dim]No data available[/dim]")
            return "\n".join(lines)

        # Calculate response statistics
        responded = [m for m in self.mentions if m.get("responded")]
        questions = [m for m in self.mentions if m.get("is_question")]
        responded_questions = [m for m in questions if m.get("responded")]

        total_mentions = len(self.mentions)
        total_responded = len(responded)
        total_questions = len(questions)
        questions_responded = len(responded_questions)

        # Overall response rate
        if total_mentions > 0:
            response_rate = int((total_responded / total_mentions) * 100)
            if response_rate >= 80:
                rate_color = "green"
            elif response_rate >= 50:
                rate_color = "yellow"
            else:
                rate_color = "red"

            lines.append(f"[bold]Overall Response Rate:[/bold] [{rate_color}]{response_rate}%[/{rate_color}]")
            lines.append(f"  Responded: {total_responded}/{total_mentions}")
        else:
            lines.append("[dim]No mentions to analyze[/dim]")

        lines.append("")

        # Questions response rate
        if total_questions > 0:
            q_rate = int((questions_responded / total_questions) * 100)
            if q_rate >= 80:
                q_color = "green"
            elif q_rate >= 50:
                q_color = "yellow"
            else:
                q_color = "red"

            lines.append(f"[bold]Questions Response Rate:[/bold] [{q_color}]{q_rate}%[/{q_color}]")
            lines.append(f"  Responded: {questions_responded}/{total_questions}")
        else:
            lines.append("[dim]No questions to analyze[/dim]")

        lines.append("")

        # Pending items
        pending = total_mentions - total_responded
        pending_questions = total_questions - questions_responded

        if pending > 0:
            lines.append(f"[bold red]Pending Responses:[/bold red]")
            lines.append(f"  Total: {pending}")
            if pending_questions > 0:
                lines.append(f"  [yellow]Questions: {pending_questions}[/yellow]")
        else:
            lines.append("[green]✓ All caught up![/green]")

        return "\n".join(lines)


class QuickStatsWidget(Static):
    """Widget showing quick stats for analytics dashboard"""

    mentions = reactive([])
    stats = reactive({})

    def render(self) -> str:
        if not self.mentions and not self.stats:
            return "[dim]Loading analytics...[/dim]"

        # Calculate metrics
        total_mentions = len(self.mentions)
        unread = sum(1 for m in self.mentions if not m.get("responded"))
        questions = sum(1 for m in self.mentions if m.get("is_question"))

        # Count unique channels and users
        unique_channels = len(set(m.get("channel") for m in self.mentions))
        unique_users = len(set(m.get("user") for m in self.mentions))

        # Active clients
        active_clients = len(self.stats)

        return f"""[bold cyan]📊 Quick Stats[/bold cyan]

[yellow]Total Mentions:[/yellow]     {total_mentions:>6}
[yellow]Unread:[/yellow]             {unread:>6}
[yellow]Questions:[/yellow]          {questions:>6}
[yellow]Active Channels:[/yellow]   {unique_channels:>6}
[yellow]Active Users:[/yellow]      {unique_users:>6}
[yellow]Connected Clients:[/yellow] {active_clients:>6}"""


class MonitorCommands(Provider):
    """Custom command provider for Slack Monitor"""

    async def search(self, query: str) -> Hits:
        """Search for commands matching the query"""
        matcher = self.matcher(query)

        # Define commands with their actions
        app = self.app

        def make_toggle_callback(title: str):
            """Create a callback to toggle a collapsible by title"""
            def callback() -> None:
                for collapsible in app.query(Collapsible):
                    if collapsible.title == title:
                        collapsible.collapsed = not collapsible.collapsed
                        break
            return callback

        def make_focus_callback(widget_id: str):
            """Create a callback to focus a widget"""
            def callback() -> None:
                try:
                    app.query_one(f"#{widget_id}").focus()
                except:
                    pass
            return callback

        commands = [
            ("Refresh Data", app.action_refresh, "Refresh all data from server"),
            ("Toggle Stats", make_toggle_callback("📊 Stats Overview"), "Show/hide Stats Overview section"),
            ("Toggle Channel Activity", make_toggle_callback("📺 Channel Activity"), "Show/hide Channel Activity section"),
            ("Toggle Client Health", make_toggle_callback("💚 Client Health Monitor"), "Show/hide Client Health Monitor section"),
            ("Toggle Peak Hours", make_toggle_callback("📈 Peak Hours Summary"), "Show/hide Peak Hours Summary section"),
            ("Focus Priority Alerts", make_focus_callback("priority-alerts-widget"), "Jump to Priority Alerts widget"),
            ("Focus Mentions", make_focus_callback("mentions-table"), "Jump to Mentions Table widget"),
            ("Focus Chart", make_focus_callback("chart-widget"), "Jump to Mentions Graph widget"),
        ]

        for name, callback, help_text in commands:
            score = matcher.match(name)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(name),
                    callback,
                    help=help_text
                )


class SlackMonitorApp(App):
    """Textual application for Slack monitoring"""

    # Register custom command provider
    COMMANDS = {MonitorCommands}

    # Theme definitions
    THEMES = {
        "dark": {
            "name": "Dark (Default)",
            "colors": {
                "primary": "#0178D4",
                "secondary": "#A45EE5",
                "accent": "#00D9FF",
                "warning": "#FFE66D",
                "error": "#F05454",
                "success": "#00C896",
                "background": "#1E1E1E",
                "surface": "#252525",
                "panel": "#2D2D2D",
            }
        },
        "light": {
            "name": "Light",
            "colors": {
                "primary": "#0066CC",
                "secondary": "#8B5CF6",
                "accent": "#0EA5E9",
                "warning": "#F59E0B",
                "error": "#EF4444",
                "success": "#10B981",
                "background": "#FFFFFF",
                "surface": "#F5F5F5",
                "panel": "#E5E5E5",
            }
        },
        "nord": {
            "name": "Nord",
            "colors": {
                "primary": "#88C0D0",
                "secondary": "#B48EAD",
                "accent": "#8FBCBB",
                "warning": "#EBCB8B",
                "error": "#BF616A",
                "success": "#A3BE8C",
                "background": "#2E3440",
                "surface": "#3B4252",
                "panel": "#434C5E",
            }
        },
        "dracula": {
            "name": "Dracula",
            "colors": {
                "primary": "#BD93F9",
                "secondary": "#FF79C6",
                "accent": "#8BE9FD",
                "warning": "#F1FA8C",
                "error": "#FF5555",
                "success": "#50FA7B",
                "background": "#282A36",
                "surface": "#1E1F29",
                "panel": "#343746",
            }
        }
    }

    CSS = """
    Screen {
        background: $surface;
    }

    #main-tabs {
        height: 1fr;
    }

    TabPane {
        height: 1fr;
    }

    /* ==================== MONITOR TAB ==================== */

    #search-container {
        height: 3;
        padding: 0 1;
        margin: 0 0 1 0;
    }

    #search-input {
        width: 1fr;
    }

    #monitor-container {
        height: 1fr;
        layout: horizontal;
    }

    #left-panel {
        width: 30%;
        height: 1fr;
        layout: vertical;
    }

    #right-panel {
        width: 70%;
        height: 1fr;
        layout: vertical;
    }

    Collapsible {
        border: solid $primary;
        margin: 0 0 1 0;
    }

    #stats-widget {
        height: auto;
        padding: 1;
    }

    #channel-activity-widget {
        height: auto;
        padding: 1;
    }

    #client-health-widget {
        height: auto;
        padding: 1;
    }

    #peak-hours-widget {
        height: auto;
        padding: 1;
    }

    #priority-alerts-widget {
        height: 18;
        border: solid red;
        padding: 1;
        margin: 0 0 1 0;
    }

    #mentions-table {
        height: 1fr;
        border: solid magenta;
        padding: 1;
        margin: 0 0 1 0;
    }

    #chart-container {
        height: 20;
        layout: horizontal;
    }

    #chart-widget {
        width: 55%;
        border: solid green;
        padding: 1;
    }

    #top-activity-widget {
        width: 45%;
        border: solid yellow;
        padding: 1;
        margin-left: 1;
    }

    DataTable {
        height: 1fr;
    }

    DataTable > .datatable--header {
        text-style: bold;
        background: $boost;
    }

    DataTable > .datatable--cursor {
        background: $accent 20%;
    }

    #status-bar {
        height: 1;
        background: $panel;
        padding: 0 1;
    }

    #loading-indicator {
        layer: overlay;
        offset: 50% 50%;
        display: none;
    }

    #loading-indicator.show {
        display: block;
    }

    .pulsate {
        border: heavy red;
        text-style: bold;
    }

    .high-activity {
        background: #3a3a00;
    }

    /* ==================== ANALYTICS TAB ==================== */

    #analytics-container {
        height: 1fr;
        layout: vertical;
        padding: 1;
    }

    #analytics-cards {
        height: 12;
        layout: horizontal;
        margin: 0 0 1 0;
    }

    #quick-stats-widget {
        width: 1fr;
        border: solid cyan;
        padding: 1;
        margin-right: 1;
    }

    #response-time-widget {
        width: 1fr;
        border: solid yellow;
        padding: 1;
    }

    #analytics-breakdown {
        height: 1fr;
        border: solid magenta;
        padding: 1;
        margin: 0 0 1 0;
    }

    #channel-breakdown-table {
        height: 1fr;
        margin-top: 1;
    }

    #analytics-sparklines {
        height: 15;
        border: solid green;
        padding: 1;
    }

    #analytics-chart-widget {
        height: 1fr;
    }

    /* ==================== SETTINGS TAB ==================== */

    #settings-container {
        height: 1fr;
        layout: vertical;
        padding: 2;
    }

    #settings-content {
        width: 80;
        height: auto;
    }

    #server-config,
    #theme-settings,
    #display-settings,
    #info-section,
    #shortcuts-section {
        padding: 0 0 1 0;
    }

    #theme-buttons {
        height: auto;
        layout: horizontal;
        margin: 1 0;
    }

    #theme-buttons Button {
        margin-right: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("ctrl+p", "command_palette", "Commands"),
        ("ctrl+1", "switch_tab_monitor", "Monitor Tab"),
        ("ctrl+2", "switch_tab_analytics", "Analytics Tab"),
        ("ctrl+3", "switch_tab_settings", "Settings Tab"),
        ("t", "cycle_theme", "Next Theme"),
        ("ctrl+f", "focus_search", "Search"),
        ("ctrl+e", "export_data", "Export"),
    ]

    def __init__(self):
        super().__init__()
        self.data = {
            "mentions": [],
            "stats": {},
            "messages_per_hour": {},
            "active_clients": []
        }
        self.selected_theme = "dark"
        self.search_filter = ""

    def compose(self) -> ComposeResult:
        """Create child widgets with tabbed interface"""
        yield Header()

        with TabbedContent(id="main-tabs"):
            # ==================== MONITOR TAB ====================
            with TabPane("Monitor", id="monitor-tab"):
                # Search bar at the top
                with Container(id="search-container"):
                    yield Input(placeholder="Search mentions (Ctrl+F to focus)...", id="search-input")

                with Container(id="monitor-container"):
                    with Vertical(id="left-panel"):
                        # Stats widget - expanded by default (most important)
                        with Collapsible(title="📊 Stats Overview", collapsed=False):
                            yield StatsWidget(id="stats-widget")

                        # Channel Activity - expanded by default
                        with Collapsible(title="📺 Channel Activity", collapsed=False):
                            yield ChannelActivityWidget(id="channel-activity-widget")

                        # Client Health - collapsed by default to save space
                        with Collapsible(title="💚 Client Health Monitor", collapsed=True):
                            yield ClientHealthWidget(id="client-health-widget")

                        # Peak Hours - collapsed by default to save space
                        with Collapsible(title="📈 Peak Hours Summary", collapsed=True):
                            yield PeakHoursWidget(id="peak-hours-widget")

                    with Vertical(id="right-panel"):
                        yield PriorityAlertsWidget(id="priority-alerts-widget")
                        yield MentionsTable(id="mentions-table")
                        with Horizontal(id="chart-container"):
                            yield MentionsGraphWidget(id="chart-widget")
                            yield TopActivityWidget(id="top-activity-widget")

            # ==================== ANALYTICS TAB ====================
            with TabPane("Analytics", id="analytics-tab"):
                with Container(id="analytics-container"):
                    # Top row - Quick stats cards
                    with Horizontal(id="analytics-cards"):
                        yield QuickStatsWidget(id="quick-stats-widget")
                        yield ResponseTimeWidget(id="response-time-widget")

                    # Middle row - Channel breakdown table
                    with Container(id="analytics-breakdown"):
                        yield Label("[bold cyan]📊 Channel Breakdown[/bold cyan]")
                        yield ChannelBreakdownTable(id="channel-breakdown-table")

                    # Bottom row - Additional sparklines
                    with Container(id="analytics-sparklines"):
                        yield Label("[bold green]📈 Activity Trends[/bold green]")
                        yield MentionsGraphWidget(id="analytics-chart-widget")

            # ==================== SETTINGS TAB ====================
            with TabPane("Settings", id="settings-tab"):
                with Container(id="settings-container"):
                    with Vertical(id="settings-content"):
                        yield Label("[bold cyan]⚙ Dashboard Settings[/bold cyan]")
                        yield Label("")

                        # Server configuration
                        with Container(id="server-config"):
                            yield Label("[bold yellow]Server Configuration[/bold yellow]")
                            yield Label(f"Server URL: {SERVER_URL}", id="server-url-label")
                            yield Label(f"WebSocket: {'Connected' if WS_URL else 'Disconnected'}", id="ws-status-label")
                            yield Label("")

                        # Theme settings
                        with Container(id="theme-settings"):
                            yield Label("[bold yellow]Theme[/bold yellow]")
                            yield Label("Current theme: Dark (Default)", id="current-theme-label")
                            with Horizontal(id="theme-buttons"):
                                yield Button("Dark", id="theme-dark", variant="primary")
                                yield Button("Light", id="theme-light")
                                yield Button("Nord", id="theme-nord")
                                yield Button("Dracula", id="theme-dracula")
                            yield Label("")

                        # Display settings
                        with Container(id="display-settings"):
                            yield Label("[bold yellow]Display Settings[/bold yellow]")
                            yield Label("Auto-refresh: Enabled", id="auto-refresh-label")
                            yield Label("Update interval: 30s", id="update-interval-label")
                            yield Label("")

                        # Info section
                        with Container(id="info-section"):
                            yield Label("[bold yellow]System Information[/bold yellow]")
                            yield Label(f"Local IP: {get_local_ip()}", id="local-ip-label")
                            ngrok = get_ngrok_url()
                            if ngrok:
                                yield Label(f"Public URL: {ngrok}", id="ngrok-url-label")
                            else:
                                yield Label("Public URL: Not available (ngrok not running)", id="ngrok-url-label")
                            yield Label("")

                        # Keyboard shortcuts
                        with Container(id="shortcuts-section"):
                            yield Label("[bold yellow]Keyboard Shortcuts[/bold yellow]")
                            yield Label("  [cyan]Ctrl+1[/cyan]   - Monitor Tab")
                            yield Label("  [cyan]Ctrl+2[/cyan]   - Analytics Tab")
                            yield Label("  [cyan]Ctrl+3[/cyan]   - Settings Tab")
                            yield Label("  [cyan]Ctrl+P[/cyan]   - Command Palette")
                            yield Label("  [cyan]Ctrl+F[/cyan]   - Focus Search")
                            yield Label("  [cyan]Ctrl+E[/cyan]   - Export Data")
                            yield Label("  [cyan]T[/cyan]        - Next Theme")
                            yield Label("  [cyan]R[/cyan]        - Refresh Data")
                            yield Label("  [cyan]Q[/cyan]        - Quit")

        with Container(id="status-bar"):
            yield ConnectionStatus()

        # Loading indicator (initially hidden)
        yield LoadingIndicator(id="loading-indicator")

        yield Footer()

    async def on_mount(self) -> None:
        """Called when app starts"""
        self.title = "Slack Activity Monitor"

        # Check for ngrok URL
        ngrok_url = get_ngrok_url()
        if ngrok_url:
            self.sub_title = f"ngrok: {ngrok_url}"
        else:
            self.sub_title = ""

        # Start data fetching
        self.fetch_initial_data()
        self.listen_to_websocket()

    @work(exclusive=True)
    async def fetch_initial_data(self) -> None:
        """Fetch initial data from server"""
        status_widget = self.query_one(ConnectionStatus)
        loading_indicator = self.query_one("#loading-indicator", LoadingIndicator)

        # Show loading indicator
        loading_indicator.add_class("show")

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

                # Show success notification
                total_mentions = len(self.data["mentions"])
                unread = sum(s.get("unread_count", 0) for s in self.data["stats"].values())
                self.notify(
                    f"✓ Data refreshed: {total_mentions} mentions ({unread} unread)",
                    severity="information",
                    timeout=3
                )

        except Exception as e:
            status_widget.status = f"Error: {str(e)[:30]}"
            status_widget.status_color = "red"
            self.notify(f"⚠ Connection error: {str(e)[:50]}", severity="error", timeout=5)
        finally:
            # Hide loading indicator
            loading_indicator.remove_class("show")

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
                            mention = msg_data["data"]
                            self.data["mentions"].append(mention)
                            self.update_widgets()

                            # Show toast notification for new mention
                            channel = mention.get("channel", "unknown")
                            user = mention.get("user", "unknown")
                            is_question = mention.get("is_question", False)
                            icon = "❓" if is_question else "💬"
                            self.notify(
                                f"{icon} New mention from {user} in #{channel}",
                                severity="warning" if is_question else "information",
                                timeout=4
                            )

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
        # ==================== MONITOR TAB WIDGETS ====================

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

        # Update priority alerts widget
        priority_widget = self.query_one(PriorityAlertsWidget)
        priority_widget.mentions = self.data["mentions"]
        priority_widget.stats = self.data["stats"]

        # Update mentions table
        mentions_widget = self.query_one(MentionsTable)
        mentions_widget.search_filter = self.search_filter
        mentions_widget.mentions = self.data["mentions"]

        # Update channel activity widget
        channel_widget = self.query_one(ChannelActivityWidget)
        channel_widget.mentions = self.data["mentions"]
        channel_widget.stats = self.data["stats"]

        # Update chart (Monitor tab)
        chart_widget = self.query_one("#chart-widget", MentionsGraphWidget)
        chart_widget.all_mentions = self.data["mentions"]

        # Update top activity widget
        top_activity_widget = self.query_one("#top-activity-widget", TopActivityWidget)
        top_activity_widget.mentions = self.data["mentions"]

        # Update client health widget
        client_health_widget = self.query_one(ClientHealthWidget)
        client_health_widget.stats = self.data["stats"]
        # Extract last seen timestamps from stats data
        connected_clients_map = {}
        for client_id, client_stats in self.data["stats"].items():
            timestamp = client_stats.get("timestamp")
            if timestamp:
                connected_clients_map[client_id] = timestamp
        client_health_widget.connected_clients = connected_clients_map

        # Update peak hours widget
        peak_hours_widget = self.query_one(PeakHoursWidget)
        peak_hours_widget.mentions = self.data["mentions"]

        # ==================== ANALYTICS TAB WIDGETS ====================

        # Update quick stats widget
        quick_stats_widget = self.query_one(QuickStatsWidget)
        quick_stats_widget.mentions = self.data["mentions"]
        quick_stats_widget.stats = self.data["stats"]

        # Update response time widget
        response_time_widget = self.query_one(ResponseTimeWidget)
        response_time_widget.mentions = self.data["mentions"]

        # Update channel breakdown table
        channel_breakdown_widget = self.query_one(ChannelBreakdownTable)
        channel_breakdown_widget.mentions = self.data["mentions"]

        # Update analytics sparklines
        analytics_chart_widget = self.query_one("#analytics-chart-widget", MentionsGraphWidget)
        analytics_chart_widget.all_mentions = self.data["mentions"]

    def action_refresh(self) -> None:
        """Refresh data"""
        self.fetch_initial_data()

    def action_quit(self) -> None:
        """Quit the app"""
        self.exit()

    def action_switch_tab_monitor(self) -> None:
        """Switch to Monitor tab"""
        tabs = self.query_one(TabbedContent)
        tabs.active = "monitor-tab"

    def action_switch_tab_analytics(self) -> None:
        """Switch to Analytics tab"""
        tabs = self.query_one(TabbedContent)
        tabs.active = "analytics-tab"

    def action_switch_tab_settings(self) -> None:
        """Switch to Settings tab"""
        tabs = self.query_one(TabbedContent)
        tabs.active = "settings-tab"

    def action_cycle_theme(self) -> None:
        """Cycle through available themes"""
        theme_keys = list(self.THEMES.keys())
        current_index = theme_keys.index(self.selected_theme)
        next_index = (current_index + 1) % len(theme_keys)
        new_theme = theme_keys[next_index]
        self.switch_theme(new_theme)

    def switch_theme(self, theme_name: str) -> None:
        """Switch to a specific theme"""
        if theme_name not in self.THEMES:
            return

        self.selected_theme = theme_name
        theme = self.THEMES[theme_name]

        # Update the theme label in settings
        try:
            theme_label = self.query_one("#current-theme-label", Label)
            theme_label.update(f"Current theme: {theme['name']}")
        except:
            pass

        # Update button variants
        for theme_key in self.THEMES.keys():
            try:
                button = self.query_one(f"#theme-{theme_key}", Button)
                button.variant = "primary" if theme_key == theme_name else "default"
            except:
                pass

        # Show notification
        self.notify(
            f"Theme changed to {theme['name']}",
            severity="information",
            timeout=2
        )

    def action_focus_search(self) -> None:
        """Focus the search input"""
        try:
            search_input = self.query_one("#search-input", Input)
            search_input.focus()
            self.notify("Search focused - type to filter mentions", severity="information", timeout=2)
        except:
            self.notify("Search not available on this tab", severity="warning", timeout=2)

    def action_export_data(self) -> None:
        """Export data to file"""
        import json
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Export to JSON
        export_data = {
            "exported_at": datetime.now().isoformat(),
            "mentions": self.data["mentions"],
            "stats": self.data["stats"],
            "active_clients": self.data.get("active_clients", []),
        }

        filename = f"slack_monitor_export_{timestamp}.json"
        try:
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2)

            self.notify(
                f"✓ Data exported to {filename}",
                severity="information",
                timeout=4
            )
        except Exception as e:
            self.notify(
                f"✗ Export failed: {str(e)[:50]}",
                severity="error",
                timeout=4
            )

    @on(Button.Pressed, "#theme-dark")
    def on_theme_dark(self) -> None:
        """Switch to dark theme"""
        self.switch_theme("dark")

    @on(Button.Pressed, "#theme-light")
    def on_theme_light(self) -> None:
        """Switch to light theme"""
        self.switch_theme("light")

    @on(Button.Pressed, "#theme-nord")
    def on_theme_nord(self) -> None:
        """Switch to nord theme"""
        self.switch_theme("nord")

    @on(Button.Pressed, "#theme-dracula")
    def on_theme_dracula(self) -> None:
        """Switch to dracula theme"""
        self.switch_theme("dracula")

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Handle search input changes"""
        self.search_filter = event.value.lower()
        # Filter mentions based on search
        self.update_widgets()


def main():
    """Run the dashboard"""
    app = SlackMonitorApp()
    app.run()


if __name__ == "__main__":
    main()
