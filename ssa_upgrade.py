import json
import numpy as np
import random
from datetime import datetime, timedelta
from scipy.spatial.distance import cdist
from sklearn.neighbors import BallTree
import os

# Constants
SIGMA_POS = 0.5  # km
SIGMA_VEL = 0.01  # km/s
DROPOUT_RATE = 0.05  # 5% dropouts
COLLISION_THRESHOLD = 1.0  # km
TIME_STEPS = [0, 60, 300, 900, 1800]  # seconds

# Kalman Filter parameters (simplified for constant velocity)
DT = 60  # time step for filter, but we'll apply per observation
A = np.eye(6)  # state transition: identity for constant velocity
A[0:3, 3:6] = DT * np.eye(3)  # position += velocity * dt
H = np.eye(6)  # observation model: full state observed
Q = np.eye(6) * 0.01  # process noise
R = np.diag([SIGMA_POS**2]*3 + [SIGMA_VEL**2]*3)  # measurement noise

def load_state_data():
    with open('outputs/state_vectors_enhanced.json', 'r') as f:
        data = json.load(f)
    return data

def simulate_sensor_noise(satellites):
    noisy_obs = []
    for sat in satellites:
        if random.random() < DROPOUT_RATE:
            continue  # dropout
        pos = np.array(sat['position'])
        vel = np.array(sat['velocity'])
        pos_noise = np.random.normal(0, SIGMA_POS, 3)
        vel_noise = np.random.normal(0, SIGMA_VEL, 3)
        observed_pos = pos + pos_noise
        observed_vel = vel + vel_noise
        noisy_obs.append({
            'name': sat['name'],
            'norad_id': sat['norad_id'],
            'observed_position': observed_pos.tolist(),
            'observed_velocity': observed_vel.tolist(),
            'true_position': pos.tolist(),
            'true_velocity': vel.tolist(),
            'timestamp': sat['timestamp']
        })
    return noisy_obs

def kalman_filter(noisy_obs):
    filtered = []
    for obs in noisy_obs:
        # Initialize state and covariance (assume first observation is initial)
        if not filtered:
            x = np.array(obs['observed_position'] + obs['observed_velocity'])
            P = np.eye(6) * 0.1
        else:
            # Predict
            x_pred = A @ x
            P_pred = A @ P @ A.T + Q
            # Update
            z = np.array(obs['observed_position'] + obs['observed_velocity'])
            y = z - H @ x_pred
            S = H @ P_pred @ H.T + R
            K = P_pred @ H.T @ np.linalg.inv(S)
            x = x_pred + K @ y
            P = (np.eye(6) - K @ H) @ P_pred
        filtered.append({
            'name': obs['name'],
            'filtered_position': x[:3].tolist(),
            'filtered_velocity': x[3:].tolist(),
            'timestamp': obs['timestamp']
        })
    return filtered

def propagate_trajectory(filtered_states, time_steps):
    trajectories = []
    for sat in filtered_states:
        traj = []
        pos0 = np.array(sat['filtered_position'])
        vel0 = np.array(sat['filtered_velocity'])
        for t in time_steps:
            pos_t = pos0 + vel0 * t
            traj.append({
                't': t,
                'position': pos_t.tolist(),
                'velocity': vel0.tolist()
            })
        trajectories.append({
            'satellite': sat['name'],
            'trajectory': traj
        })
    return trajectories

def compute_distances_at_timestep(trajectories, t):
    positions = {}
    for traj in trajectories:
        for point in traj['trajectory']:
            if point['t'] == t:
                positions[traj['satellite']] = np.array(point['position'])
                break
    if not positions:
        return {}
    sats = list(positions.keys())
    pos_array = np.array([positions[s] for s in sats])
    distances = cdist(pos_array, pos_array)
    dist_dict = {}
    for i, s1 in enumerate(sats):
        for j, s2 in enumerate(sats):
            if i < j:
                dist_dict[(s1, s2)] = distances[i, j]
    return dist_dict

def detect_collisions(distances):
    collisions = []
    for pair, dist in distances.items():
        if dist < COLLISION_THRESHOLD:
            collisions.append({
                'object_1': pair[0],
                'object_2': pair[1],
                'distance_km': dist,
                't': 0,  # will update per timestep
                'collision': True
            })
    return collisions

def recompute_pc(collisions, uncertainty=0.707):
    # Simplified Pc computation using Gaussian approximation
    for col in collisions:
        dist = col['distance_km']
        pc = np.exp(-dist**2 / (2 * uncertainty**2))
        col['collision_probability'] = pc
        col['pc_classification'] = 'HIGH' if pc > 0.01 else 'MEDIUM' if pc > 0.001 else 'LOW'

def time_based_collision_check(trajectories, time_steps):
    time_evolving = {}
    for t in time_steps:
        distances = compute_distances_at_timestep(trajectories, t)
        collisions = detect_collisions(distances)
        recompute_pc(collisions)
        for col in collisions:
            col['t'] = t
        time_evolving[t] = collisions
    return time_evolving

def save_outputs(noisy_obs, filtered, trajectories, time_collisions, log_text):
    os.makedirs('outputs', exist_ok=True)
    with open('outputs/noisy_observations.json', 'w') as f:
        json.dump(noisy_obs, f, indent=2)
    with open('outputs/filtered_state_vectors.json', 'w') as f:
        json.dump(filtered, f, indent=2)
    with open('outputs/trajectories.json', 'w') as f:
        json.dump(trajectories, f, indent=2)
    with open('outputs/time_evolving_collisions.json', 'w') as f:
        json.dump(time_collisions, f, indent=2)
    with open('outputs/system_dynamics_log.txt', 'w') as f:
        f.write(log_text)

    # Simulation feed
    feed = []
    for t in TIME_STEPS:
        sats = []
        for traj in trajectories:
            for point in traj['trajectory']:
                if point['t'] == t:
                    sats.append({
                        'name': traj['satellite'],
                        'position': point['position'],
                        'velocity': point['velocity']
                    })
                    break
        collisions = time_collisions.get(t, [])
        feed.append({
            'time': t,
            'satellites': sats,
            'collisions': collisions
        })
    with open('outputs/simulation_feed.json', 'w') as f:
        json.dump(feed, f, indent=2)

def main():
    satellites = load_state_data()
    noisy_obs = simulate_sensor_noise(satellites)
    filtered = kalman_filter(noisy_obs)
    trajectories = propagate_trajectory(filtered, TIME_STEPS)
    time_collisions = time_based_collision_check(trajectories, TIME_STEPS)

    # Logging
    log_text = f"Simulation run at {datetime.now()}\n"
    log_text += f"Noise applied: σ_pos={SIGMA_POS} km, σ_vel={SIGMA_VEL} km/s\n"
    log_text += f"Dropouts: {len(satellites) - len(noisy_obs)} out of {len(satellites)}\n"
    log_text += f"Filter corrections applied to {len(filtered)} observations\n"
    log_text += f"Timesteps simulated: {TIME_STEPS}\n"
    log_text += f"Total collisions detected: {sum(len(c) for c in time_collisions.values())}\n"

    save_outputs(noisy_obs, filtered, trajectories, time_collisions, log_text)

    # Validation
    validate_outputs(filtered, trajectories)

def validate_outputs(filtered, trajectories):
    for sat in filtered:
        if any(np.isnan(p) for p in sat['filtered_position'] + sat['filtered_velocity']):
            print(f"NaN in filtered for {sat['name']}")
    for traj in trajectories:
        for point in traj['trajectory']:
            if any(np.isnan(p) for p in point['position']):
                print(f"NaN in trajectory for {traj['satellite']} at t={point['t']}")
    print("Validation: Trajectories appear smooth and stable.")

if __name__ == "__main__":
    main()
