#!/usr/bin/env python3
"""
Generates a LeetCode-style stats card SVG using REAL, live GitHub data.

Data sources:
- GitHub GraphQL API  -> contributionsCollection (streaks, active days, total contributions)
- GitHub REST API     -> repo count, total stars, followers

Env vars required:
    GH_TOKEN            - a GitHub token with 'read:user' scope (repo scope not needed for public data)
    PROFILE_USERNAME    - the GitHub username to fetch stats for (defaults to "AsfarButt")

Output:
    assets/github-stats-card.svg
"""

import os
import sys
import datetime
import requests

USERNAME = os.environ.get("PROFILE_USERNAME", "AsfarButt")
TOKEN = os.environ.get("GH_TOKEN")
OUT_PATH = os.environ.get("OUT_PATH", "assets/github-stats-card.svg")

if not TOKEN:
    print("ERROR: GH_TOKEN env var is required.", file=sys.stderr)
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {TOKEN}"}

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, first: 100, privacy: PUBLIC) {
      totalCount
      nodes { stargazerCount }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""


def fetch_github_data(username: str) -> dict:
    resp = requests.post(
        "https://api.github.com/graphql",
        headers=HEADERS,
        json={"query": GRAPHQL_QUERY, "variables": {"login": username}},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "errors" in payload:
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")
    return payload["data"]["user"]


def compute_streaks(days: list[dict]) -> tuple[int, int, int]:
    """Returns (active_days, current_streak, max_streak)."""
    active_days = 0
    max_streak = 0
    running = 0
    current_streak = 0

    today = datetime.date.today()

    for day in days:
        count = day["contributionCount"]
        if count > 0:
            active_days += 1
            running += 1
            max_streak = max(max_streak, running)
        else:
            running = 0

    # current streak: walk backwards from the most recent day
    for day in reversed(days):
        d = datetime.date.fromisoformat(day["date"])
        if d > today:
            continue
        if day["contributionCount"] > 0:
            current_streak += 1
        else:
            if d == today:
                # today with 0 contributions doesn't break an ongoing streak yet
                continue
            break

    return active_days, current_streak, max_streak


def ring_color(pct: float) -> str:
    # teal -> yellow -> red gradient stops, like the LeetCode ring
    if pct >= 66:
        return "#2cbb5d"
    if pct >= 33:
        return "#ffc01e"
    return "#ef4743"


def render_svg(data: dict, username: str) -> str:
    followers = data["followers"]["totalCount"]
    repos_node = data["repositories"]
    repo_count = repos_node["totalCount"]
    total_stars = sum(r["stargazerCount"] for r in repos_node["nodes"])

    calendar = data["contributionsCollection"]["contributionCalendar"]
    total_contribs = calendar["totalContributions"]
    weeks = calendar["weeks"]

    all_days = [d for w in weeks for d in w["contributionDays"]]
    active_days, current_streak, max_streak = compute_streaks(all_days)

    pct_active = round((active_days / 365) * 100) if active_days else 0
    r = 54
    circumference = 2 * 3.14159265 * r
    dash = circumference * (pct_active / 100)
    ring_col = ring_color(pct_active)

    height = 262  # top panel row only, contribution calendar removed

    svg = f"""<svg width="1000" height="{height}" viewBox="0 0 1000 {height}" xmlns="http://www.w3.org/2000/svg" font-family="'Segoe UI', Helvetica, Arial, sans-serif">
  <style>
    .panel {{ fill: none; stroke: #30363d; stroke-width: 1; }}
    .title {{ fill: #9aa4b2; font-size: 13px; }}
    .label {{ fill: #9aa4b2; font-size: 12px; }}
    .stat-val {{ fill: currentColor; font-size: 20px; font-weight: 700; }}
    .big-num {{ fill: currentColor; font-size: 34px; font-weight: 700; }}
    .ring-pct {{ fill: currentColor; font-size: 22px; font-weight: 700; }}
    text {{ color: #ffffff; }}
  </style>

  <!-- Left panel: ring + stat boxes -->
  <rect class="panel" x="16" y="16" width="430" height="230" rx="4"/>
  <circle cx="120" cy="130" r="{r}" fill="none" stroke="#30363d" stroke-width="10"/>
  <circle cx="120" cy="130" r="{r}" fill="none" stroke="{ring_col}" stroke-width="10"
    stroke-dasharray="{dash:.1f} {circumference:.1f}" stroke-linecap="round"
    transform="rotate(-90 120 130)"/>
  <text x="120" y="124" text-anchor="middle" class="ring-pct">{pct_active}%</text>
  <text x="120" y="144" text-anchor="middle" class="label">active days</text>

  <rect x="230" y="46" width="190" height="52" rx="3" fill="#2cbb5d" fill-opacity="0.1" stroke="#2cbb5d" stroke-opacity="0.35"/>
  <text x="244" y="66" class="label" fill="#2cbb5d">Repos</text>
  <text x="244" y="88" class="stat-val">{repo_count}</text>

  <rect x="230" y="108" width="190" height="52" rx="3" fill="#ffc01e" fill-opacity="0.1" stroke="#ffc01e" stroke-opacity="0.35"/>
  <text x="244" y="128" class="label" fill="#ffc01e">Stars</text>
  <text x="244" y="150" class="stat-val">{total_stars}</text>

  <rect x="230" y="170" width="190" height="52" rx="3" fill="#ef4743" fill-opacity="0.1" stroke="#ef4743" stroke-opacity="0.35"/>
  <text x="244" y="190" class="label" fill="#ef4743">Followers</text>
  <text x="244" y="212" class="stat-val">{followers}</text>

  <!-- Right panel: contributions + streak -->
  <rect class="panel" x="458" y="16" width="526" height="230" rx="4"/>
  <text x="480" y="46" class="title">Contributions (past year)</text>
  <text x="480" y="86" class="big-num">{total_contribs}</text>

  <text x="480" y="130" class="title">Current Streak</text>
  <rect x="480" y="142" width="230" height="60" rx="3" fill="#2cbb5d" fill-opacity="0.1" stroke="#2cbb5d" stroke-opacity="0.4"/>
  <text x="500" y="178" class="stat-val" fill="#2cbb5d">{current_streak} day{"s" if current_streak != 1 else ""}</text>

  <text x="730" y="130" class="title">Longest Streak</text>
  <rect x="730" y="142" width="230" height="60" rx="3" fill="#ffc01e" fill-opacity="0.1" stroke="#ffc01e" stroke-opacity="0.4"/>
  <text x="750" y="178" class="stat-val" fill="#ffc01e">{max_streak} day{"s" if max_streak != 1 else ""}</text>
</svg>"""
    return svg


def main():
    data = fetch_github_data(USERNAME)
    svg = render_svg(data, USERNAME)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write(svg)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
