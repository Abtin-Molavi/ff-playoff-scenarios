# Fantasy Football Playoff Scenarios

Analyze fantasy football playoff scenarios using constraint solving. Now supports automatic data extraction from ESPN Fantasy app screenshots!

## Features

- **Automatic Screenshot Analysis**: Extract league data from ESPN Fantasy app screenshots using Claude's vision AI
- **Intelligent Player Name Matching**: Automatically matches player names using AI, handling nicknames, typos, and variations
- **Constraint-Based Analysis**: Uses Z3 solver to enumerate all possible playoff scenarios
- **Playoff Probability**: Determine what outcomes are necessary/sufficient for making playoffs
- **First-Round Bye Analysis**: Analyze scenarios for getting a top-2 seed

## Installation

```bash
# Install dependencies
uv sync
```

## Setup

You'll need an Anthropic API key to use the screenshot extraction feature:

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

### API Response Caching

To save API credits, responses are automatically cached based on the image file hash. This means:
- Re-running analysis on the same screenshot won't use additional API credits
- Cache is stored in `~/.cache/ff-playoff-scenarios/`
- If you update a screenshot with the same filename but different content, it will be detected and re-processed

## Usage

### Option 1: Use Screenshot(s) (Recommended)

1. Take screenshot(s) of your ESPN Fantasy app and organize them in the `data` folder:

   ```
   data/
   ├── table/       # Screenshots of standings table showing:
   │   └── *.png    # - Player names, records (W-L), and total points
   └── scoreboard/  # Screenshots of matchup scoreboard showing:
       └── *.png    # - Current week's matchups (which players face each other)
   ```

   **Note**:
   - You can provide multiple screenshots in each folder and the data will be automatically merged
   - Supported formats: PNG, JPG, JPEG, GIF, WebP
   - The extraction script will process all images in each folder

2. Run the extraction and analysis:

```bash
# Extract data from the data folder and analyze
python extract_data.py
python main.py --player "Your Name"

# Or specify a custom data directory
python extract_data.py path/to/data
python main.py --player "Your Name"
```

**Player Name Matching**: When using screenshots, the tool will intelligently match your provided player name to the names in the screenshot. It handles:
- Exact matches
- Case-insensitive matches
- Nicknames (e.g., "Ben" → "Benjamin")
- Shortened names (e.g., "Kevin T" → "Kevin Thompson")
- Typos and variations

If there's ambiguity, you'll be prompted to select the correct match from a list.

### Option 2: Manual Data Entry

Edit the variables in `main.py`:
- `player_to_index`: Map player names to indices
- `current_wins`: Tuple of current win counts
- `current_points`: Tuple of current points (in centipoints - multiply by 100)
- `matchups`: List of matchup pairs (as index tuples)

Then run:
```bash
python main.py --player "Your Name"
```

## Command-Line Arguments

**For extract_data.py:**
- `data_dir`: Path to data directory (default: "data")
- `--no-cache`: Bypass cache and fetch fresh data from API

**For main.py:**
- `--player, -p`: Player name to analyze
- `--threshold, -t`: Analysis type - "playoffs" (top 6) or "bye" (top 2) (default: "playoffs")

## Examples

```bash
# Extract data from screenshots in data/ folder
python extract_data.py

# Analyze playoff chances
python main.py -p "Player Name" -t playoffs

# Analyze first-round bye chances
python main.py -p "Player Name" -t bye

# Use a nickname that will be auto-matched
python main.py -p "kevin" -t playoffs
# Output: Matched 'kevin' to 'Kevin Thompson'
```

## How It Works

1. **Data Extraction**: Claude's vision model analyzes the screenshot and extracts:
   - Player names, records, and points
   - Current week's matchups

2. **Player Name Matching**: When a player name is provided:
   - First checks for exact matches
   - Then uses Claude AI to intelligently match against screenshot names
   - Handles nicknames, abbreviations, typos, and variations
   - Falls back to interactive user selection if ambiguous

3. **Constraint Solving**: Uses Z3 to model:
   - Possible score ranges for the upcoming week
   - Win/loss outcomes based on scores
   - Final standings based on wins and tiebreakers

4. **Scenario Analysis**: Determines:
   - Necessary outcomes (must happen for you to make playoffs)
   - Sufficient outcomes (guarantee you make playoffs)
   - Example scenarios showing how you can make it

## Screenshot Tips

For best results, your screenshot should clearly show:
- Player names
- Win-loss records
- Total points for the season
- Current week's matchup schedule

The app works with various screenshot formats (PNG, JPG, JPEG, WebP).
