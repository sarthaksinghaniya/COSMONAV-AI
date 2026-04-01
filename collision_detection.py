#!/usr/bin/env python3
"""
Space Situational Awareness - Collision Detection System
Using KD-Tree for efficient spatial indexing and TCA calculations
"""
import json
import numpy as np
from scipy.spatial import KDTree
from datetime import datetime
import math
import itertools

# Configuration
MAX_DISTANCE_KM = 5000.0  # Increased from 50km to 5000km for LEO analysis
COLLISION_THRESHOLDS = {
    'HIGH': 10.0,    # km (increased for space analysis)
    'MEDIUM': 50.0,  # km
    'LOW': 100.0     # km
}

def load_state_vectors(filepath):
    """Load and validate state vectors from JSON file"""
    print("Loading state vectors...")
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        # Validate structure
        validated_data = []
        for i, obj in enumerate(data):
            try:
                # Required fields
                assert 'position' in obj and len(obj['position']) == 3
                assert 'velocity' in obj and len(obj['velocity']) == 3
                assert 'name' in obj
                assert 'norad_id' in obj

                # Convert to numpy arrays
                obj['position'] = np.array(obj['position'], dtype=np.float64)
                obj['velocity'] = np.array(obj['velocity'], dtype=np.float64)

                # Validate values
                pos_mag = np.linalg.norm(obj['position'])
                vel_mag = np.linalg.norm(obj['velocity'])

                if pos_mag < 5000 or pos_mag > 20000:  # Reasonable orbital range
                    print(f"  Warning: Object {obj['name']} has unusual position magnitude: {pos_mag:.1f} km")
                    continue

                if vel_mag < 1.0 or vel_mag > 20.0:  # Reasonable orbital speeds
                    print(f"  Warning: Object {obj['name']} has unusual velocity magnitude: {vel_mag:.3f} km/s")
                    continue

                validated_data.append(obj)

            except (AssertionError, ValueError, TypeError) as e:
                print(f"  Skipping invalid object {i}: {e}")
                continue

        print(f"  Loaded {len(validated_data)} valid state vectors")
        return validated_data

    except Exception as e:
        print(f"Error loading state vectors: {e}")
        return []

def build_spatial_index(objects):
    """Build KD-Tree for efficient spatial queries"""
    print("Building spatial index (KD-Tree)...")
    positions = np.array([obj['position'] for obj in objects])
    tree = KDTree(positions)
    print(f"  KD-Tree built with {len(objects)} objects")
    return tree, positions

def calculate_tca_and_distance(obj1, obj2):
    """Calculate Time to Closest Approach and minimum distance"""
    # Relative position and velocity
    r_rel = obj1['position'] - obj2['position']  # km
    v_rel = obj1['velocity'] - obj2['velocity']  # km/s

    # Magnitude squared of relative velocity
    v_rel_mag_sq = np.dot(v_rel, v_rel)

    if v_rel_mag_sq < 1e-10:  # Nearly zero relative velocity
        # Objects are moving parallel, use current distance
        distance = np.linalg.norm(r_rel)
        return 0.0, distance

    # Time to closest approach: tca = - (r_rel · v_rel) / |v_rel|²
    tca = -np.dot(r_rel, v_rel) / v_rel_mag_sq

    # If TCA is negative, objects are moving apart
    if tca < 0:
        return None, None

    # Position at TCA
    r_tca = r_rel + v_rel * tca
    distance = np.linalg.norm(r_tca)

    return tca, distance

def assess_collision_risk(distance_km):
    """Assess collision risk based on minimum distance"""
    if distance_km < COLLISION_THRESHOLDS['HIGH']:
        return 'HIGH'
    elif distance_km < COLLISION_THRESHOLDS['MEDIUM']:
        return 'MEDIUM'
    elif distance_km < COLLISION_THRESHOLDS['LOW']:
        return 'LOW'
    else:
        return None

def calculate_collision_probability(distance_km, tca_seconds, v_rel_mag):
    """Calculate heuristic collision probability score"""
    # Simplified probability model based on:
    # - Distance (closer = higher risk)
    # - Time to approach (sooner = higher risk)
    # - Relative velocity (higher = more dangerous)

    if distance_km > 10.0:
        return 0.0

    # Distance factor (inverse relationship)
    dist_factor = max(0.1, 10.0 / distance_km)

    # Time factor (sooner is riskier, but not too soon)
    time_factor = max(0.1, min(2.0, 3600.0 / max(tca_seconds, 60.0)))

    # Velocity factor (higher relative speed increases risk)
    vel_factor = min(3.0, v_rel_mag / 5.0)

    # Combined probability score (0-100 scale)
    probability = min(100.0, dist_factor * time_factor * vel_factor * 10.0)

    return round(probability, 2)

def find_collision_candidates(objects, tree, positions):
    """Find potential collision candidates using spatial indexing"""
    print("Finding collision candidates...")

    collision_alerts = []
    pairs_checked = 0
    candidates_found = 0

    # For each object, find neighbors within MAX_DISTANCE_KM
    for i, obj1 in enumerate(objects):
        if i % 50 == 0:
            print(f"  Processing object {i+1}/{len(objects)}...")

        # Query KD-tree for neighbors within MAX_DISTANCE_KM
        indices = tree.query_ball_point(positions[i], MAX_DISTANCE_KM)

        # Remove self from results
        indices = [idx for idx in indices if idx != i]

        for j in indices:
            obj2 = objects[j]
            pairs_checked += 1

            # Calculate TCA and minimum distance
            tca, distance = calculate_tca_and_distance(obj1, obj2)

            if tca is None or distance is None:
                continue  # Objects moving apart or invalid

            # Assess collision risk
            risk_level = assess_collision_risk(distance)
            if risk_level is None:
                continue  # No risk

            # Calculate relative velocity magnitude
            v_rel = obj1['velocity'] - obj2['velocity']
            v_rel_mag = np.linalg.norm(v_rel)

            # Calculate collision probability
            probability = calculate_collision_probability(distance, tca, v_rel_mag)

            # Create alert
            alert = {
                "object_1": obj1['name'],
                "object_2": obj2['name'],
                "norad_1": obj1['norad_id'],
                "norad_2": obj2['norad_id'],
                "distance_km": round(distance, 3),
                "tca_seconds": round(tca, 1),
                "risk_level": risk_level,
                "collision_probability": probability,
                "relative_velocity_kms": round(v_rel_mag, 3),
                "current_separation_km": round(np.linalg.norm(obj1['position'] - obj2['position']), 3)
            }

            collision_alerts.append(alert)
            candidates_found += 1

    print(f"  Checked {pairs_checked} pairs")
    print(f"  Found {candidates_found} collision candidates")

    return collision_alerts

def rank_top_risks(alerts, top_n=10):
    """Rank alerts by collision probability and distance"""
    if not alerts:
        return []

    # Sort by collision probability (descending), then by distance (ascending)
    ranked = sorted(alerts,
                    key=lambda x: (-x['collision_probability'], x['distance_km']))

    return ranked[:top_n]

def save_collision_alerts(alerts, filepath):
    """Save collision alerts to JSON file"""
    print(f"Saving {len(alerts)} collision alerts...")

    try:
        with open(filepath, 'w') as f:
            json.dump(alerts, f, indent=2)
        print(f"  Saved to: {filepath}")
        print(f"  File size: {len(alerts)} alerts")
    except Exception as e:
        print(f"Error saving alerts: {e}")

def generate_summary(alerts, objects):
    """Generate comprehensive analysis summary"""
    print("\n" + "=" * 70)
    print("COLLISION DETECTION ANALYSIS SUMMARY")
    print("=" * 70)

    total_objects = len(objects)
    total_alerts = len(alerts)

    # Risk level breakdown
    risk_counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    for alert in alerts:
        risk_counts[alert['risk_level']] += 1

    print(f"\nObjects analyzed: {total_objects}")
    print(f"Collision alerts generated: {total_alerts}")
    print(f"Alert rate: {total_alerts/max(1, total_objects*(total_objects-1)//2)*100:.3f}% of possible pairs")

    print(f"\nRisk Level Breakdown:")
    print(f"  HIGH risk (< 1 km):     {risk_counts['HIGH']:4d} alerts")
    print(f"  MEDIUM risk (< 5 km):   {risk_counts['MEDIUM']:4d} alerts")
    print(f"  LOW risk (< 10 km):     {risk_counts['LOW']:4d} alerts")

    if alerts:
        # Statistics
        distances = [a['distance_km'] for a in alerts]
        tcas = [a['tca_seconds'] for a in alerts]
        probabilities = [a['collision_probability'] for a in alerts]

        print(f"\nDistance Statistics:")
        print(f"  Minimum: {min(distances):.3f} km")
        print(f"  Maximum: {max(distances):.3f} km")
        print(f"  Average: {np.mean(distances):.3f} km")
        print(f"  Median:  {np.median(distances):.3f} km")

        print(f"\nTCA Statistics:")
        print(f"  Minimum: {min(tcas):.1f} seconds")
        print(f"  Maximum: {max(tcas):.1f} seconds")
        print(f"  Average: {np.mean(tcas):.1f} seconds")

        print(f"\nCollision Probability:")
        print(f"  Maximum: {max(probabilities):.2f}%")
        print(f"  Average: {np.mean(probabilities):.2f}%")

        # Top risk
        top_risk = max(alerts, key=lambda x: x['collision_probability'])
        print(f"\nHighest Risk Collision:")
        print(f"  Objects: {top_risk['object_1']} vs {top_risk['object_2']}")
        print(f"  Distance: {top_risk['distance_km']:.3f} km")
        print(f"  TCA: {top_risk['tca_seconds']:.1f} seconds")
        print(f"  Risk Level: {top_risk['risk_level']}")
        print(f"  Collision Probability: {top_risk['collision_probability']:.2f}%")

    print("\n" + "=" * 70)

def main():
    print("=" * 70)
    print("SPACE SITUATIONAL AWARENESS - COLLISION DETECTION SYSTEM")
    print("=" * 70)

    # Load data
    objects = load_state_vectors('dataset/state_vectors.json')
    if not objects:
        print("No valid objects loaded. Exiting.")
        return False

    # Build spatial index
    tree, positions = build_spatial_index(objects)

    # Find collision candidates
    alerts = find_collision_candidates(objects, tree, positions)

    # Rank top risks
    top_risks = rank_top_risks(alerts, top_n=10)

    # Save results
    save_collision_alerts(alerts, 'dataset/collision_alerts.json')

    # Generate summary
    generate_summary(alerts, objects)

    # Save top risks separately
    if top_risks:
        save_collision_alerts(top_risks, 'dataset/top_collision_risks.json')
        print(f"\nTop 10 highest risk collisions saved to: dataset/top_collision_risks.json")

    print("\nCollision detection analysis complete!")
    return True

if __name__ == "__main__":
    main()
