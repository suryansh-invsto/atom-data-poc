"""System metrics collection for load testing."""

import psutil
import time
import os
from typing import Dict, List
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class SystemSnapshot:
    """Single point-in-time system metrics snapshot."""
    timestamp: float
    cpu_percent: float
    cpu_per_core: List[float]
    memory_rss_mb: float
    memory_vms_mb: float
    memory_percent: float
    network_bytes_sent: int
    network_bytes_recv: int
    open_files: int
    num_threads: int


class SystemMetricsCollector:
    """Collects system-level performance metrics during load tests."""

    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.snapshots: List[SystemSnapshot] = []
        self.start_time = None
        self.start_network = None

    def start_collection(self):
        """Initialize baseline metrics."""
        self.start_time = time.time()
        net_io = psutil.net_io_counters()
        self.start_network = {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv
        }

    def collect_snapshot(self) -> SystemSnapshot:
        """Collect current system metrics."""
        # Get process-specific metrics
        with self.process.oneshot():
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            num_threads = self.process.num_threads()
            try:
                open_files = len(self.process.open_files())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                open_files = 0

        # Get CPU metrics
        cpu_percent = self.process.cpu_percent(interval=0.1)
        cpu_per_core = psutil.cpu_percent(interval=0.1, percpu=True)

        # Get network metrics
        net_io = psutil.net_io_counters()

        snapshot = SystemSnapshot(
            timestamp=time.time() - (self.start_time or time.time()),
            cpu_percent=cpu_percent,
            cpu_per_core=cpu_per_core,
            memory_rss_mb=memory_info.rss / 1024 / 1024,
            memory_vms_mb=memory_info.vms / 1024 / 1024,
            memory_percent=memory_percent,
            network_bytes_sent=net_io.bytes_sent - (self.start_network['bytes_sent'] if self.start_network else 0),
            network_bytes_recv=net_io.bytes_recv - (self.start_network['bytes_recv'] if self.start_network else 0),
            open_files=open_files,
            num_threads=num_threads
        )

        self.snapshots.append(snapshot)
        return snapshot

    def get_summary(self) -> Dict:
        """Generate summary statistics from collected snapshots."""
        if not self.snapshots:
            return {}

        cpu_percents = [s.cpu_percent for s in self.snapshots]
        memory_rss = [s.memory_rss_mb for s in self.snapshots]
        memory_percent = [s.memory_percent for s in self.snapshots]
        threads = [s.num_threads for s in self.snapshots]

        # Calculate network throughput
        if len(self.snapshots) > 1:
            duration = self.snapshots[-1].timestamp - self.snapshots[0].timestamp
            if duration > 0:
                bytes_sent_per_sec = self.snapshots[-1].network_bytes_sent / duration
                bytes_recv_per_sec = self.snapshots[-1].network_bytes_recv / duration
            else:
                bytes_sent_per_sec = bytes_recv_per_sec = 0
        else:
            bytes_sent_per_sec = bytes_recv_per_sec = 0

        return {
            "duration_seconds": self.snapshots[-1].timestamp if self.snapshots else 0,
            "cpu": {
                "avg_percent": sum(cpu_percents) / len(cpu_percents),
                "max_percent": max(cpu_percents),
                "min_percent": min(cpu_percents),
                "num_cores": len(self.snapshots[0].cpu_per_core) if self.snapshots else 0
            },
            "memory": {
                "avg_rss_mb": sum(memory_rss) / len(memory_rss),
                "max_rss_mb": max(memory_rss),
                "peak_percent": max(memory_percent),
                "final_rss_mb": memory_rss[-1]
            },
            "network": {
                "total_sent_mb": self.snapshots[-1].network_bytes_sent / 1024 / 1024,
                "total_recv_mb": self.snapshots[-1].network_bytes_recv / 1024 / 1024,
                "avg_send_mbps": (bytes_sent_per_sec * 8 / 1024 / 1024),
                "avg_recv_mbps": (bytes_recv_per_sec * 8 / 1024 / 1024)
            },
            "threads": {
                "avg": sum(threads) / len(threads),
                "max": max(threads),
                "final": threads[-1]
            },
            "snapshots_collected": len(self.snapshots)
        }

    def get_time_series(self) -> Dict[str, List]:
        """Get time series data for plotting."""
        return {
            "timestamps": [s.timestamp for s in self.snapshots],
            "cpu_percent": [s.cpu_percent for s in self.snapshots],
            "memory_rss_mb": [s.memory_rss_mb for s in self.snapshots],
            "memory_percent": [s.memory_percent for s in self.snapshots],
            "num_threads": [s.num_threads for s in self.snapshots]
        }

    def print_summary(self):
        """Print human-readable summary."""
        summary = self.get_summary()

        if not summary:
            print("No metrics collected")
            return

        print(f"\n{'='*60}")
        print("System Metrics Summary")
        print(f"{'='*60}")

        print(f"\nDuration: {summary['duration_seconds']:.2f}s")

        print(f"\nCPU ({summary['cpu']['num_cores']} cores):")
        print(f"  Average: {summary['cpu']['avg_percent']:.1f}%")
        print(f"  Peak:    {summary['cpu']['max_percent']:.1f}%")

        print(f"\nMemory:")
        print(f"  Average RSS: {summary['memory']['avg_rss_mb']:.1f} MB")
        print(f"  Peak RSS:    {summary['memory']['max_rss_mb']:.1f} MB")
        print(f"  Final RSS:   {summary['memory']['final_rss_mb']:.1f} MB")
        print(f"  Peak %:      {summary['memory']['peak_percent']:.1f}%")

        print(f"\nNetwork:")
        print(f"  Sent:     {summary['network']['total_sent_mb']:.2f} MB")
        print(f"  Received: {summary['network']['total_recv_mb']:.2f} MB")
        print(f"  Avg Send: {summary['network']['avg_send_mbps']:.2f} Mbps")
        print(f"  Avg Recv: {summary['network']['avg_recv_mbps']:.2f} Mbps")

        print(f"\nThreads:")
        print(f"  Average: {summary['threads']['avg']:.0f}")
        print(f"  Peak:    {summary['threads']['max']}")
        print(f"  Final:   {summary['threads']['final']}")

        print(f"{'='*60}\n")
