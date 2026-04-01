# Uncertainty Modeling and Probability of Collision Analysis
Generated: 2026-04-01 19:50:20

## Executive Summary

### System Configuration
- Uncertainty Model: Diagonal covariance with sigma_x = sigma_y = sigma_z = 0.5 km (LEO)
- Conjunction Radius: 2.0 km
- Monte Carlo Samples: 1000 per conjunction

### Key Statistics
- **Total Alerts Analyzed**: 60
- **Highest Pc**: 1.3727e-01
- **Average Pc**: 4.6423e-03
- **Median Pc**: 0.0000e+00
- **Std Dev Pc**: 2.4630e-02
- **Minimum Pc**: 0.0000e+00

### Risk Distribution
- **HIGH RISK** (Pc > 1e-3): 4 events
- **MEDIUM RISK** (1e-5 < Pc <= 1e-3): 0 events
- **LOW RISK** (Pc <= 1e-5): 56 events

## Methodology

### Step 1: Uncertainty Model
Each satellite has a 3x3 covariance matrix:
```
C = diag([sigma_x^2, sigma_y^2, sigma_z^2]) = diag([0.25, 0.25, 0.25]) km^2
```

### Step 2: Combined Uncertainty
For each conjunction pair:
```
C_combined = C_obj1 + C_obj2
```

### Step 3: Probability of Collision
Three complementary methods:

1. **Gaussian Approximation**: Pc ~ exp(-d^2 / (2*sigma^2))
2. **Tail Probability**: P(encounter) using error function
3. **Volume-Based**: Probability within conjunction sphere

Final Pc is averaged across methods, with Monte Carlo validation.

### Step 4-6: Classification and Decisions
- HIGH (Pc > 1e-3): EXECUTE maneuver
- MEDIUM (Pc > 1e-5): MONITOR closely
- LOW (Pc <= 1e-5): ROUTINE monitoring

## Top 10 Highest Risk Conjunctions


### 1. 0 STARLINK-30161 <-> 0 STARLINK-1300
- **Collision Probability**: 1.3727e-01
- **Risk Classification**: HIGH
- **Decision**: EXECUTE_MANEUVER
- **Miss Distance**: 2.80 km
- **Time to CA**: 2725.9 seconds
- **Relative Velocity**: 0.472 km/s
- **Uncertainty (sigma_eff)**: 0.707 km
- **Pc Breakdown**:
  - Gaussian: 4.9787e-02
  - Tail Probability: 7.1529e-03
  - Volume-Based: 1.1236e-03
  - Monte Carlo: 4.9100e-01

### 2. 0 STARLINK-1300 <-> 0 STARLINK-30161
- **Collision Probability**: 1.3727e-01
- **Risk Classification**: HIGH
- **Decision**: EXECUTE_MANEUVER
- **Miss Distance**: 2.80 km
- **Time to CA**: 2725.9 seconds
- **Relative Velocity**: 0.472 km/s
- **Uncertainty (sigma_eff)**: 0.707 km
- **Pc Breakdown**:
  - Gaussian: 4.9787e-02
  - Tail Probability: 7.1529e-03
  - Volume-Based: 1.1236e-03
  - Monte Carlo: 4.9100e-01

### 3. 0 STARLINK-35071 <-> 0 STARLINK-32400
- **Collision Probability**: 2.0017e-03
- **Risk Classification**: HIGH
- **Decision**: EXECUTE_MANEUVER
- **Miss Distance**: 4.13 km
- **Time to CA**: 174.0 seconds
- **Relative Velocity**: 10.988 km/s
- **Uncertainty (sigma_eff)**: 0.707 km
- **Pc Breakdown**:
  - Gaussian: 6.1442e-06
  - Tail Probability: 4.8168e-07
  - Volume-Based: 1.3866e-07
  - Monte Carlo: 8.0000e-03

### 4. 0 STARLINK-32400 <-> 0 STARLINK-35071
- **Collision Probability**: 2.0017e-03
- **Risk Classification**: HIGH
- **Decision**: EXECUTE_MANEUVER
- **Miss Distance**: 4.13 km
- **Time to CA**: 174.0 seconds
- **Relative Velocity**: 10.988 km/s
- **Uncertainty (sigma_eff)**: 0.707 km
- **Pc Breakdown**:
  - Gaussian: 6.1442e-06
  - Tail Probability: 4.8168e-07
  - Volume-Based: 1.3866e-07
  - Monte Carlo: 8.0000e-03

### 5. 0 STARLINK-34138 <-> 0 STARLINK-5872
- **Collision Probability**: 5.0555e-13
- **Risk Classification**: LOW
- **Decision**: ROUTINE
- **Miss Distance**: 6.58 km
- **Time to CA**: 221.9 seconds
- **Relative Velocity**: 7.775 km/s
- **Uncertainty (sigma_eff)**: 0.707 km
- **Pc Breakdown**:
  - Gaussian: 1.8795e-12
  - Tail Probability: 1.0024e-13
  - Volume-Based: 4.2416e-14
  - Monte Carlo: 0.0000e+00

### 6. 0 STARLINK-5872 <-> 0 STARLINK-34138
- **Collision Probability**: 5.0555e-13
- **Risk Classification**: LOW
- **Decision**: ROUTINE
- **Miss Distance**: 6.58 km
- **Time to CA**: 221.9 seconds
- **Relative Velocity**: 7.775 km/s
- **Uncertainty (sigma_eff)**: 0.707 km
- **Pc Breakdown**:
  - Gaussian: 1.8795e-12
  - Tail Probability: 1.0024e-13
  - Volume-Based: 4.2416e-14
  - Monte Carlo: 0.0000e+00

### 7. 0 STARLINK-6320 <-> 0 STARLINK-32163
- **Collision Probability**: 3.2746e-48
- **Risk Classification**: LOW
- **Decision**: ROUTINE
- **Miss Distance**: 11.78 km
- **Time to CA**: 230.3 seconds
- **Relative Velocity**: 4.291 km/s
- **Uncertainty (sigma_eff)**: 0.707 km
- **Pc Breakdown**:
  - Gaussian: 1.2479e-47
  - Tail Probability: 3.3720e-49
  - Volume-Based: 2.8163e-49
  - Monte Carlo: 0.0000e+00

### 8. 0 STARLINK-32163 <-> 0 STARLINK-6320
- **Collision Probability**: 3.2746e-48
- **Risk Classification**: LOW
- **Decision**: ROUTINE
- **Miss Distance**: 11.78 km
- **Time to CA**: 230.3 seconds
- **Relative Velocity**: 4.291 km/s
- **Uncertainty (sigma_eff)**: 0.707 km
- **Pc Breakdown**:
  - Gaussian: 1.2479e-47
  - Tail Probability: 3.3720e-49
  - Volume-Based: 2.8163e-49
  - Monte Carlo: 0.0000e+00

### 9. 0 STARLINK-35986 <-> 0 STARLINK-36054
- **Collision Probability**: 3.7677e-65
- **Risk Classification**: LOW
- **Decision**: ROUTINE
- **Miss Distance**: 12.38 km
- **Time to CA**: 383.7 seconds
- **Relative Velocity**: 9.546 km/s
- **Uncertainty (sigma_eff)**: 0.707 km
- **Pc Breakdown**:
  - Gaussian: 1.4412e-64
  - Tail Probability: 3.3418e-66
  - Volume-Based: 3.2523e-66
  - Monte Carlo: 0.0000e+00

### 10. 0 STARLINK-36054 <-> 0 STARLINK-35986
- **Collision Probability**: 3.7677e-65
- **Risk Classification**: LOW
- **Decision**: ROUTINE
- **Miss Distance**: 12.38 km
- **Time to CA**: 383.7 seconds
- **Relative Velocity**: 9.546 km/s
- **Uncertainty (sigma_eff)**: 0.707 km
- **Pc Breakdown**:
  - Gaussian: 1.4412e-64
  - Tail Probability: 3.3418e-66
  - Volume-Based: 3.2523e-66
  - Monte Carlo: 0.0000e+00


## Data Files Generated

1. **outputs/collision_alerts_enhanced.json** - Enhanced alerts with Pc and uncertainty
2. **outputs/plots/probability_distribution.png** - Visualization of Pc distribution
3. **outputs/uncertainty_summary.json** - Summary statistics
4. **outputs/uncertainty_analysis_report.md** - This report

## Recommendations

1. **High-Risk Conjunctions**: Execute collision avoidance maneuvers immediately
2. **Medium-Risk:** Increase tracking frequency to 1-minute intervals
3. **Low-Risk:** Continue routine 6-hour schedule monitoring

Monitor conjunction geometry over next 24 hours as Pc can evolve significantly.
