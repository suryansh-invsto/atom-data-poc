# Cache Architecture Performance POC

Performance comparison between 2-tier (API + Redis) and 3-tier (API + Redis + Memory) cache architectures for trading strategy engine.

## Setup

1. Start Redis:
```bash
docker-compose up -d
```

2. Install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Create environment file:
```bash
cp .env.example .env
```

## Running Tests

### 2-Tier Test
```bash
python main.py --mode 2-tier --duration 60
```

### 3-Tier Test
```bash
python main.py --mode 3-tier --duration 60
```

### Generate Comparison Report
```bash
python generate_report.py
```

## Project Structure

```
.
├── docker-compose.yml          # Redis setup
├── requirements.txt            # Python dependencies
├── main.py                     # Test runner
├── src/
│   ├── data_services.py       # 2-tier and 3-tier implementations
│   ├── strategies.py          # Mock trading strategies
│   ├── metrics.py             # Performance tracking
│   └── load_test.py           # Load test orchestration
├── profiling_output/          # Generated test results
└── generate_report.py         # Report generator
```
