"""
Extract fantasy football data from ESPN app screenshots using vision AI.
"""
import base64
import json
import hashlib
from pathlib import Path
from typing import Dict, Tuple, List
import anthropic
import os


def get_cache_dir() -> Path:
    """Get or create the cache directory."""
    cache_dir = Path.home() / ".cache" / "ff-playoff-scenarios"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_image_hash(image_path: str) -> str:
    """Calculate SHA256 hash of image file."""
    with open(image_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def get_cached_response(image_path: str) -> Dict | None:
    """Check if cached response exists for this image."""
    cache_dir = get_cache_dir()
    image_hash = get_image_hash(image_path)
    cache_file = cache_dir / f"{image_hash}.json"

    if cache_file.exists():
        with open(cache_file, "r") as f:
            return json.load(f)
    return None


def save_cached_response(image_path: str, data: Dict):
    """Save API response to cache."""
    cache_dir = get_cache_dir()
    image_hash = get_image_hash(image_path)
    cache_file = cache_dir / f"{image_hash}.json"

    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2)


def encode_image(image_path: str) -> str:
    """Encode image to base64 string."""
    with open(image_path, "rb") as image_file:
        return base64.standard_b64encode(image_file.read()).decode("utf-8")


def get_image_media_type(image_path: Path) -> str:
    """Determine the media type of an image file."""
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # Check magic bytes
    if image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return "image/png"
    elif image_bytes.startswith(b'\xff\xd8\xff'):
        return "image/jpeg"
    elif image_bytes.startswith(b'GIF87a') or image_bytes.startswith(b'GIF89a'):
        return "image/gif"
    elif image_bytes.startswith(b'RIFF') and image_bytes[8:12] == b'WEBP':
        return "image/webp"

    # Fallback to extension-based detection
    suffix = image_path.suffix.lower()
    media_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp"
    }
    return media_type_map.get(suffix, "image/png")


def extract_table_data(image_paths: List[str], api_key: str = None, no_cache: bool = False) -> Dict:
    """
    Extract team standings from table screenshots.

    Args:
        image_paths: List of paths to table screenshot images
        api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
        no_cache: If True, bypass cache and fetch fresh data

    Returns:
        Dictionary with player standings:
        {
            "players": [
                {"name": "Player Name", "wins": X, "losses": Y, "points": Z},
                ...
            ]
        }
    """
    if api_key is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("API key required. Set ANTHROPIC_API_KEY environment variable or pass api_key parameter.")

    client = anthropic.Anthropic(api_key=api_key)

    all_players = []

    for image_path in image_paths:
        print(f"Processing table image: {image_path}")

        # Check cache first
        if not no_cache:
            cached_data = get_cached_response(image_path)
            if cached_data is not None:
                print(f"  Using cached data")
                all_players.extend(cached_data.get("players", []))
                continue

        print(f"  Fetching data from API...")

        # Read and encode image
        img_path = Path(image_path)
        if not img_path.exists():
            raise FileNotFoundError(f"Image not found: {img_path}")

        with open(img_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        media_type = get_image_media_type(img_path)

        prompt = """Please extract the following information from this ESPN Fantasy Football standings table:

For each team in the league, extract:
- Team owner name (the name of the player, not the team name)
- Current record (wins-losses)
- Total points scored this season (in centipoints - multiply by 100 if showing as decimal)

Return the data in this exact JSON format:
{
    "players": [
        {"name": "Owner Name", "wins": 10, "losses": 3, "points": 146426},
        ...
    ]
}

IMPORTANT:
- Use the OWNER name, not the team name
- Points should be in centipoints (multiply decimal points by 100)
- Include ALL players visible in the table
- Player names should match exactly as they appear
- Return ONLY valid JSON, no other text"""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ],
                }
            ],
        )

        # Extract JSON from response
        response_text = message.content[0].text
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            raise ValueError(f"No JSON found in response: {response_text}")

        json_str = response_text[json_start:json_end]
        data = json.loads(json_str)

        # Save to cache
        save_cached_response(str(img_path), data)

        all_players.extend(data.get("players", []))

    # Deduplicate players across multiple table screenshots
    print("Deduplicating players from table images...")
    deduplicated = deduplicate_players({"players": all_players}, client)

    return deduplicated


def extract_scoreboard_data(image_paths: List[str], player_names: List[str], api_key: str = None, no_cache: bool = False) -> Dict:
    """
    Extract matchups from scoreboard screenshots.

    Args:
        image_paths: List of paths to scoreboard screenshot images
        player_names: List of canonical player names to help with matching
        api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
        no_cache: If True, bypass cache and fetch fresh data

    Returns:
        Dictionary with matchups:
        {
            "matchups": [
                ["Player1", "Player2"],
                ["Player3", "Player4"],
                ...
            ]
        }
    """
    if api_key is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("API key required. Set ANTHROPIC_API_KEY environment variable or pass api_key parameter.")

    client = anthropic.Anthropic(api_key=api_key)

    all_matchups = []

    for image_path in image_paths:
        print(f"Processing scoreboard image: {image_path}")

        # Check cache first
        if not no_cache:
            cached_data = get_cached_response(image_path)
            if cached_data is not None:
                print(f"  Using cached data")
                all_matchups.extend(cached_data.get("matchups", []))
                continue

        print(f"  Fetching data from API...")

        # Read and encode image
        img_path = Path(image_path)
        if not img_path.exists():
            raise FileNotFoundError(f"Image not found: {img_path}")

        with open(img_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        media_type = get_image_media_type(img_path)

        # Include player names in prompt to help with matching
        player_list = json.dumps(player_names, indent=2)

        prompt = f"""Please extract the matchups from this ESPN Fantasy Football scoreboard screenshot.

The league has the following players:
{player_list}

For each matchup visible in the screenshot, identify which two players are facing each other.
Use the owner names (not team names) and match them to the player list above.

Return the data in this exact JSON format:
{{
    "matchups": [
        ["Player1", "Player2"],
        ["Player3", "Player4"],
        ...
    ]
}}

IMPORTANT:
- Use owner names from the provided list above
- Each matchup should be a pair of two players
- Include ALL matchups visible in the image
- Match player names as closely as possible to the provided list
- Return ONLY valid JSON, no other text"""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ],
                }
            ],
        )

        # Extract JSON from response
        response_text = message.content[0].text
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            raise ValueError(f"No JSON found in response: {response_text}")

        json_str = response_text[json_start:json_end]
        data = json.loads(json_str)

        # Save to cache
        save_cached_response(str(img_path), data)

        all_matchups.extend(data.get("matchups", []))

    # Deduplicate matchups
    unique_matchups = []
    seen = set()
    for matchup in all_matchups:
        # Sort to handle [A, B] vs [B, A]
        key = tuple(sorted(matchup))
        if key not in seen:
            seen.add(key)
            unique_matchups.append(matchup)

    return {"matchups": unique_matchups}


def normalize_matchup_names(matchups: List[List[str]], canonical_names: List[str], client: anthropic.Anthropic) -> List[List[str]]:
    """
    Use Claude to normalize matchup names to match canonical player names.
    Handles cases where scoreboard shows initials (e.g., "J. Doe") but
    canonical list has full names (e.g., "John Doe").

    Args:
        matchups: List of matchup pairs with potentially abbreviated names
        canonical_names: List of full canonical player names
        client: Anthropic client for API calls

    Returns:
        List of matchup pairs with normalized names matching canonical_names
    """
    if not matchups:
        return []

    matchups_json = json.dumps(matchups, indent=2)
    canonical_json = json.dumps(canonical_names, indent=2)

    normalize_prompt = f"""Given these fantasy football matchups with potentially abbreviated names:
{matchups_json}

And this list of canonical full player names:
{canonical_json}

Please normalize all names in the matchups to match the canonical names exactly. Handle cases like:
- "J. Doe" should match "John Doe"
- "A. Smith" should match "Alice Smith"
- etc.

Return ONLY a valid JSON object in this exact format:
{{
    "matchups": [
        ["Full Name 1", "Full Name 2"],
        ["Full Name 3", "Full Name 4"],
        ...
    ]
}}

IMPORTANT:
- Use exact names from the canonical list
- Match abbreviated names (initials) to their full versions
- Return ONLY the JSON, no other text"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": normalize_prompt
            }
        ],
    )

    response_text = message.content[0].text

    # Try to find JSON in the response
    json_start = response_text.find('{')
    json_end = response_text.rfind('}') + 1

    if json_start == -1 or json_end == 0:
        raise ValueError(f"No JSON found in normalization response: {response_text}")

    json_str = response_text[json_start:json_end]
    normalized_data = json.loads(json_str)

    return normalized_data.get("matchups", [])


def extract_data_from_data_folder(data_dir: str = "data", api_key: str = None, no_cache: bool = False) -> Dict:
    """
    Extract fantasy football data from images in the data folder.

    The data folder should contain:
    - data/table/: Screenshots of the standings table
    - data/scoreboard/: Screenshots of the matchup scoreboards

    Args:
        data_dir: Path to data directory
        api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
        no_cache: If True, bypass cache and fetch fresh data

    Returns:
        Dictionary with extracted data:
        {
            "player_to_index": dict mapping player names to indices,
            "current_wins": tuple of wins for each player,
            "current_points": tuple of points for each player,
            "matchups": list of tuples with matchup pairs
        }
    """
    data_path = Path(data_dir)
    table_dir = data_path / "table"
    scoreboard_dir = data_path / "scoreboard"

    if not table_dir.exists():
        raise FileNotFoundError(f"Table directory not found: {table_dir}")
    if not scoreboard_dir.exists():
        raise FileNotFoundError(f"Scoreboard directory not found: {scoreboard_dir}")

    # Find all images in each directory
    image_extensions = [".png", ".jpg", ".jpeg", ".gif", ".webp"]
    image_extensions += [ext.upper() for ext in image_extensions]
    table_images = []
    for ext in image_extensions:
        table_images.extend(table_dir.glob(f"*{ext}"))
    table_images.sort()

    scoreboard_images = []
    for ext in image_extensions:
        scoreboard_images.extend(scoreboard_dir.glob(f"*{ext}"))
    scoreboard_images.sort()

    if not table_images:
        raise FileNotFoundError(f"No images found in {table_dir}")
    if not scoreboard_images:
        raise FileNotFoundError(f"No images found in {scoreboard_dir}")

    print(f"Found {len(table_images)} table image(s)")
    print(f"Found {len(scoreboard_images)} scoreboard image(s)")
    print()

    # Step 1: Extract table data (player standings)
    print("=" * 60)
    print("STEP 1: Extracting player standings from table images")
    print("=" * 60)
    table_data = extract_table_data([str(p) for p in table_images], api_key, no_cache)

    player_names = [p["name"] for p in table_data["players"]]
    print(f"\nFound {len(player_names)} players: {', '.join(player_names)}")
    print()

    # Step 2: Extract scoreboard data (matchups)
    print("=" * 60)
    print("STEP 2: Extracting matchups from scoreboard images")
    print("=" * 60)
    scoreboard_data = extract_scoreboard_data([str(p) for p in scoreboard_images], player_names, api_key, no_cache)

    print(f"\nFound {len(scoreboard_data['matchups'])} matchup(s):", scoreboard_data['matchups'])
    print()

    # Convert to main.py format
    player_to_index = {player["name"]: i for i, player in enumerate(table_data["players"])}
    current_wins = tuple(player["wins"] for player in table_data["players"])
    current_points = tuple(player["points"] for player in table_data["players"])

    # Normalize matchup names using AI to handle initials/abbreviations
    if api_key is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    normalized_matchups = normalize_matchup_names(scoreboard_data["matchups"], player_names, client)

    # Convert matchup names to indices
    matchups = []
    for matchup in normalized_matchups:
        if len(matchup) != 2:
            continue
        try:
            p1_idx = player_to_index[matchup[0]]
            p2_idx = player_to_index[matchup[1]]
            matchups.append((p1_idx, p2_idx))
        except KeyError as e:
            print(f"Warning: Could not find player in matchup: {e}")
            print(f"  Available players: {list(player_to_index.keys())}")
            continue

    return {
        "player_to_index": player_to_index,
        "current_wins": current_wins,
        "current_points": current_points,
        "matchups": matchups
    }


def deduplicate_players(data: Dict, client: anthropic.Anthropic) -> Dict:
    """
    Use Claude to intelligently deduplicate player names that might be abbreviated.

    Args:
        data: Dictionary with "players" list containing player data
        client: Anthropic client for API calls

    Returns:
        Dictionary with deduplicated players
    """
    players_json = json.dumps(data["players"], indent=2)

    dedup_prompt = f"""The following list of fantasy football players may contain duplicates where the same person appears with both full names and abbreviated names (e.g., "John Doe" and "J. Doe").

Players:
{players_json}

Please deduplicate this list by:
1. Identifying which entries represent the same person (full name vs abbreviated)
2. For each duplicate set, keep ONLY the full name version and merge their stats (keeping the highest wins and points values)
3. Return the deduplicated list

Return ONLY a valid JSON object in this exact format:
{{
    "players": [
        {{"name": "Full Name", "wins": X, "losses": Y, "points": Z}},
        ...
    ]
}}

Important:
- Use full names (e.g., "John Doe" not "J. Doe")
- If you see both versions, merge them and keep the better stats
- Return ONLY the JSON, no other text"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": dedup_prompt
            }
        ],
    )

    response_text = message.content[0].text

    # Try to find JSON in the response
    json_start = response_text.find('{')
    json_end = response_text.rfind('}') + 1

    if json_start == -1 or json_end == 0:
        raise ValueError(f"No JSON found in deduplication response: {response_text}")

    json_str = response_text[json_start:json_end]
    deduplicated_data = json.loads(json_str)

    return deduplicated_data


def match_player_name(input_name: str, canonical_names: List[str], api_key: str = None) -> str:
    """
    Use Claude to match a user-provided player name to a canonical name.
    Handles abbreviations, typos, and case differences.

    Args:
        input_name: The name provided by the user
        canonical_names: List of valid player names
        api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)

    Returns:
        The matched canonical name

    Raises:
        ValueError: If no match can be found
    """
    if api_key is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("API key required. Set ANTHROPIC_API_KEY environment variable or pass api_key parameter.")

    client = anthropic.Anthropic(api_key=api_key)

    canonical_json = json.dumps(canonical_names, indent=2)

    match_prompt = f"""Given this user input name: "{input_name}"

And this list of valid player names:
{canonical_json}

Please match the user input to one of the valid player names. Handle:
- Case differences (e.g., "john" matches "John Doe")
- Partial names (e.g., "John" matches "John Doe")
- First or last name only (e.g., "Doe" matches "John Doe")
- Minor typos

Return ONLY a valid JSON object in this exact format:
{{
    "matched_name": "Exact Name From List",
    "confidence": "high|medium|low"
}}

If you cannot find a reasonable match, use "matched_name": null.
Return ONLY the JSON, no other text."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": match_prompt
            }
        ],
    )

    response_text = message.content[0].text

    # Try to find JSON in the response
    json_start = response_text.find('{')
    json_end = response_text.rfind('}') + 1

    if json_start == -1 or json_end == 0:
        raise ValueError(f"No JSON found in match response: {response_text}")

    json_str = response_text[json_start:json_end]
    match_data = json.loads(json_str)

    matched_name = match_data.get("matched_name")
    if matched_name is None:
        raise ValueError(f"Could not match '{input_name}' to any player name")

    return matched_name


def save_extracted_data(data: Dict, output_path: str = "extracted_data.json"):
    """Save extracted data to JSON file for inspection."""
    with open(output_path, "w") as f:
        # Convert tuples to lists for JSON serialization
        json_data = {
            "player_to_index": data["player_to_index"],
            "current_wins": list(data["current_wins"]),
            "current_points": list(data["current_points"]),
            "matchups": data["matchups"]
        }
        json.dump(json_data, f, indent=2)
    print(f"Extracted data saved to {output_path}")


if __name__ == "__main__":
    import sys

    # Default to using the data folder
    data_dir = "data"
    if len(sys.argv) > 1:
        data_dir = sys.argv[1]

    print(f"Extracting data from {data_dir}/")
    data = extract_data_from_data_folder(data_dir)

    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"\nPlayers: {len(data['player_to_index'])}")
    for name, idx in data['player_to_index'].items():
        wins = data['current_wins'][idx]
        points = data['current_points'][idx]
        print(f"  {name}: {wins} wins, {points/100:.2f} points")

    print(f"\nMatchups: {len(data['matchups'])}")
    index_to_player = {v: k for k, v in data['player_to_index'].items()}
    for p1, p2 in data['matchups']:
        print(f"  {index_to_player[p1]} vs {index_to_player[p2]}")

    save_extracted_data(data)
