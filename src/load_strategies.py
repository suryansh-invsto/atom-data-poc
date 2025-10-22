"""Strategy generator for load testing with 30-50 instruments."""

import random
from typing import List, Dict
from .strategies import BaseStrategy


# 500 S&P 500 stocks (full index)
TEST_INSTRUMENTS = [
    # Top 50
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "BRK.B", "JPM", "V",
    "UNH", "XOM", "LLY", "MA", "JNJ", "PG", "HD", "CVX", "MRK", "ABBV",
    "KO", "PEP", "AVGO", "COST", "WMT", "BAC", "CRM", "NFLX", "AMD", "ORCL",
    "TMO", "ACN", "CSCO", "ADBE", "ABT", "DIS", "WFC", "MCD", "VZ", "INTC",
    "INTU", "AMGN", "IBM", "GE", "CAT", "BA", "GS", "AXP", "NOW", "QCOM",
    # 51-100
    "SPGI", "C", "DHR", "TXN", "RTX", "AMAT", "PM", "LOW", "BMY", "MS",
    "SCHW", "UNP", "HON", "BLK", "LMT", "NEE", "BKNG", "ELV", "SYK", "PLD",
    "DE", "T", "GILD", "CB", "MDT", "AMT", "MMC", "VRTX", "SBUX", "REGN",
    "ADI", "CI", "MO", "SO", "ZTS", "ISRG", "PGR", "LRCX", "BDX", "TJX",
    "FI", "CME", "DUK", "PYPL", "SLB", "GE", "NOC", "USB", "ETN", "BSX",
    # 101-150
    "APD", "MMM", "NSC", "EQIX", "EOG", "ICE", "CSX", "AON", "WM", "CL",
    "ITW", "MCK", "HCA", "PNC", "EMR", "APH", "GM", "MU", "F", "TGT",
    "KLAC", "SHW", "PSA", "ADP", "MSI", "GD", "TT", "MAR", "SNPS", "HUM",
    "FCX", "NXPI", "CDNS", "ORLY", "ROP", "AJG", "ADSK", "MNST", "MCO", "AIG",
    "COF", "AZO", "CCI", "AFL", "CMG", "TDG", "KMB", "CARR", "D", "FDX",
    # 151-200
    "TEL", "DHI", "TRV", "WELL", "CPRT", "MPC", "CTAS", "JCI", "HLT", "AMP",
    "PSX", "LHX", "PAYX", "SRE", "FICO", "O", "ALL", "NEM", "IQV", "AME",
    "LEN", "KMI", "A", "VRSK", "PCG", "CMI", "DLR", "FAST", "PRU", "GWW",
    "KR", "YUM", "CTVA", "EXC", "KHC", "EW", "PH", "DD", "IDXX", "BK",
    "EXR", "GLW", "PWR", "SPG", "RSG", "ODFL", "ED", "WMB", "XEL", "VLO",
    # 201-250
    "RMD", "ROK", "DOV", "TROW", "HIG", "HWM", "EFX", "PPG", "VICI", "IT",
    "CBRE", "IR", "KVUE", "AVB", "MLM", "VMC", "AXON", "DAL", "MPWR", "MTD",
    "WEC", "WAB", "URI", "GPN", "ACGL", "ANSS", "ROST", "KEYS", "MTB", "HAL",
    "EBAY", "XYL", "WTW", "HPQ", "FTV", "ETR", "CHD", "BAX", "DOW", "BR",
    "GEHC", "TTWO", "STZ", "AWK", "FITB", "DTE", "CDW", "EIX", "IFF", "TSCO",
    # 251-300
    "LYB", "AEE", "TYL", "DFS", "ES", "HBAN", "CAH", "VTR", "SYY", "APTV",
    "GRMN", "ZBH", "SBAC", "NVR", "TDY", "FANG", "PKI", "INVH", "RF", "EXPE",
    "GIS", "WBD", "ARE", "DGX", "STT", "HPE", "MKC", "K", "CNP", "IP",
    "LDOS", "NTRS", "VRSN", "LUV", "CINF", "FE", "WST", "UAL", "SWK", "PODD",
    "ZBRA", "TRMB", "CCL", "CF", "MAS", "HOLX", "AMCR", "MOH", "COO", "PFG",
    # 301-350
    "J", "NDAQ", "CLX", "IEX", "LH", "LNT", "TER", "CHRW", "CTRA", "ATO",
    "CBOE", "DRI", "CMS", "WRB", "EXPD", "STE", "AKAM", "WAT", "JBHT", "EVRG",
    "POOL", "LVS", "CPT", "JKHY", "EQR", "BBY", "CFG", "EPAM", "ULTA", "MAA",
    "BG", "KIM", "BALL", "SWKS", "INCY", "MRO", "HSY", "JNPR", "CAG", "EMN",
    "TECH", "HSIC", "TXT", "CRL", "UDR", "CTLT", "SNA", "ESS", "REG", "CE",
    # 351-400
    "VTRS", "OKE", "AVY", "NDSN", "PAYC", "PEAK", "BXP", "PNR", "WDC", "RJF",
    "BRO", "HII", "OMC", "AES", "ALGN", "LKQ", "TAP", "IPG", "ALLE", "CPB",
    "TPR", "HRL", "FFIV", "AIZ", "MKTX", "GL", "NI", "BBWI", "FOXA", "GNRC",
    "IVZ", "DXC", "PNW", "SEE", "BEN", "LW", "AAL", "FRT", "AOS", "CZR",
    "ALB", "UHS", "WYNN", "HAS", "RL", "NWS", "MHK", "PARA", "NWSA", "VFC",
    # 401-450
    "WHR", "BF.B", "NRG", "ZION", "BWA", "DVA", "NCLH", "DISH", "FMC", "PHM",
    "DVN", "TFX", "MTCH", "MGM", "MOS", "AAP", "ROL", "QRVO", "LEG", "PENN",
    "HES", "CMA", "UAA", "XRAY", "FOX", "KMX", "ALK", "ETSY", "RHI", "NWL",
    "PVH", "HBI", "GPS", "NOV", "FBHS", "VNO", "SLG", "NLSN", "BBY", "TYL",
    "IRM", "NWSA", "HST", "AIV", "APA", "LYV", "JBHT", "PEAK", "ENPH", "SMCI",
    # 451-500
    "RIVN", "LCID", "PLTR", "SNOW", "COIN", "RBLX", "U", "HOOD", "SOFI", "PANW",
    "CRWD", "ZS", "DDOG", "NET", "WDAY", "TEAM", "ZM", "DOCU", "OKTA", "MDB",
    "FTNT", "DT", "BILL", "S", "PATH", "DKNG", "ABNB", "DASH", "LYFT", "UBER",
    "DEI", "CSGP", "PGRE", "CUZ", "BDN", "PDM", "SUI", "ELS", "LSI", "STAG",
    "FR", "CUBE", "NSA", "PSB", "REXR", "EGP", "TRNO", "VRE", "KRG", "UE"
]

# Strategy templates with realistic characteristics
STRATEGY_TEMPLATES = {
    "high_frequency": {
        "timeframe": "1m",
        "lookback_options": [20, 50, 100],
        "instruments_range": (3, 5),
        "weight": 0.40  # 40% of strategies
    },
    "scalping": {
        "timeframe": "1m",
        "lookback_options": [50, 100],
        "instruments_range": (5, 8),
        "weight": 0.30  # 30% of strategies
    },
    "momentum": {
        "timeframe": "5m",
        "lookback_options": [100, 200],
        "instruments_range": (10, 15),
        "weight": 0.15  # 15% of strategies
    },
    "mean_reversion": {
        "timeframe": "5m",
        "lookback_options": [50, 100, 200],
        "instruments_range": (8, 12),
        "weight": 0.10  # 10% of strategies
    },
    "swing": {
        "timeframe": "15m",
        "lookback_options": [100, 200, 500],
        "instruments_range": (15, 25),
        "weight": 0.04  # 4% of strategies
    },
    "position": {
        "timeframe": "60m",
        "lookback_options": [100, 200],
        "instruments_range": (20, 30),
        "weight": 0.01  # 1% of strategies
    }
}


class LoadTestStrategy(BaseStrategy):
    """Strategy designed for load testing."""

    def __init__(self, strategy_id: int, strategy_type: str, instruments: List[str],
                 timeframe: str, lookback: int):
        name = f"{strategy_type}_{strategy_id}"
        super().__init__(name, instruments, timeframe, lookback)
        self.strategy_type = strategy_type
        self.strategy_id = strategy_id


class StrategyGenerator:
    """Generates realistic strategies for load testing."""

    def __init__(self, seed: int = 42, num_workers: int = 4):
        self.rng = random.Random(seed)
        self.num_workers = num_workers

        # Create instrument groups for each worker with controlled overlap
        self._setup_instrument_groups()

    def _setup_instrument_groups(self):
        """
        Setup instrument groups for multi-worker testing with controlled overlap.

        For 4 workers with 494 instruments:
        - Worker 0: Instruments   0-149 (150 primary) + hot instruments
        - Worker 1: Instruments 150-299 (150 primary) + hot instruments
        - Worker 2: Instruments 300-449 (150 primary) + hot instruments
        - Worker 3: Instruments   0-149 (150 primary) + hot instruments

        Hot instruments (last 44): Shared across all workers for realistic overlap
        """
        total_instruments = len(TEST_INSTRUMENTS)

        # Last 44 instruments are "hot" - shared across all workers
        self.hot_instruments = TEST_INSTRUMENTS[-44:]  # Instruments 451-494

        # Remaining 450 instruments divided into groups
        primary_instruments = TEST_INSTRUMENTS[:-44]  # Instruments 0-449
        instruments_per_group = len(primary_instruments) // self.num_workers

        self.worker_instrument_groups = {}
        for worker_id in range(self.num_workers):
            start_idx = worker_id * instruments_per_group
            end_idx = start_idx + instruments_per_group

            # Each worker gets: primary instruments + hot instruments
            primary = primary_instruments[start_idx:end_idx]
            self.worker_instrument_groups[worker_id] = primary + self.hot_instruments

        # Handle remainder (shouldn't be any with 450/4, but just in case)
        remainder_start = self.num_workers * instruments_per_group
        if remainder_start < len(primary_instruments):
            remainder = primary_instruments[remainder_start:]
            # Add remainder to last worker
            self.worker_instrument_groups[self.num_workers - 1].extend(remainder)

    def generate_strategies(self, count: int, worker_id: int = None) -> List[LoadTestStrategy]:
        """
        Generate N strategies with realistic distribution and controlled instrument overlap.

        Args:
            count: Number of strategies to generate
            worker_id: If provided, generates strategies for specific worker using its instrument group

        Returns:
            List of LoadTestStrategy instances
        """
        strategies = []

        # Determine strategy type distribution
        type_counts = self._calculate_type_distribution(count)

        strategy_id = 0
        for strategy_type, type_count in type_counts.items():
            template = STRATEGY_TEMPLATES[strategy_type]

            for _ in range(type_count):
                # Select instruments
                num_instruments = self.rng.randint(*template["instruments_range"])

                if worker_id is not None:
                    # Generate for specific worker using its instrument group
                    instruments = self._select_from_worker_group(worker_id, num_instruments)
                else:
                    # Generate for all workers (original behavior for backward compatibility)
                    instruments = self._select_from_all_instruments(num_instruments)

                # Select lookback period
                lookback = self.rng.choice(template["lookback_options"])

                strategy = LoadTestStrategy(
                    strategy_id=strategy_id,
                    strategy_type=strategy_type,
                    instruments=instruments,
                    timeframe=template["timeframe"],
                    lookback=lookback
                )

                strategies.append(strategy)
                strategy_id += 1

        return strategies

    def _calculate_type_distribution(self, total_count: int) -> Dict[str, int]:
        """Calculate how many strategies of each type to create."""
        distribution = {}

        for strategy_type, template in STRATEGY_TEMPLATES.items():
            count = int(total_count * template["weight"])
            if count > 0:
                distribution[strategy_type] = count

        # Adjust for rounding errors - add remainder to most common type
        assigned = sum(distribution.values())
        if assigned < total_count:
            distribution["high_frequency"] += (total_count - assigned)

        return distribution

    def _select_from_worker_group(self, worker_id: int, count: int) -> List[str]:
        """
        Select instruments from specific worker's group.

        80% from primary instruments, 20% from hot instruments for realistic overlap.
        """
        available_instruments = self.worker_instrument_groups[worker_id]

        # Calculate how many from primary vs hot
        hot_count = max(1, int(count * 0.20))  # 20% hot instruments
        primary_count = count - hot_count

        selected = []

        # Select from primary instruments (non-hot)
        primary_pool = [inst for inst in available_instruments if inst not in self.hot_instruments]
        if primary_pool and primary_count > 0:
            primary_selected = self.rng.sample(primary_pool, min(primary_count, len(primary_pool)))
            selected.extend(primary_selected)

        # Select from hot instruments
        if self.hot_instruments and hot_count > 0:
            hot_selected = self.rng.sample(self.hot_instruments, min(hot_count, len(self.hot_instruments)))
            selected.extend(hot_selected)

        # If we still need more, fill from remaining available
        if len(selected) < count:
            remaining = [inst for inst in available_instruments if inst not in selected]
            selected.extend(self.rng.sample(remaining, min(count - len(selected), len(remaining))))

        return selected[:count]

    def _select_from_all_instruments(self, count: int) -> List[str]:
        """Select instruments from all available (original behavior)."""
        return self.rng.sample(TEST_INSTRUMENTS, min(count, len(TEST_INSTRUMENTS)))

    def get_statistics(self, strategies: List[LoadTestStrategy]) -> Dict:
        """Get statistics about generated strategies."""
        stats = {
            "total_strategies": len(strategies),
            "by_type": {},
            "by_timeframe": {},
            "instruments": {
                "unique_count": len(set(inst for s in strategies for inst in s.instruments)),
                "total_count": sum(len(s.instruments) for s in strategies),
                "avg_per_strategy": sum(len(s.instruments) for s in strategies) / len(strategies),
                "most_common": {}
            },
            "lookback": {
                "min": min(s.lookback for s in strategies),
                "max": max(s.lookback for s in strategies),
                "avg": sum(s.lookback for s in strategies) / len(strategies)
            }
        }

        # Count by type
        for s in strategies:
            stats["by_type"][s.strategy_type] = stats["by_type"].get(s.strategy_type, 0) + 1
            stats["by_timeframe"][s.timeframe] = stats["by_timeframe"].get(s.timeframe, 0) + 1

        # Count instrument usage
        instrument_counts = {}
        for s in strategies:
            for inst in s.instruments:
                instrument_counts[inst] = instrument_counts.get(inst, 0) + 1

        # Top 10 most used instruments
        sorted_instruments = sorted(instrument_counts.items(), key=lambda x: x[1], reverse=True)
        stats["instruments"]["most_common"] = dict(sorted_instruments[:10])

        return stats
