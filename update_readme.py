#!/usr/bin/env python3
"""
README.md Auto-Updater for ISRO SSA Project
Updates README.md with latest metrics and status information
"""

import json
import os
from datetime import datetime

def update_readme_metrics():
    """Update README.md with current project metrics"""

    dataset_dir = "dataset"
    readme_path = "README.md"

    # Check if files exist
    collision_alerts_file = os.path.join(dataset_dir, "collision_alerts.json")
    state_vectors_file = os.path.join(dataset_dir, "state_vectors.json")
    clean_satellites_file = os.path.join(dataset_dir, "clean_satellites.json")

    updates = {}

    # Load collision alerts
    if os.path.exists(collision_alerts_file):
        with open(collision_alerts_file, 'r') as f:
            alerts = json.load(f)

        # Calculate risk distribution
        risk_counts = {}
        for alert in alerts:
            risk = alert['risk_level']
            risk_counts[risk] = risk_counts.get(risk, 0) + 1

        updates['total_alerts'] = len(alerts)
        updates['high_risk'] = risk_counts.get('HIGH', 0)
        updates['medium_risk'] = risk_counts.get('MEDIUM', 0)
        updates['low_risk'] = risk_counts.get('LOW', 0)

        # Find closest approach
        if alerts:
            min_distance_alert = min(alerts, key=lambda x: x['distance_km'])
            updates['closest_approach'] = min_distance_alert['distance_km']
            updates['closest_pair'] = f"{min_distance_alert['object_1']} ↔ {min_distance_alert['object_2']}"

    # Load state vectors count
    if os.path.exists(state_vectors_file):
        with open(state_vectors_file, 'r') as f:
            state_vectors = json.load(f)
        updates['state_vectors_count'] = len(state_vectors)

    # Load clean satellites count
    if os.path.exists(clean_satellites_file):
        with open(clean_satellites_file, 'r') as f:
            satellites = json.load(f)
        updates['clean_satellites_count'] = len(satellites)

    # Update README.md if we have new data
    if updates:
        update_readme_file(readme_path, updates)
        print(f"README.md updated with latest metrics: {updates}")
    else:
        print("No updates needed - data files not found")

def update_readme_file(readme_path, updates):
    """Update specific sections in README.md"""

    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Update status section
    if 'total_alerts' in updates:
        old_status = "Total Alerts:     60"
        new_status = f"Total Alerts:     {updates['total_alerts']}"
        content = content.replace(old_status, new_status)

        old_high = "├── HIGH Risk:    6  (10.0%)"
        new_high = f"├── HIGH Risk:    {updates['high_risk']}  ({updates['high_risk']/updates['total_alerts']*100:.1f}%)"
        content = content.replace(old_high, new_high)

        old_medium = "├── MEDIUM Risk:  16 (26.7%)"
        new_medium = f"├── MEDIUM Risk:  {updates['medium_risk']}  ({updates['medium_risk']/updates['total_alerts']*100:.1f}%)"
        content = content.replace(old_medium, new_medium)

        old_low = "└── LOW Risk:     38 (63.3%)"
        new_low = f"└── LOW Risk:     {updates['low_risk']}  ({updates['low_risk']/updates['total_alerts']*100:.1f}%)"
        content = content.replace(old_low, new_low)

    # Update closest approach
    if 'closest_approach' in updates:
        old_closest = "Closest Approach:** 4.131 km (STARLINK-35071 ↔ STARLINK-32400)"
        new_closest = f"Closest Approach:** {updates['closest_approach']:.3f} km ({updates['closest_pair']})"
        content = content.replace(old_closest, new_closest)

    # Update last modified date
    current_date = datetime.now().strftime("%B %d, %Y")
    old_date = "**Last Updated:** April 1, 2026"
    new_date = f"**Last Updated:** {current_date}"
    content = content.replace(old_date, new_date)

    # Write back updated content
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    update_readme_metrics()