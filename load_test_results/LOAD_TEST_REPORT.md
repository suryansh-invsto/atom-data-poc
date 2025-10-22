# Load Test Comparison Report

## Test Configuration

- **Instruments Pool**: 50 stocks
- **Instruments per Strategy**: 3-30 (varies by type)
- **Test Duration**: 10 simulated minutes
- **Strategy Mix**: High-frequency, Scalping, Momentum, Mean-reversion, Swing, Position

## Results Comparison

### Latency Performance

| Strategies | 2-Tier P50 | 2-Tier P99 | 3-Tier P50 | 3-Tier P99 | Improvement |
|------------|------------|------------|------------|------------|-------------|
|        100 |   1199.158 |   1686.232 |     14.903 |     35.655 | 80.5x       |
|         10 |   1120.872 |   1204.348 |     22.421 |     35.655 | 50.0x       |
|         25 |   1128.618 |   1378.256 |     14.903 |     35.655 | 75.7x       |
|         50 |   1192.501 |   1686.232 |     14.903 |     35.655 | 80.0x       |

### Resource Utilization

| Strategies | 2-Tier CPU | 2-Tier Mem | 3-Tier CPU | 3-Tier Mem | Mem Diff |
|------------|------------|------------|------------|------------|----------|
|        100 |        0.0 |      144.2 |        0.0 |       77.8 | +   -66.4 |
|         10 |        0.0 |       75.5 |        0.0 |       65.0 | +   -10.6 |
|         25 |        0.0 |      105.1 |        0.0 |       78.0 | +   -27.0 |
|         50 |        0.0 |      117.3 |        0.0 |       80.7 | +   -36.6 |

### Key Findings

- **Average Speedup**: 1.99x faster with 3-tier
- **Memory Overhead**: +-35.1 MB average for in-memory cache
- **Max Tested Capacity**: 100 strategies (2-tier), 100 strategies (3-tier)

### Recommendations

Based on the test results:

1. **3-tier architecture is recommended** for production deployment
2. Memory overhead is minimal compared to performance gains
3. System can comfortably handle tested load levels
4. Consider horizontal scaling for loads beyond tested capacity
