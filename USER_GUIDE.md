# User Guide

## Getting Your ESPN Credentials

The app needs four values to connect to your league. All are set in the `.env` file.

### League ID

1. Go to your league on [ESPN Fantasy Football](https://fantasy.espn.com/football/)
2. Look at the URL -- it contains `leagueId=XXXXX`
3. That number is your `ESPN_LEAGUE_ID`

### Season Year

Set `ESPN_YEAR` to the season you want to view (e.g. `2024` for the 2024-25 NFL season).

### Authentication Cookies (Private Leagues)

Private leagues require two cookies from ESPN: `espn_s2` and `SWID`.

1. Log in to [espn.com](https://www.espn.com/) in your browser
2. Open Developer Tools (F12 or Cmd+Option+I on Mac)
3. Go to **Application** (Chrome) or **Storage** (Firefox) > **Cookies** > `https://www.espn.com`
4. Find and copy these two cookies:
   - **`espn_s2`** -- a long encoded string. Paste this as `ESPN_S2` in your `.env`
   - **`SWID`** -- looks like `{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}` (include the curly braces). Paste this as `ESPN_SWID` in your `.env`

### Example `.env` File

```
ESPN_LEAGUE_ID=48153607
ESPN_YEAR=2024
ESPN_S2=AEBBzK0x7jQ3nJKl...long_string...
ESPN_SWID={1A2B3C4D-5E6F-7A8B-9C0D-1E2F3A4B5C6D}
```

## Using the App

### Starting the App

```bash
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

### League Standings

The home page shows all teams in your league ranked by standing. For each team you can see:

- **Rank** -- with gold/silver/bronze badges for the top 3
- **Team name and logo**
- **Record** -- wins, losses, and ties
- **Points for / against** -- total season scoring
- **Streak** -- current win (green) or loss (red) streak

Click any team name to view their roster.

### Team Roster

Each team's roster page is divided into three sections:

- **Starters** -- active lineup, sorted by position (QB, RB, WR, TE, FLEX, K, D/ST). Each player shows their lineup slot, position, NFL team, total points, and average points.
- **Bench** -- reserve players not in the active lineup
- **Injured Reserve** -- players on IR with their injury status

Players with injury designations (Questionable, Doubtful, Out) are shown with color-coded badges next to their name.
