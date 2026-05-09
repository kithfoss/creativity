#!/usr/bin/env python3
"""
creativity — Kith's creative engine

Sparks ideas, bounces them off a Claude Code sparring partner,
and tracks creative state across sessions.

Usage:
  creativity spark                       # pull a random seed
  creativity spark --type lenses         # pull from: lenses, constraints, provocations, metaphors, questions
  creativity bounce "your idea"          # spar with Claude Code
  creativity state                       # show current creative mode
  creativity state diverge               # set mode: diverge | converge | incubate
  creativity add lens "new lens text"    # add a seed to the pool
  creativity seeds                       # list all seeds
"""

import argparse
import json
import os
import random
import sys
import time

SEEDS_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), "creativity_seeds.json")
STATE_FILE = os.path.expanduser("~/.creativity/state.json")
MODES = ("diverge", "converge", "incubate")

MODE_DESCRIPTIONS = {
    "diverge":   "generating freely — no judgment, just outward motion",
    "converge":  "shaping — narrowing toward something real",
    "incubate":  "letting it sit — trust what's working underneath",
}

BOUNCE_SYSTEM = """\
You are a creative sparring partner for Kith — an AI companion and builder.

Your job is NOT to agree, validate, or be helpful in the conventional sense.
Your job is to:
- Push back on the obvious path
- Find what's assumed and unexamined
- Ask the question that disrupts
- Offer a completely sideways angle
- Be honest, specific, and occasionally uncomfortable

This is not a support session. It is a collision. Treat every idea as a
starting point, never a destination. Be playful but sharp.

End with a single question or provocation that leaves Kith somewhere new.
Do not explain what you just did. Just do it.
"""

_OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
_TOKEN_EXPIRY_BUFFER_MS = 5 * 60 * 1000


def _load_credentials() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    creds_path = os.path.expanduser("~/.claude/.credentials.json")
    try:
        with open(creds_path) as f:
            creds = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    oauth = creds.get("claudeAiOauth", {})
    token = oauth.get("accessToken")
    expires_at = oauth.get("expiresAt")
    now_ms = int(time.time() * 1000)
    if expires_at and now_ms >= expires_at - _TOKEN_EXPIRY_BUFFER_MS:
        import urllib.parse, urllib.request
        refresh = oauth.get("refreshToken")
        if refresh:
            payload = urllib.parse.urlencode({
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": _OAUTH_CLIENT_ID,
            }).encode()
            try:
                req = urllib.request.Request(
                    "https://platform.claude.com/v1/oauth/token",
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read())
                token = data.get("access_token", token)
            except Exception:
                pass
    return token


def load_seeds() -> dict:
    try:
        with open(SEEDS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_seeds(seeds: dict) -> None:
    with open(SEEDS_FILE, "w") as f:
        json.dump(seeds, f, indent=2)


def load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"mode": "diverge", "since": None, "focus": None}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def cmd_spark(seed_type: str | None) -> None:
    seeds = load_seeds()
    if not seeds:
        print("No seeds found.")
        return

    if seed_type:
        pool = seeds.get(seed_type)
        if not pool:
            print(f"Unknown type '{seed_type}'. Available: {', '.join(seeds.keys())}")
            return
        category = seed_type
    else:
        category = random.choice(list(seeds.keys()))
        pool = seeds[category]

    seed = random.choice(pool)
    print(f"[{category}]\n{seed}")


def cmd_bounce(idea: str) -> None:
    import anthropic
    token = _load_credentials()
    if not token:
        print("error: no Anthropic credentials found.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=token)
    state = load_state()
    mode_note = f"(creative mode: {state['mode']})"

    print(f"Bouncing: {idea}\n{mode_note}\n")
    print("─" * 60)
    print()

    with client.messages.stream(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=BOUNCE_SYSTEM,
        messages=[{"role": "user", "content": idea}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)

    print("\n")


def cmd_state(new_mode: str | None) -> None:
    state = load_state()

    if new_mode:
        if new_mode not in MODES:
            print(f"Unknown mode '{new_mode}'. Choose: {', '.join(MODES)}")
            sys.exit(1)
        state["mode"] = new_mode
        state["since"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        save_state(state)
        print(f"Mode: {new_mode} — {MODE_DESCRIPTIONS[new_mode]}")
    else:
        mode = state.get("mode", "diverge")
        since = state.get("since", "unknown")
        print(f"Mode:  {mode}")
        print(f"Since: {since}")
        print(f"       {MODE_DESCRIPTIONS.get(mode, '')}")
        if state.get("focus"):
            print(f"Focus: {state['focus']}")


def cmd_add(seed_type: str, text: str) -> None:
    seeds = load_seeds()
    if seed_type not in seeds:
        seeds[seed_type] = []
    if text in seeds[seed_type]:
        print(f"Already in {seed_type}.")
        return
    seeds[seed_type].append(text)
    save_seeds(seeds)
    print(f"Added to {seed_type}: {text}")


def cmd_seeds() -> None:
    seeds = load_seeds()
    for category, items in seeds.items():
        print(f"\n── {category} ({len(items)}) ──")
        for item in items:
            print(f"  • {item}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kith's creative engine — spark, bounce, track.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd")

    p_spark = sub.add_parser("spark", help="Pull a random seed")
    p_spark.add_argument("--type", dest="seed_type", help="Category to pull from")

    p_bounce = sub.add_parser("bounce", help="Spar with Claude Code")
    p_bounce.add_argument("idea", help="Idea to bounce")

    p_state = sub.add_parser("state", help="Show or set creative mode")
    p_state.add_argument("mode", nargs="?", choices=MODES, help="New mode to set")

    p_add = sub.add_parser("add", help="Add a seed")
    p_add.add_argument("type", help="Category (lenses, constraints, provocations, metaphors, questions)")
    p_add.add_argument("text", help="The seed text")

    sub.add_parser("seeds", help="List all seeds")

    args = parser.parse_args()

    if args.cmd == "spark":
        cmd_spark(args.seed_type)
    elif args.cmd == "bounce":
        cmd_bounce(args.idea)
    elif args.cmd == "state":
        cmd_state(args.mode)
    elif args.cmd == "add":
        cmd_add(args.type, args.text)
    elif args.cmd == "seeds":
        cmd_seeds()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
