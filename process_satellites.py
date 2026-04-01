#!/usr/bin/env python3
"""
Satellite Data Cleaning and Processing Pipeline
"""
import json
import os
from datetime import datetime
from pathlib import Path
import random
import numpy as np
from collections import defaultdict

# Configuration
RAW_DATA_DIR = r"c:\Users\LOQ\Desktop\ISRO_PROJECT\Raw-Data"
OUTPUT_DIR = r"c:\Users\LOQ\Desktop\ISRO_PROJECT\dataset"
LEO_THRESHOLD = 11  # Mean motion > 11 indicates LEO
TARGET_SIZE_MIN = 300
TARGET_SIZE_MAX = 500

def parse_tle_line(line0, line1, line2):
    """Parse TLE format and extract orbital parameters"""
    try:
        # Extract from line 1
        norad_id = int(line1[2:7].strip())
        epoch_year = int(line1[18:20])
        epoch_day = float(line1[20:32])
        
        # Convert epoch to full year
        if epoch_year < 57:
            full_year = 2000 + epoch_year
        else:
            full_year = 1900 + epoch_year
        
        # Convert day of year to datetime
        epoch_date = datetime(full_year, 1, 1)
        from datetime import timedelta
        epoch_date = epoch_date + timedelta(days=epoch_day - 1)
        
        # Parse BSTAR (special format: ±abcde-f means ±0.abcde × 10^(-f))
        try:
            bstar_str = line1[53:61].strip()
            if bstar_str:
                # Handle the special TLE BSTAR format
                sign = 1 if bstar_str[0] != '-' else -1
                bstar_num = float('0.' + bstar_str[1:6])
                bstar_exp = int(bstar_str[6:8])
                bstar = sign * bstar_num * (10 ** (-bstar_exp))
            else:
                bstar = 0
        except:
            bstar = 0
        
        # Extract from line 2
        inclination = float(line2[8:16])
        raan = float(line2[17:25])
        eccentricity = float('0.' + line2[26:33])
        arg_perigee = float(line2[34:42])
        mean_anomaly = float(line2[43:51])
        mean_motion = float(line2[52:63])
        
        return {
            'name': line0.strip(),
            'norad_id': norad_id,
            'epoch': epoch_date.isoformat(),
            'inclination': inclination,
            'eccentricity': eccentricity,
            'raan': raan,
            'arg_perigee': arg_perigee,
            'mean_anomaly': mean_anomaly,
            'mean_motion': mean_motion,
            'bstar': bstar,
            'source': 'real'
        }
    except Exception as e:
        return None

def read_tle_file(filepath):
    """Read and parse TLE format files"""
    objects = []
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        i = 0
        while i < len(lines):
            if i + 2 < len(lines):
                line0 = lines[i].strip()
                line1 = lines[i+1].strip()
                line2 = lines[i+2].strip()
                
                # Check if lines 1 and 2 are valid TLE lines
                if line1.startswith('1 ') and line2.startswith('2 '):
                    obj = parse_tle_line(line0, line1, line2)
                    if obj:
                        objects.append(obj)
                    i += 3
                else:
                    i += 1
            else:
                break
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    
    return objects

def read_json_file(filepath):
    """Read and standardize JSON satellite data"""
    objects = []
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Ensure data is a list
        if not isinstance(data, list):
            data = [data]
        
        for item in data:
            try:
                # Map JSON fields to standard schema
                obj = {
                    'name': item.get('OBJECT_NAME', '').strip(),
                    'norad_id': int(item.get('NORAD_CAT_ID', 0)),
                    'epoch': item.get('EPOCH', ''),
                    'inclination': float(item.get('INCLINATION', 0)),
                    'eccentricity': float(item.get('ECCENTRICITY', 0)),
                    'raan': float(item.get('RA_OF_ASC_NODE', 0)),
                    'arg_perigee': float(item.get('ARG_OF_PERICENTER', 0)),
                    'mean_anomaly': float(item.get('MEAN_ANOMALY', 0)),
                    'mean_motion': float(item.get('MEAN_MOTION', 0)),
                    'bstar': float(item.get('BSTAR', 0)),
                    'source': 'real'
                }
                
                # Validate required fields
                if obj['norad_id'] > 0 and obj['name'] and obj['epoch']:
                    objects.append(obj)
            except (ValueError, TypeError):
                continue
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    
    return objects

def clean_and_deduplicate(all_objects):
    """Remove duplicates, invalid records, and keep latest epoch"""
    dedup = {}
    removed_count = 0
    
    for obj in all_objects:
        norad_id = obj['norad_id']
        
        if norad_id <= 0:
            removed_count += 1
            continue
        
        # Validate critical parameters
        if (obj['inclination'] < -90 or obj['inclination'] > 90 or
            obj['eccentricity'] < 0 or obj['eccentricity'] > 1 or
            obj['mean_motion'] <= 0):
            removed_count += 1
            continue
        
        # Keep latest epoch if duplicate
        if norad_id not in dedup or obj['epoch'] > dedup[norad_id]['epoch']:
            dedup[norad_id] = obj
    
    print(f"\nCleaning: Removed {removed_count} invalid records")
    print(f"Deduplicated to {len(dedup)} unique objects")
    
    return list(dedup.values())

def filter_leo_objects(objects):
    """Keep only LEO objects (mean_motion > 11)"""
    leo_objects = [obj for obj in objects if obj['mean_motion'] > LEO_THRESHOLD]
    removed = len(objects) - len(leo_objects)
    print(f"Filtering: Removed {removed} non-LEO objects")
    return leo_objects

def downsample_dataset(objects, max_size):
    """Downsample dataset to a maximum size while preserving diversity"""
    if len(objects) <= max_size:
        return objects
    
    # Sort by inclination to preserve orbital diversity
    sorted_objs = sorted(objects, key=lambda x: x['inclination'])
    
    # Sample evenly across inclination ranges
    sampled = []
    chunk_size = len(sorted_objs) / max_size
    for i in range(max_size):
        idx = int(i * chunk_size)
        if idx < len(sorted_objs):
            sampled.append(sorted_objs[idx])
    
    removed = len(objects) - len(sampled)
    print(f"Downsampling: Removed {removed} objects to reach target size {max_size}")
    return sampled

def generate_synthetic_debris(real_objects, target_total):
    """Generate synthetic debris around real satellites"""
    synthetic = []
    objects_needed = max(0, target_total - len(real_objects))
    
    if objects_needed <= 0:
        return synthetic
    
    # Group by inclination range to cluster debris
    inclination_groups = defaultdict(list)
    for obj in real_objects:
        inc_range = int(obj['inclination'] / 10) * 10
        inclination_groups[inc_range].append(obj)
    
    # Generate synthetic debris
    base_norad = 100000
    for _ in range(objects_needed):
        # Pick a random inclination group
        if inclination_groups:
            inc_range = random.choice(list(inclination_groups.keys()))
            reference_obj = random.choice(inclination_groups[inc_range])
            
            # Create synthetic variant with slight perturbations
            synthetic_obj = {
                'name': f"DEBRIS-{base_norad}",
                'norad_id': base_norad,
                'epoch': reference_obj['epoch'],
                'inclination': reference_obj['inclination'] + np.random.normal(0, 0.5),
                'eccentricity': max(0.0001, reference_obj['eccentricity'] + np.random.normal(0, 0.00005)),
                'raan': (reference_obj['raan'] + np.random.normal(0, 10)) % 360,
                'arg_perigee': (reference_obj['arg_perigee'] + np.random.normal(0, 20)) % 360,
                'mean_anomaly': (reference_obj['mean_anomaly'] + np.random.normal(0, 20)) % 360,
                'mean_motion': reference_obj['mean_motion'] + np.random.normal(0, 0.1),
                'bstar': reference_obj['bstar'] + np.random.normal(0, 0.00001),
                'source': 'synthetic'
            }
            
            # Clamp values to valid ranges
            synthetic_obj['inclination'] = max(-90, min(90, synthetic_obj['inclination']))
            synthetic_obj['eccentricity'] = max(0.0001, min(0.9, synthetic_obj['eccentricity']))
            synthetic_obj['mean_motion'] = max(LEO_THRESHOLD, synthetic_obj['mean_motion'])
            
            synthetic.append(synthetic_obj)
            base_norad += 1
    
    print(f"Generated {len(synthetic)} synthetic debris objects")
    return synthetic

def main():
    print("=" * 70)
    print("SATELLITE DATA PROCESSING PIPELINE")
    print("=" * 70)
    
    # Load all data
    all_objects = []
    
    print("\n[STEP 1] Reading Raw Data Files...")
    for file in os.listdir(RAW_DATA_DIR):
        filepath = os.path.join(RAW_DATA_DIR, file)
        
        if file.endswith('.json'):
            print(f"  Reading {file}...", end=" ")
            data = read_json_file(filepath)
            all_objects.extend(data)
            print(f"[OK] ({len(data)} records)")
        
        elif file.endswith('.txt'):
            print(f"  Reading {file}...", end=" ")
            data = read_tle_file(filepath)
            all_objects.extend(data)
            print(f"[OK] ({len(data)} records)")
        
        elif file.endswith(('.htm', '.html', '.xml')):
            print(f"  Skipping {file} (irrelevant format)")
    
    print(f"\nTotal records loaded: {len(all_objects)}")
    
    # Step 2: Clean and Deduplicate
    print("\n[STEP 2] Cleaning & Deduplicating...")
    cleaned_objects = clean_and_deduplicate(all_objects)
    
    # Step 3: Filter LEO objects
    print("\n[STEP 3] Filtering LEO Objects (mean_motion > {})...".format(LEO_THRESHOLD))
    leo_objects = filter_leo_objects(cleaned_objects)
    
    # Step 3b: Downsample if needed
    print("\n[STEP 3b] Downsampling LEO Objects...")
    target = random.randint(TARGET_SIZE_MIN, TARGET_SIZE_MAX)
    print(f"  Current dataset size: {len(leo_objects)}")
    print(f"  Target dataset size: {target}")
    
    if len(leo_objects) > TARGET_SIZE_MAX:
        # Downsample to max target
        leo_objects = downsample_dataset(leo_objects, TARGET_SIZE_MAX)
    
    # Step 4: Generate Synthetic Debris
    print(f"\n[STEP 4] Generating Synthetic Debris...")
    print(f"  Current dataset size: {len(leo_objects)}")
    print(f"  Target dataset size: {TARGET_SIZE_MIN}-{TARGET_SIZE_MAX}")
    
    target = random.randint(TARGET_SIZE_MIN, TARGET_SIZE_MAX)
    synthetic_debris = generate_synthetic_debris(leo_objects, target)
    
    # Combine real + synthetic
    final_dataset = leo_objects + synthetic_debris
    
    # Step 5: Validation
    print(f"\n[STEP 5] Validation...")
    
    # Check duplicates
    norad_ids = [obj['norad_id'] for obj in final_dataset]
    duplicates = len(norad_ids) - len(set(norad_ids))
    print(f"  Duplicate NORAD IDs: {duplicates}")
    
    # Check data validity
    invalid = 0
    for obj in final_dataset:
        if (obj['inclination'] < -90 or obj['inclination'] > 90 or
            obj['eccentricity'] < 0 or obj['eccentricity'] > 1 or
            obj['mean_motion'] <= 0):
            invalid += 1
    print(f"  Invalid objects: {invalid}")
    
    print(f"  Final dataset size: {len(final_dataset)}")
    print(f"  Real objects: {len(leo_objects)}")
    print(f"  Synthetic objects: {len(synthetic_debris)}")
    
    if duplicates > 0 or invalid > 0:
        print("\n  [WARN] Data validation issues detected!")
    else:
        print("\n  [OK] All validations passed!")
    
    # Step 6: Save Dataset
    print(f"\n[STEP 6] Saving Dataset...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    output_file = os.path.join(OUTPUT_DIR, 'clean_satellites.json')
    with open(output_file, 'w') as f:
        json.dump(final_dataset, f, indent=2)
    
    print(f"  [OK] Saved to: {output_file}")
    
    # Step 7: Summary
    print(f"\n{'=' * 70}")
    print("PROCESSING SUMMARY")
    print(f"{'=' * 70}")
    print(f"Total objects in final dataset: {len(final_dataset)}")
    print(f"Real satellites: {len(leo_objects)}")
    print(f"Synthetic debris: {len(synthetic_debris)}")
    print(f"Source breakdown:")
    real_count = len([o for o in final_dataset if o['source'] == 'real'])
    synthetic_count = len([o for o in final_dataset if o['source'] == 'synthetic'])
    print(f"  - Real: {real_count}")
    print(f"  - Synthetic: {synthetic_count}")
    print(f"\nDataset location: {output_file}")
    print("=" * 70)
    
    return True

if __name__ == "__main__":
    main()
