# Player Performance Modeling Research

## Overview

This document surveys statistical and machine learning approaches for predicting
fantasy football player performance. The goal is to identify methods that can
power start/sit decisions, draft rankings, and waiver wire recommendations within
our analytics system.

## Statistical Approaches

### Linear Regression

Linear regression is the recommended starting point. It is interpretable,
fast to train, and provides a useful baseline against which more complex models
can be compared. A simple model might predict weekly fantasy points from
features such as opponent defensive rank, recent scoring average, and home/away
status. Ridge and Lasso variants help manage multicollinearity among correlated
football statistics (e.g., targets and receptions).

**Pros:** Easy to interpret coefficients, fast iteration, minimal tuning.
**Cons:** Assumes linear relationships, struggles with interaction effects.

### Random Forests

Random forests handle non-linear relationships and feature interactions without
explicit specification. They are robust to outliers and require less feature
engineering than linear models. Feature importance scores are a valuable
byproduct, revealing which inputs matter most for each position.

**Pros:** Handles non-linearity, built-in feature importance, resistant to overfitting.
**Cons:** Less interpretable than linear models, slower to train on large datasets.

### Gradient Boosting (XGBoost / LightGBM)

Gradient boosted trees typically deliver the best predictive accuracy for
tabular data. XGBoost and LightGBM are widely used in sports analytics and
Kaggle competitions. They require careful hyperparameter tuning (learning rate,
max depth, number of estimators) but reward the effort with strong results.

**Pros:** State-of-the-art accuracy on tabular data, handles missing values natively.
**Cons:** Risk of overfitting without proper cross-validation, harder to interpret.

### Bayesian Methods

Bayesian approaches are especially useful early in the NFL season when sample
sizes are small. Prior distributions can encode preseason projections, which are
then updated as weekly data arrives. Bayesian hierarchical models can share
information across players at the same position, improving estimates for
players with limited data.

**Pros:** Natural uncertainty quantification, principled handling of small samples.
**Cons:** Computationally expensive, requires careful prior specification.

### Recommended Progression

1. Start with ridge regression as a baseline.
2. Add a random forest model and compare error metrics.
3. Introduce gradient boosting for production predictions.
4. Explore Bayesian methods for early-season and uncertainty use cases.

## Key Prediction Features

### Usage Metrics

- **Snap count percentage:** The strongest single predictor of opportunity.
- **Target share:** Percentage of team pass attempts directed at a player.
- **Air yards share:** Measures the depth and volume of a receiver's targets.
- **Red zone touches/targets:** High-value scoring opportunities.
- **Rush attempts inside the 5:** Touchdown-dependent but highly predictive for RBs.
- **Routes run:** For receivers, a more granular measure than snap counts.

### Matchup Features

- **Opponent defensive rank vs. position:** Points allowed to QBs, RBs, WRs, TEs.
- **Implied team total (Vegas):** Strong proxy for overall offensive output.
- **Game spread:** Influences run/pass ratio and garbage time opportunity.
- **Opponent pass rush pressure rate:** Impacts QB and receiver production.

### Situational Features

- **Home/away:** Consistent 1-2 point advantage for home players.
- **Weather (outdoor games):** Wind speed above 15 mph suppresses passing.
- **Injury report status:** Players listed as questionable average fewer snaps.
- **Bye week timing:** Post-bye performance tends to regress slightly.
- **Short week (Thursday games):** Associated with lower scoring overall.

### Historical Features

- **Rolling averages (3-week, 5-week):** Capture recent form.
- **Season-long averages:** Capture talent level.
- **Year-over-year trends:** Aging curves, role changes.

## Fantasy-Specific Metrics

### VORP (Value Over Replacement Player)

VORP measures how many more points a player scores than a freely available
replacement at the same position. It is the foundation of value-based drafting.

```
VORP = Player Projected Points - Replacement Level Points
```

Replacement level is typically defined as the points scored by the last starter
at a position in a given league format. For a 12-team, 1-QB league:

| Position | Replacement Level (starter #) |
|----------|-------------------------------|
| QB       | QB13                          |
| RB       | RB25                          |
| WR       | WR25                          |
| TE       | TE13                          |

### Positional Scarcity

Positional scarcity measures how quickly value drops off at each position.
Running back and tight end typically show the steepest drop-offs, making
early-round RBs and elite TEs more valuable than their raw point totals suggest.
This metric should adjust dynamically based on league size and roster settings.

### Consistency Score

A player's floor/ceiling spread matters for weekly decisions. Consistency can
be measured as the coefficient of variation (standard deviation divided by mean)
of weekly fantasy points. Lower CV indicates a safer floor.

### Expected Fantasy Points (xFP)

Built from opportunity data (targets, rush attempts, red zone usage) rather than
actual results. xFP strips out touchdown variance and big-play luck, providing
a more stable measure of underlying production.

## Start/Sit Decision Framework

### Projection-Based Approach

The simplest method: start whichever player has the higher point projection.
This works well when the gap between players is large (more than 3-4 points).

### Floor/Ceiling Analysis

When projections are close, consider the game context:

- **Need a safe floor (favored to win matchup):** Prefer high-volume players
  with consistent usage patterns and low weekly variance.
- **Need upside (underdog in matchup):** Prefer boom/bust players with
  touchdown dependency or big-play ability.

### Composite Decision Score

```
Decision Score = (0.6 * Projection) + (0.2 * Floor) + (0.2 * Matchup Rating)
```

Weights can be adjusted based on game context. The matchup rating normalizes
opponent defensive performance on a 1-10 scale.

## Draft Strategy Optimization

### Value-Based Drafting (VBD)

VBD ranks players by VORP rather than raw projected points. This naturally
accounts for positional scarcity and identifies the best value at each pick.
The system should compute VBD rankings dynamically, adjusting as players are
drafted and replacement levels shift.

### ADP Analysis

Average Draft Position (ADP) from platforms like ESPN, Yahoo, and Sleeper
reveals where the market expects players to go. Comparing our VORP rankings
to ADP identifies value picks (players with high VORP going later than expected)
and overvalued players (low VORP relative to ADP).

### Draft Pick Value Curve

Each draft slot has an expected value based on historical hit rates. Early-round
picks carry less risk but less surplus value. Middle-round picks offer the
highest potential surplus value when the model identifies undervalued players.

### Auction Draft Considerations

For auction formats, dollar values can be derived from VORP using a linear
scaling that maps total VORP to total league budget minus minimum bids.

## Implementation Notes

- All models should be trained on a minimum of 3 seasons of data.
- Use walk-forward cross-validation that respects the time-series nature of NFL data.
- Evaluate models using MAE (mean absolute error) for point projections.
- Position-specific models tend to outperform single universal models.
- Retrain weekly during the season as new data arrives.
