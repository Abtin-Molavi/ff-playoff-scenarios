# FF Playoff Scenarios

A script that uses the Z3 SMT solver to analyze fantasy football playoff scenarios. Given a player and a goal (making the playoffs or getting a first-round bye), it determines:

- **All possible scenarios** where that player achieves the goal
- **Necessary outcomes** — matchup results that must happen for the player to have any shot
- **Sufficient conditions** — matchup result combinations that guarantee the goal regardless of scores
- **An example scenario** with a full final standings breakdown

## How it works

The script encodes the league standings rules (wins, then total points as tiebreaker) as Z3 constraints and uses the solver to enumerate valid end-of-week standings. It then analyzes those scenarios to extract necessary and sufficient matchup outcomes.

## Setup

```bash
uv sync
```

## ESPN credentials

The script fetches live data from your ESPN private league. You'll need two cookies from your browser session:

1. Go to [espn.com](https://espn.com) and log in
2. Open DevTools → Application → Cookies
3. Copy the values for `espn_s2` and `SWID`

These are stable for a full season. Set them as environment variables:

```bash
export ESPN_S2="your_espn_s2_value"
export ESPN_SWID="{your-swid-value}"
```

## Usage

```bash
python main.py --league-id <id> --year <year> --week <week> <threshold>
```

- `--league-id` — your ESPN league ID (found in the URL on the ESPN fantasy page)
- `--year` — the season year (e.g. `2024`)
- `--week` — the week number you want to analyze
- `threshold` — either `playoffs` (top 6) or `bye` (top 2)

Credentials can also be passed directly instead of using env vars:

```bash
python main.py --league-id 12345 --year 2024 --week 14 --espn-s2 "..." --swid "{...}" playoffs
```

After fetching league data, the script will print the available player names and prompt you to enter one.

## Example

```
$ python main.py --league-id 12345 --year 2024 --week 14 playoffs

Fetching league data from ESPN...
Loaded 10 teams: Abtin Molavi, Ben Smith, ...
Enter player name to analyze: Abtin Rasoulian

Analyzing scenarios for Abtin to make the playoffs...
42 scenarios found.
If these outcomes occur, then Abtin is guaranteed to make the playoffs...
 Case 1:
   Abtin wins vs Kevin P AND
   Sam loses vs Ben
...
```
