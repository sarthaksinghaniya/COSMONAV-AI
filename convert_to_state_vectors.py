#!/usr/bin/env python3
"""
Orbital Elements to State Vectors Converter
Using SGP4 Propagation Model
"""
import json
import numpy as np
from datetime import datetime, timedelta
import math
import subprocess
import sys

# Install SGP4 if needed
try:
    from sgp4.api import Satrec, jday
    from sgp4.conveniences import jday_datetime
    SGP4_AVAILABLE = True
except ImportError:
    print("SGP4 library not available. Installing...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "sgp4"])
        print("SGP4 installed successfully")
        # Import after installation
        from sgp4.api import Satrec, jday
        from sgp4.conveniences import jday_datetime
        SGP4_AVAILABLE = True
    except subprocess.CalledProcessError:
        print("Failed to install SGP4")
        SGP4_AVAILABLE = False

def create_tle_from_elements(sat_data):
    """Create TLE format strings from orbital elements"""
    try:
        # Extract data
        name = sat_data['name'][:24]  # TLE name limit
        norad_id = sat_data['norad_id']
        epoch_str = sat_data['epoch']
        inclination = sat_data['inclination']
        eccentricity = sat_data['eccentricity']
        raan = sat_data['raan']
        arg_perigee = sat_data['arg_perigee']
        mean_anomaly = sat_data['mean_anomaly']
        mean_motion = sat_data['mean_motion']
        bstar = sat_data['bstar']

        # Parse epoch
        epoch_dt = datetime.fromisoformat(epoch_str.replace('Z', '+00:00'))
        year = epoch_dt.year
        day_of_year = epoch_dt.timetuple().tm_yday + epoch_dt.hour/24 + epoch_dt.minute/1440 + epoch_dt.second/86400

        # Format eccentricity for TLE (remove decimal point)
        ecc_str = f"{eccentricity:.7f}"[2:]  # Remove '0.' and take next 7 digits

        # Create TLE line 1 (simplified)
        line1 = f"1 {norad_id:05d}U {year%100:02d}{day_of_year:012.8f}  .00000000  00000-0  {bstar:>8.4e} 0  999"

        # Create TLE line 2
        line2 = f"2 {norad_id:05d} {inclination:8.4f} {raan:8.4f} {ecc_str:7s} {arg_perigee:8.4f} {mean_anomaly:8.4f} {mean_motion:11.8f}"

        return name, line1, line2

    except Exception as e:
        print(f"Error creating TLE for {sat_data.get('name', 'Unknown')}: {e}")
        return None, None, None

def propagate_satellite(tle_name, tle_line1, tle_line2, target_time=None):
    """Propagate satellite using SGP4 and return position/velocity"""
    try:
        # Create satellite object
        satellite = Satrec.twoline2rv(tle_line1, tle_line2)

        # Use current time if not specified
        if target_time is None:
            target_time = datetime.now()

        # Convert to Julian date
        jd, fr = jday_datetime(target_time)

        # Propagate
        error_code, position, velocity = satellite.sgp4(jd, fr)

        if error_code != 0:
            if processed_count < 5:  # Show first few errors
                print(f"  SGP4 error {error_code} for {tle_name} (jd={jd:.2f}, fr={fr:.6f})")
            return None, None

        # Convert from km and km/s to desired units (already in km, km/s)
        position_km = [float(position[0]), float(position[1]), float(position[2])]
        velocity_kms = [float(velocity[0]), float(velocity[1]), float(velocity[2])]

        return position_km, velocity_kms

    except Exception as e:
        print(f"  Exception in propagation for {tle_name}: {e}")
        return None, None

def validate_state_vector(position, velocity):
    """Validate position and velocity vectors"""
    if position is None or velocity is None:
        return False

    # Check for NaN or zero position
    if any(math.isnan(p) or p == 0 for p in position):
        return False

    # Check position magnitude (should be ~6371-10000 km for LEO)
    pos_magnitude = math.sqrt(sum(p**2 for p in position))
    if pos_magnitude < 6000 or pos_magnitude > 15000:  # Relaxed range
        return False

    # Check velocity magnitude (should be ~6-10 km/s for LEO, but allow wider range)
    velocity_magnitude = math.sqrt(sum(v**2 for v in velocity))
    if velocity_magnitude < 3.0 or velocity_magnitude > 15.0:  # Relaxed range
        return False

    return True

def test_sgp4():
    """Test SGP4 with a known good TLE"""
    print("Testing SGP4 with known TLE...")

    # ISS TLE (example)
    tle_line1 = "1 25544U 98067A   24001.00000000  .00000000  00000-0  00000-0 0  9999"
    tle_line2 = "2 25544  51.6400 000.0000 0001000 000.0000 000.0000 15.50000000 00000"

    try:
        satellite = Satrec.twoline2rv(tle_line1, tle_line2)
        jd, fr = jday_datetime(datetime.now())
        error_code, position, velocity = satellite.sgp4(jd, fr)

        if error_code == 0:
            print(f"  Test successful: pos={position}, vel={velocity}")
            return True
        else:
            print(f"  Test failed with error code: {error_code}")
            return False
    except Exception as e:
        print(f"  Test exception: {e}")
        return False

def main():
    print("=" * 70)
    print("ORBITAL ELEMENTS TO STATE VECTORS CONVERTER")
    print("=" * 70)

    # Check SGP4 availability
    if not SGP4_AVAILABLE:
        print("Cannot proceed without SGP4 library")
        return False

    # Test SGP4
    if not test_sgp4():
        print("SGP4 test failed - aborting")
        return False

    # Load dataset
    print("\n[STEP 1] Loading Dataset...")
    try:
        with open('dataset/clean_satellites.json', 'r') as f:
            satellites = json.load(f)
        print(f"  Loaded {len(satellites)} satellite records")
    except Exception as e:
        print(f"Error loading dataset: {e}")
        return False

    # Step 2: Convert to state vectors
    print("\n[STEP 2] Converting to State Vectors...")
    state_vectors = []
    processed_count = 0
    skipped_count = 0
    target_limit = 300  # Aim for middle of 200-400 range

    current_time = datetime.now()

    for i, sat in enumerate(satellites[:target_limit]):  # Limit processing
        if i % 50 == 0:
            print(f"  Processing satellite {i+1}/{min(len(satellites), target_limit)}...")

        # Validate required fields
        required_fields = ['name', 'norad_id', 'epoch', 'inclination', 'eccentricity',
                          'raan', 'arg_perigee', 'mean_anomaly', 'mean_motion', 'bstar']
        if not all(field in sat for field in required_fields):
            print(f"  Skipping {sat.get('name', 'Unknown')} - missing required fields")
            skipped_count += 1
            continue

        # Create TLE
        tle_name, tle_line1, tle_line2 = create_tle_from_elements(sat)
        if tle_name is None:
            skipped_count += 1
            continue

        # Debug: print first few TLEs
        if i < 3:
            print(f"  Sample TLE for {sat['name']}:")
            print(f"    {tle_line1}")
            print(f"    {tle_line2}")

        # Propagate to get state vectors
        position, velocity = propagate_satellite(tle_name, tle_line1, tle_line2, current_time)
        if position is None or velocity is None:
            if i < 10:  # Only show first few errors
                print(f"  Propagation failed for {sat['name']}")
            skipped_count += 1
            continue

        # Validate state vectors
        if not validate_state_vector(position, velocity):
            if processed_count < 5:  # Show first few validation failures
                pos_mag = math.sqrt(sum(p**2 for p in position)) if position else 0
                vel_mag = math.sqrt(sum(v**2 for v in velocity)) if velocity else 0
                print(f"  Validation failed for {sat['name']}: pos_mag={pos_mag:.1f}, vel_mag={vel_mag:.3f}")
                print(f"    Position: {position}")
                print(f"    Velocity: {velocity}")
            skipped_count += 1
            continue

        # Create output object
        state_vector = {
            "name": sat['name'],
            "norad_id": sat['norad_id'],
            "position": [round(p, 3) for p in position],  # Round to 3 decimal places
            "velocity": [round(v, 6) for v in velocity],  # Round to 6 decimal places
            "source": sat.get('source', 'real'),
            "timestamp": current_time.isoformat()
        }

        state_vectors.append(state_vector)
        processed_count += 1

    print(f"  Successfully processed: {processed_count}")
    print(f"  Skipped/invalid: {skipped_count}")

    # Step 3: Final validation
    print("\n[STEP 3] Final Validation...")

    # Check for duplicates
    norad_ids = [sv['norad_id'] for sv in state_vectors]
    duplicates = len(norad_ids) - len(set(norad_ids))
    print(f"  Duplicate NORAD IDs: {duplicates}")

    # Check data validity
    invalid = 0
    for sv in state_vectors:
        if not validate_state_vector(sv['position'], sv['velocity']):
            invalid += 1
    print(f"  Invalid state vectors: {invalid}")

    print(f"  Final dataset size: {len(state_vectors)}")

    if duplicates > 0 or invalid > 0:
        print("\n  [WARN] Validation issues detected!")
    else:
        print("\n  [OK] All validations passed!")

    # Step 4: Save output
    print("\n[STEP 4] Saving State Vectors...")
    output_file = 'dataset/state_vectors.json'
    try:
        with open(output_file, 'w') as f:
            json.dump(state_vectors, f, indent=2)
        print(f"  [OK] Saved to: {output_file}")
        print(f"  File size: {len(state_vectors)} objects")
    except Exception as e:
        print(f"Error saving file: {e}")
        return False

    # Step 5: Summary
    print(f"\n{'=' * 70}")
    print("CONVERSION SUMMARY")
    print(f"{'=' * 70}")
    print(f"Input satellites: {len(satellites)}")
    print(f"Target limit: {target_limit}")
    print(f"Successfully processed: {processed_count}")
    print(f"Skipped/invalid: {skipped_count}")
    print(f"Final dataset size: {len(state_vectors)}")
    print(f"Processing success rate: {processed_count/max(1, processed_count + skipped_count)*100:.1f}%")
    print(f"\nOutput file: {output_file}")
    print(f"Coordinate system: ECI (Earth-Centered Inertial)")
    print(f"Units: Position (km), Velocity (km/s)")
    print(f"Timestamp: {current_time.isoformat()}")
    print("=" * 70)

    return True

if __name__ == "__main__":
    main()
