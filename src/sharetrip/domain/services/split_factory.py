from sharetrip.domain.entities.expense import SplitType
from sharetrip.domain.services.split_strategy import (
    EqualSplitter,
    HybridSplitter,
    PercentageSplitter,
    SplitStrategy,
)

_STRATEGIES: dict[SplitType, SplitStrategy] = {
    SplitType.EQUAL: EqualSplitter(),
    SplitType.PERCENTAGE: PercentageSplitter(),
    SplitType.HYBRID: HybridSplitter(),
}


class SplitFactory:
    def get_strategy(self, split_type: SplitType) -> SplitStrategy:
        strategy = _STRATEGIES.get(split_type)
        if strategy is None:
            raise ValueError(f"Unknown split type: {split_type}")
        return strategy
