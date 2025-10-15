#!/usr/bin/env python3
"""
Mock Data Generator for Slack Monitor
Generates realistic test data for quick dashboard iteration
"""

import random
from datetime import datetime, timedelta
from typing import List, Dict
from pydantic import BaseModel

# Mock data templates
MOCK_CLIENTS = [
    "MacBook-Pro.local",
    "iMac-Office.local",
    "MacBook-Air-Home.local",
    "Mac-Mini-Server.local",
    "MacBook-Work.local"
]

MOCK_CHANNELS = [
    "engineering",
    "sales",
    "support",
    "marketing",
    "general",
    "random",
    "product",
    "design",
    "ops",
    "leadership"
]

MOCK_USERS = [
    "Alice",
    "Bob",
    "Carol",
    "David",
    "Emma",
    "Frank",
    "Grace",
    "Henry",
    "Iris",
    "Jack"
]

# Message templates with varying content
MESSAGE_TEMPLATES = [
    "Hey {mention}, can you help me with {topic}?",
    "{mention} what do you think about {topic}?",
    "Thanks {mention}! That solved the {topic} issue.",
    "{mention} heads up - {topic} is down",
    "FYI {mention} - shipped {topic} to production",
    "{mention} quick question about {topic}",
    "Meeting at 2pm to discuss {topic}. {mention} can you join?",
    "{mention} great work on {topic}!",
    "Did anyone see {mention}'s update on {topic}?",
    "{mention} the client is asking about {topic}",
    "Breaking: {topic} just launched! cc {mention}",
    "{mention} can we sync on {topic} tomorrow?",
    "Reminder {mention}: {topic} deadline is Friday",
    "{mention} I'm blocked on {topic}, any ideas?",
    "{mention} let's prioritize {topic} this sprint",
]

TOPICS = [
    "the API",
    "the deployment",
    "the dashboard",
    "user authentication",
    "database migration",
    "performance issues",
    "the new feature",
    "customer feedback",
    "the bug fix",
    "code review",
    "the integration",
    "monitoring alerts",
    "test coverage",
    "documentation",
    "the release",
]

# Question templates (should end with ?)
QUESTION_TEMPLATES = [
    "{mention} can you review this PR?",
    "{mention} what's the status of {topic}?",
    "{mention} how should we handle {topic}?",
    "{mention} when can we ship {topic}?",
    "{mention} did you see the issue with {topic}?",
    "{mention} should we reschedule the {topic} meeting?",
    "{mention} any updates on {topic}?",
    "{mention} is {topic} ready for prod?",
]


class MockMention(BaseModel):
    """Mock mention data matching server's Mention model"""
    timestamp: str
    channel: str
    user: str
    text: str
    is_question: bool
    responded: bool
    client_id: str
    workspace: str = "Acme Corp"  # Default workspace name


class MockStats(BaseModel):
    """Mock stats data"""
    client_id: str
    unread_count: int
    messages_last_hour: int
    active_channels: List[str]
    timestamp: str


def generate_mock_mentions(
    num_mentions: int = 50,
    hours_spread: int = 12,
    clients: List[str] = None,
    channels: List[str] = None
) -> List[MockMention]:
    """
    Generate realistic mock mentions for TODAY

    Args:
        num_mentions: Number of mentions to generate
        hours_spread: Spread mentions across this many hours (default 12 for today)
        clients: List of client IDs (default: use MOCK_CLIENTS)
        channels: List of channels (default: use MOCK_CHANNELS)
    """
    if clients is None:
        clients = MOCK_CLIENTS[:3]  # Use 3 clients by default
    if channels is None:
        channels = MOCK_CHANNELS

    mentions = []
    now = datetime.now()

    # Calculate work hours range (8am to current time, or 8am-8pm if after 8pm)
    work_start = now.replace(hour=8, minute=0, second=0, microsecond=0)
    work_end = now.replace(hour=20, minute=0, second=0, microsecond=0)

    # If we're before 8am, no data should be generated for today yet
    if now.hour < 8:
        return mentions

    # If we're past 8pm, use 8pm as the end time, otherwise use current time
    effective_end = min(now, work_end)

    # Calculate the time range in seconds
    time_range_seconds = (effective_end - work_start).total_seconds()

    for i in range(num_mentions):
        # Generate random timestamp between 8am and current time (or 8pm)
        random_seconds = random.uniform(0, time_range_seconds)
        timestamp = work_start + timedelta(seconds=random_seconds)

        # Pick random elements
        client = random.choice(clients)
        channel = random.choice(channels)
        user = random.choice(MOCK_USERS)
        topic = random.choice(TOPICS)

        # 30% chance of being a question
        is_question = random.random() < 0.3

        if is_question:
            template = random.choice(QUESTION_TEMPLATES)
        else:
            template = random.choice(MESSAGE_TEMPLATES)

        # Format message
        text = template.format(mention="@you", topic=topic)

        # Add some variety
        if random.random() < 0.2:  # 20% chance of longer message
            text += f" We should also consider {random.choice(TOPICS)}."

        # 60% chance of being responded to if not recent (older than 2 hours)
        hours_old = (now - timestamp).total_seconds() / 3600
        if hours_old > 2:
            responded = random.random() < 0.6
        else:
            responded = False  # Recent messages likely unread

        mention = MockMention(
            timestamp=timestamp.isoformat(),
            channel=channel,
            user=user,
            text=text,
            is_question=is_question,
            responded=responded,
            client_id=client,
            workspace="Acme Corp"  # Default workspace
        )
        mentions.append(mention)

    return mentions


def generate_mock_stats(clients: List[str] = None) -> List[MockStats]:
    """Generate mock stats for clients"""
    if clients is None:
        clients = MOCK_CLIENTS[:3]

    stats = []
    now = datetime.now()

    for client in clients:
        # Random activity levels
        unread = random.randint(0, 15)
        last_hour = random.randint(0, 25)
        num_channels = random.randint(2, 6)
        active_channels = random.sample(MOCK_CHANNELS, num_channels)

        stat = MockStats(
            client_id=client,
            unread_count=unread,
            messages_last_hour=last_hour,
            active_channels=active_channels,
            timestamp=now.isoformat()
        )
        stats.append(stat)

    return stats


def generate_mock_channel_activity(
    hours: int = 13,  # 8am-8pm = 13 hours
    clients: List[str] = None,
    channels: List[str] = None
) -> List[Dict]:
    """Generate mock channel activity for graphs - TODAY ONLY (8am-8pm work hours)"""
    if clients is None:
        clients = MOCK_CLIENTS[:3]
    if channels is None:
        channels = random.sample(MOCK_CHANNELS, 5)

    activity = []
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_hour = now.hour

    # Generate activity for work hours (8am-8pm)
    work_start = 8
    work_end = 20

    # Generate hourly activity for each client and channel
    for client in clients:
        for hour in range(work_start, work_end + 1):
            # Only generate data for hours that have passed today
            if hour > current_hour:
                continue

            # Each channel has different activity patterns
            for channel in channels:
                # Simulate realistic activity patterns
                # Peak hours (10am-4pm) have more activity
                if 10 <= hour <= 16:
                    base_count = random.randint(8, 25)
                elif 8 <= hour <= 9 or 17 <= hour <= 20:
                    # Morning ramp-up and evening wind-down
                    base_count = random.randint(3, 12)
                else:
                    base_count = random.randint(0, 5)

                # Some channels are more active
                if channel in ["engineering", "support"]:
                    base_count = int(base_count * 1.5)

                activity.append({
                    "channel": channel,
                    "message_count": base_count,
                    "hour": hour,
                    "date": today,  # Always use today's date
                    "client_id": client
                })

    return activity


def generate_high_activity_scenario() -> Dict:
    """Generate a high-activity scenario for testing alerts - TODAY ONLY"""
    clients = MOCK_CLIENTS[:2]
    mentions = []
    now = datetime.now()

    # Generate burst of activity in last 2 hours (to ensure we're in today)
    for i in range(30):
        minutes_ago = random.randint(0, 120)
        timestamp = now - timedelta(minutes=minutes_ago)

        # Mostly direct mentions and questions
        user = random.choice(MOCK_USERS)
        channel = random.choice(["engineering", "support", "urgent"])
        is_question = random.random() < 0.7  # 70% questions

        if is_question:
            text = random.choice(QUESTION_TEMPLATES).format(
                mention="@you",
                topic=random.choice(TOPICS)
            )
        else:
            text = f"@you urgent: {random.choice(TOPICS)} needs attention!"

        mention = MockMention(
            timestamp=timestamp.isoformat(),
            channel=channel,
            user=user,
            text=text,
            is_question=is_question,
            responded=False,  # All unread
            client_id=random.choice(clients),
            workspace="Acme Corp"
        )
        mentions.append(mention)

    # Generate corresponding high activity stats
    stats = [
        MockStats(
            client_id=client,
            unread_count=random.randint(15, 30),
            messages_last_hour=random.randint(25, 50),
            active_channels=["engineering", "support", "urgent", "general"],
            timestamp=now.isoformat()
        )
        for client in clients
    ]

    return {
        "mentions": mentions,
        "stats": stats,
        "scenario": "high_activity"
    }


def generate_multi_job_scenario() -> Dict:
    """Generate scenario simulating multiple jobs/workspaces"""
    # Simulate 3 different workspaces (jobs)
    workspaces = [
        {
            "name": "Job1-Company-A",
            "channels": ["engineering", "product", "general"],
            "activity": "high"
        },
        {
            "name": "Job2-Company-B",
            "channels": ["support", "sales", "ops"],
            "activity": "medium"
        },
        {
            "name": "Job3-Freelance",
            "channels": ["client-work", "design", "random"],
            "activity": "low"
        }
    ]

    all_mentions = []
    all_stats = []
    now = datetime.now()

    for workspace in workspaces:
        client_id = workspace["name"]

        # Activity level affects message frequency
        if workspace["activity"] == "high":
            num_mentions = random.randint(15, 30)
        elif workspace["activity"] == "medium":
            num_mentions = random.randint(5, 15)
        else:
            num_mentions = random.randint(1, 5)

        # Generate mentions for this workspace (keep within today)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        max_hours = (now - today_start).total_seconds() / 3600

        for i in range(num_mentions):
            hours_ago = random.uniform(0, min(8, max_hours))  # Last 8 hours or less if early morning
            timestamp = now - timedelta(hours=hours_ago)

            mention = MockMention(
                timestamp=timestamp.isoformat(),
                channel=random.choice(workspace["channels"]),
                user=random.choice(MOCK_USERS),
                text=random.choice(MESSAGE_TEMPLATES).format(
                    mention="@you",
                    topic=random.choice(TOPICS)
                ),
                is_question=random.random() < 0.3,
                responded=hours_ago > 3,  # Older messages responded
                client_id=client_id,
                workspace=workspace["name"]  # Use workspace name
            )
            all_mentions.append(mention)

        # Generate stats
        stat = MockStats(
            client_id=client_id,
            unread_count=random.randint(0, num_mentions // 2),
            messages_last_hour=random.randint(0, num_mentions // 3),
            active_channels=workspace["channels"],
            timestamp=now.isoformat()
        )
        all_stats.append(stat)

    return {
        "mentions": all_mentions,
        "stats": all_stats,
        "scenario": "multi_job"
    }


# Quick access functions
def get_default_mock_data() -> Dict:
    """Get default mock data set - ALL DATA FROM TODAY (8am-8pm work hours)"""
    return {
        "mentions": generate_mock_mentions(num_mentions=50, hours_spread=12),
        "stats": generate_mock_stats(),
        "channel_activity": generate_mock_channel_activity(hours=13),  # 8am-8pm = 13 hours
        "scenario": "default"
    }


def get_mock_scenario(scenario: str = "default") -> Dict:
    """Get specific mock scenario - ALL DATA FROM TODAY"""
    scenarios = {
        "default": get_default_mock_data,
        "high_activity": generate_high_activity_scenario,
        "multi_job": generate_multi_job_scenario,
    }

    if scenario in scenarios:
        return scenarios[scenario]()
    else:
        return get_default_mock_data()


def is_data_from_today(timestamp_str: str) -> bool:
    """Check if a timestamp string is from today"""
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        today = datetime.now().date()
        return timestamp.date() == today
    except:
        return False
