import json
import networkx as nx
import matplotlib.pyplot as plt
from collections import defaultdict
import os

# Constants
HIGH_THRESHOLD = 0.01  # Define HIGH Pc threshold
MEDIUM_THRESHOLD = 0.001  # Define MEDIUM Pc threshold
MAX_DELTA_V = 1.0  # m/s, example max delta-v per satellite
FUEL_COST_FACTOR = 1.0  # Example fuel cost per delta-v

# Load data
def load_data():
    with open('outputs/state_vectors_enhanced.json', 'r') as f:
        satellites = json.load(f)
    with open('outputs/collision_alerts_enhanced.json', 'r') as f:
        alerts = json.load(f)
    with open('outputs/decision_log_pc_enhanced.json', 'r') as f:
        decisions = json.load(f)
    return satellites, alerts, decisions

# Filter high and medium risk alerts
def filter_risks(alerts):
    high_medium = []
    for alert in alerts:
        pc = alert.get('collision_probability', 0)
        if pc >= MEDIUM_THRESHOLD:  # MEDIUM and HIGH
            high_medium.append(alert)
    return high_medium

# Build interaction graph
def build_graph(high_medium_alerts):
    G = nx.Graph()
    for alert in high_medium_alerts:
        obj1 = alert['object_1']
        obj2 = alert['object_2']
        pc = alert['collision_probability']
        tca = alert['tca_seconds']
        weight = pc * (1 / (tca + 1))  # Weight by Pc and inverse TCA
        G.add_edge(obj1, obj2, weight=weight, pc=pc, tca=tca)
    return G

# Conflict grouping using connected components
def conflict_grouping(G):
    return list(nx.connected_components(G))

# Generate candidate maneuvers (simple: small delta-v in directions)
def generate_candidates(satellite, max_dv=MAX_DELTA_V):
    candidates = [
        {'delta_v': [0, 0, 0], 'action': 'HOLD'},
        {'delta_v': [0.1, 0, 0], 'action': 'MANEUVER'},
        {'delta_v': [0, 0.1, 0], 'action': 'MANEUVER'},
        {'delta_v': [0, 0, 0.1], 'action': 'MANEUVER'},
        {'delta_v': [-0.1, 0, 0], 'action': 'MANEUVER'},
        {'delta_v': [0, -0.1, 0], 'action': 'MANEUVER'},
        {'delta_v': [0, 0, -0.1], 'action': 'MANEUVER'},
    ]
    return candidates

# Evaluate maneuver (simplified)
def evaluate_maneuver(satellite, maneuver, cluster_alerts, all_alerts):
    fuel_cost = sum(abs(dv) for dv in maneuver['delta_v']) * FUEL_COST_FACTOR
    # Simplified risk reduction: assume maneuver reduces Pc by factor
    risk_reduction = 0.5 * sum(alert['collision_probability'] for alert in cluster_alerts if satellite in [alert['object_1'], alert['object_2']])
    # Secondary risk: check if new alerts created (simplified, assume none)
    secondary_risk = 0
    return fuel_cost, risk_reduction, secondary_risk

# Global optimization for cluster (greedy: choose best for each satellite)
def optimize_cluster(cluster, alerts, all_alerts):
    decisions = {}
    for sat in cluster:
        cluster_alerts = [a for a in alerts if a['object_1'] in cluster and a['object_2'] in cluster]
        candidates = generate_candidates(sat)
        best = min(candidates, key=lambda m: evaluate_maneuver(sat, m, cluster_alerts, all_alerts)[0] - evaluate_maneuver(sat, m, cluster_alerts, all_alerts)[1])  # Minimize cost - reduction
        fuel, red, sec = evaluate_maneuver(sat, best, cluster_alerts, all_alerts)
        decisions[sat] = {
            "satellite": sat,
            "action": best['action'],
            "delta_v": best['delta_v'],
            "fuel_cost": fuel,
            "risk_reduction": red,
            "secondary_risk": sec
        }
    return decisions

# Main engine
def fleet_optimization():
    satellites, alerts, decisions = load_data()
    high_medium_alerts = filter_risks(alerts)
    G = build_graph(high_medium_alerts)
    clusters = conflict_grouping(G)
    all_decisions = {}
    for cluster in clusters:
        cluster_decisions = optimize_cluster(cluster, high_medium_alerts, alerts)
        all_decisions.update(cluster_decisions)
    
    # Save outputs
    os.makedirs('outputs', exist_ok=True)
    with open('outputs/fleet_optimization.json', 'w') as f:
        json.dump(list(all_decisions.values()), f, indent=2)
    
    # Fleet summary
    total_risk_before = sum(a['collision_probability'] for a in alerts)
    total_risk_after = total_risk_before - sum(d['risk_reduction'] for d in all_decisions.values())
    total_fuel = sum(d['fuel_cost'] for d in all_decisions.values())
    efficiency_gain = (total_risk_before - total_risk_after) / total_risk_before * 100 if total_risk_before > 0 else 0
    
    summary = {
        "total_risk_before": total_risk_before,
        "total_risk_after": total_risk_after,
        "fuel_consumption_total": total_fuel,
        "efficiency_gain_percent": efficiency_gain
    }
    with open('outputs/fleet_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Visualizations
    os.makedirs('outputs/plots', exist_ok=True)
    # Graph visualization
    plt.figure(figsize=(10, 8))
    pos = nx.spring_layout(G)
    nx.draw(G, pos, with_labels=True, node_color='skyblue', edge_color='red', width=[d['weight']*10 for u,v,d in G.edges(data=True)])
    plt.title('Fleet Interaction Graph')
    plt.savefig('outputs/plots/fleet_graph.png')
    plt.close()
    
    # Before after risk (simple bar chart)
    plt.figure()
    plt.bar(['Before', 'After'], [total_risk_before, total_risk_after])
    plt.title('Risk Comparison')
    plt.ylabel('Total Collision Probability')
    plt.savefig('outputs/plots/before_after_risk.png')
    plt.close()
    
    return all_decisions, summary

if __name__ == "__main__":
    decisions, summary = fleet_optimization()
    print("Optimization complete.")
    print(summary)
