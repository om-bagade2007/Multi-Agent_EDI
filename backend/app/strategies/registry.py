"""Named strategy constructors for API and experiment selection."""
from app.strategies.hungarian import HungarianStrategy
from app.strategies.nearest import NearestStrategy

STRATEGIES = {"nearest": NearestStrategy, "hungarian": HungarianStrategy}
