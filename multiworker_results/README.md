# Multi-Worker Cache Architecture Performance Tests

## Overview

Testing memory efficiency and cache performance across different cache architectures and worker assignment strategies for a trading strategy execution engine.

**Main Test File**: `multiworker_test.py`

## Test Setup

- **Workers**: 4 processes
- **Strategies**: 500 total
- **Instruments**: ~494 with controlled 30% overlap
- **Duration**: 5 minutes real-time execution
- **Data**: New 1m bars fetched every 60 seconds

## Cache Architectures

### 2-tier
Redis-only caching. Every request hits Redis (network call).

### 3-tier-redundant
Each worker maintains its own isolated memory cache + shared Redis.
**Problem**: Data duplicated across all 4 workers.

### 3-tier-shared
All workers share a single memory cache (via `multiprocessing.Manager()`) + Redis.
**Benefit**: No data duplication, optimal memory usage.

## Assignment Strategies

### Sticky
Strategies assigned by consistent hashing on `strategy_id`.
Simple load balancing.

### Sharded
Strategies assigned by hashing on `primary_instrument`.
All strategies trading the same instrument run on the same worker.
**Benefit**: Better cache locality.

## Test Scenarios

| Scenario | Total Memory (MB) | Description |
|----------|------------------|-------------|
| **3-tier-shared + sharded** | **365.6** | ⭐ Winner: Shared cache + instrument locality |
| 3-tier-shared + sticky | 403.7 | Shared cache, suboptimal locality |
| 3-tier-redundant + sharded | 532.6 | Per-worker cache duplication |
| 2-tier + sticky | 551.1 | Redis-only, better connection reuse |
| 2-tier + sharded | 592.3 | Redis-only, worst case |
| 3-tier-redundant + sticky | 574.1 | Duplication + poor locality |

## Results Summary

**Best Configuration**: 3-tier-shared with sharded assignment
- **Memory**: 365.6 MB (38% less than worst case)
- **Cache Hit Rate**: 84.7% (memory layer)
- **Key Insight**: Shared memory eliminates duplication, sharded assignment optimizes locality

## Running Tests

```bash
# Single test
python multiworker_test.py 4 3-tier-shared sharded

# All scenarios
./run_all_tests.sh
```

## Files

- `multiworker_4w_*.json` - Latest test results with controlled instrument distribution
- `old results ; high overlap/` - Previous tests with 80%+ instrument overlap (invalid)
- `old results ; simulated/` - Previous simulated tests (not real-time)
