#!/usr/bin/env python3
"""Generate flame graph visualizations from profiling data."""

import pstats
import sys
from pathlib import Path


def generate_callgraph(prof_file: Path, output_file: Path):
    """Generate a call graph from profiling data."""
    stats = pstats.Stats(str(prof_file))
    stats.sort_stats('cumulative')

    # Get top functions
    top_functions = []
    for func, (cc, nc, tt, ct, callers) in stats.stats.items():
        filename, line, func_name = func
        top_functions.append({
            'name': func_name,
            'file': filename,
            'line': line,
            'ncalls': nc,
            'tottime': tt,
            'cumtime': ct,
            'percall': ct / nc if nc > 0 else 0
        })

    # Sort by cumulative time
    top_functions.sort(key=lambda x: x['cumtime'], reverse=True)

    # Generate HTML visualization
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Performance Profile</title>
    <style>
        body {{ font-family: 'Courier New', monospace; margin: 20px; background: #1e1e1e; color: #d4d4d4; }}
        h1 {{ color: #4ec9b0; }}
        h2 {{ color: #569cd6; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th {{ background: #264f78; color: white; padding: 10px; text-align: left; position: sticky; top: 0; }}
        td {{ padding: 8px; border-bottom: 1px solid #3c3c3c; }}
        tr:hover {{ background: #2d2d30; }}
        .hot {{ color: #f48771; font-weight: bold; }}
        .warm {{ color: #ce9178; }}
        .cool {{ color: #4ec9b0; }}
        .bar {{ background: #0e639c; height: 20px; display: inline-block; }}
        .metric {{ font-family: monospace; text-align: right; }}
    </style>
</head>
<body>
    <h1>🔥 Performance Profile: {prof_file.name}</h1>

    <h2>Top Functions by Cumulative Time</h2>
    <p>Functions that consume the most time (including calls to other functions)</p>

    <table>
        <thead>
            <tr>
                <th>Function</th>
                <th>Location</th>
                <th>Calls</th>
                <th>Total Time</th>
                <th>Cumulative</th>
                <th>Per Call</th>
                <th>Profile</th>
            </tr>
        </thead>
        <tbody>
"""

    max_cumtime = max(f['cumtime'] for f in top_functions[:50]) if top_functions else 1

    for i, func in enumerate(top_functions[:50]):
        # Color code by importance
        if i < 5:
            color_class = 'hot'
        elif i < 15:
            color_class = 'warm'
        else:
            color_class = 'cool'

        # Bar width proportional to cumulative time
        bar_width = int((func['cumtime'] / max_cumtime) * 300)

        # Clean up file path
        file_path = func['file']
        if 'site-packages' in file_path:
            file_path = '...' + file_path.split('site-packages')[-1]
        elif len(file_path) > 60:
            file_path = '...' + file_path[-57:]

        html += f"""
            <tr>
                <td class="{color_class}">{func['name']}</td>
                <td><small>{file_path}:{func['line']}</small></td>
                <td class="metric">{func['ncalls']:,}</td>
                <td class="metric">{func['tottime']:.3f}s</td>
                <td class="metric">{func['cumtime']:.3f}s</td>
                <td class="metric">{func['percall']*1000:.2f}ms</td>
                <td><div class="bar" style="width: {bar_width}px;"></div></td>
            </tr>
"""

    html += """
        </tbody>
    </table>

    <h2>Top Functions by Total Time</h2>
    <p>Functions that consume the most time (excluding calls to other functions)</p>

    <table>
        <thead>
            <tr>
                <th>Function</th>
                <th>Location</th>
                <th>Total Time</th>
                <th>% of Total</th>
                <th>Profile</th>
            </tr>
        </thead>
        <tbody>
"""

    # Sort by total time
    by_tottime = sorted(top_functions, key=lambda x: x['tottime'], reverse=True)[:30]
    max_tottime = max(f['tottime'] for f in by_tottime) if by_tottime else 1
    total_time = sum(f['tottime'] for f in top_functions)

    for func in by_tottime:
        bar_width = int((func['tottime'] / max_tottime) * 300)
        percentage = (func['tottime'] / total_time * 100) if total_time > 0 else 0

        file_path = func['file']
        if 'site-packages' in file_path:
            file_path = '...' + file_path.split('site-packages')[-1]
        elif len(file_path) > 60:
            file_path = '...' + file_path[-57:]

        html += f"""
            <tr>
                <td>{func['name']}</td>
                <td><small>{file_path}:{func['line']}</small></td>
                <td class="metric">{func['tottime']:.3f}s</td>
                <td class="metric">{percentage:.1f}%</td>
                <td><div class="bar" style="width: {bar_width}px;"></div></td>
            </tr>
"""

    html += """
        </tbody>
    </table>

    <footer style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #3c3c3c; color: #858585;">
        <p>Generated from cProfile data</p>
    </footer>
</body>
</html>
"""

    with open(output_file, 'w') as f:
        f.write(html)

    print(f"✓ Generated {output_file}")


def main():
    output_dir = Path('./profiling_output')

    # Generate for both profiles
    profiles = [
        ('cpu_2-tier.prof', 'profile_2tier.html'),
        ('cpu_3-tier.prof', 'profile_3tier.html')
    ]

    for prof_file, html_file in profiles:
        prof_path = output_dir / prof_file
        html_path = output_dir / html_file

        if prof_path.exists():
            print(f"\nProcessing {prof_file}...")
            generate_callgraph(prof_path, html_path)
        else:
            print(f"Warning: {prof_path} not found")

    print(f"\n✓ Profile visualizations generated in {output_dir}/")
    print("\nOpen the HTML files in a browser to view the interactive profiles:")
    print(f"  - {output_dir}/profile_2tier.html")
    print(f"  - {output_dir}/profile_3tier.html")


if __name__ == '__main__':
    main()
