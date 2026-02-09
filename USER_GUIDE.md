# User Guide

## Getting Your ESPN Credentials

When adding a league in the app, you need four values from ESPN. Here's how to find them.

### League ID

1. Go to your league on [ESPN Fantasy Football](https://fantasy.espn.com/football/)
2. Look at the URL -- it contains `leagueId=XXXXX`
3. That number is your League ID

### Season Year

The season year for the data you want to view (e.g. `2024` for the 2024-25 NFL season).

### Authentication Cookies (Private Leagues)

Private leagues require two cookies from ESPN: `espn_s2` and `SWID`.

1. Log in to [espn.com](https://www.espn.com/) in your browser
2. Open Developer Tools (F12 or Cmd+Option+I on Mac)
3. Go to **Application** (Chrome) or **Storage** (Firefox) > **Cookies** > `https://www.espn.com`
4. Find and copy these two cookies:
   - **`espn_s2`** -- a long encoded string
   - **`SWID`** -- looks like `{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}` (include the curly braces)

## Using the App

### Starting the App

```bash
python app.py
```

Open `http://127.0.0.1:8000` in your browser.

### Account & Leagues

1. **Register** an account at `/register` with a username and password.
2. **Log in** at `/login`.
3. **Add a league** from the Leagues page -- enter your league name and ESPN credentials (League ID, Season Year, espn_s2, SWID). The app validates the credentials by connecting to ESPN before saving.
4. You can add multiple leagues and switch between them from the Leagues page.

### League Standings

From a league, click **Standings** to see all teams ranked by standing. For each team you can see:

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

Players whose names match the NFL stats database are linked to their individual player detail page.

## Analytics

Analytics features use NFL player stats from [nfl_data_py](https://github.com/nflverse/nfl_data_py) stored in MongoDB. The data must be loaded before analytics pages will show results.

### Populating Analytics Data

1. **Initialize the database** (creates collections and indexes, only needed once):

   ```bash
   python scripts/init_db.py
   ```

2. **Load player stats** for the season(s) you want to analyze:

   ```bash
   python scripts/load_stats.py --years 2024
   ```

   You can load multiple seasons at once:

   ```bash
   python scripts/load_stats.py --years 2022 2023 2024
   ```

   This downloads seasonal and weekly stats from nfl_data_py and upserts them into the `seasonal_stats` and `weekly_stats` MongoDB collections. Running it again for the same season updates existing records (safe to re-run during the season for updated stats).

3. **Verify the data loaded** -- navigate to any league's Analytics page. If data is missing, the page will show a message with instructions.

### League Analytics Page

From any league, click **Analytics** to see the top 10 players at each position (QB, RB, WR, TE) for that league's season, ranked by PPR fantasy points. Each player shows total points, average per game, and games played. Click a player name to view their detail page.

### Player Detail Page

Click any player name in the analytics rankings or on a team roster to see their individual page. This includes:

- **Season Summary** -- total points, average per game, games played, positional rank (e.g. QB3), floor, ceiling, and consistency (standard deviation)
- **Recent Form** -- last 3 weeks average compared to season average, with a trending up/down/steady indicator
- **Weekly Scoring Trend** -- a week-by-week table showing opponent, points scored, and a visual bar comparing each week to the season average

### Team Analytics Page

From a team's roster page, click **Team Analytics** to see a detailed breakdown of the full roster:

- **Suggestions** -- actionable recommendations such as "Consider starting Player X over Player Y" when a bench player has outperformed a starter over the last 3 weeks, or alerts when a starter is trending down
- **Roster Breakdown** -- every player (starters and bench) with their season points, average per game, last 3 weeks average, trend direction (up/down/steady arrow), and positional rank

The roster analysis cross-references ESPN roster data with the NFL stats database to provide insights. Players not found in the stats database will show ESPN-reported stats only (no trend or positional rank).
