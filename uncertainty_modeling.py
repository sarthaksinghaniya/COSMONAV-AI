"""
Orbital Uncertainty Modeling and Probability of Collision Analysis
Enhanced conjunction analysis with Gaussian uncertainty model
"""

import json
import numpy as np
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any
import matplotlib.pyplot as plt
from scipy.integrate import quad
from scipy.special import erfc

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UncertaintyModel:
    """Represents position uncertainty as covariance matrix"""
    
    def __init__(self, sigma_x: float = 0.5, sigma_y: float = 0.5, sigma_z: float = 0.5):
        """
        Initialize covariance matrix for LEO objects
        
        Args:
            sigma_x, sigma_y, sigma_z: Standard deviations in km (default 0.5 km)
        """
        self.sigma = np.array([sigma_x, sigma_y, sigma_z])
        self.covariance = np.diag(self.sigma ** 2)
        logger.info(f"Initialized uncertainty model with σ = {self.sigma} km")
    
    def get_covariance(self) -> np.ndarray:
        """Return 3x3 covariance matrix"""
        return self.covariance.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize covariance matrix"""
        return {
            "sigma_km": self.sigma.tolist(),
            "covariance_diagonal": np.diag(self.covariance).tolist(),
            "covariance_matrix": self.covariance.tolist()
        }


class CollisionProbabilityCalculator:
    """Computes probability of collision between satellite pairs"""
    
    def __init__(self, uncertainty_model: UncertaintyModel):
        """
        Initialize Pc calculator
        
        Args:
            uncertainty_model: UncertaintyModel instance
        """
        self.uncertainty = uncertainty_model
    
    def combine_covariance(self, cov1: np.ndarray, cov2: np.ndarray) -> np.ndarray:
        """
        Combine covariance matrices from two objects (Step 2)
        
        C_combined = C1 + C2
        """
        return cov1 + cov2
    
    def compute_pc_gaussian(self, relative_position: np.ndarray, 
                           combined_cov: np.ndarray, 
                           conjunction_radius: float = 2.0) -> float:
        """
        Compute probability of collision using Gaussian model (Step 3)
        
        Pc ≈ exp(-d² / (2σ²))
        
        Args:
            relative_position: 3D relative position at TCA (km)
            combined_cov: Combined covariance matrix
            conjunction_radius: Collision threshold (km)
        
        Returns:
            Pc: Probability of collision [0, 1]
        """
        # Compute miss distance
        d = np.linalg.norm(relative_position)
        
        # Effective uncertainty (trace of covariance / 3)
        sigma_eff = np.sqrt(np.trace(combined_cov) / 3.0)
        
        # Gaussian approximation
        if sigma_eff > 0:
            pc = np.exp(-d**2 / (2 * sigma_eff**2))
        else:
            pc = 0.0
        
        return max(0.0, min(pc, 1.0))  # Clamp to [0, 1]
    
    def compute_pc_tail_probability(self, relative_position: np.ndarray,
                                   combined_cov: np.ndarray,
                                   conjunction_radius: float = 2.0) -> float:
        """
        More realistic Pc using tail probability of Rayleigh distribution
        
        P(encounter) = Φ(-d/σ) where Φ is complementary error function
        """
        d = np.linalg.norm(relative_position)
        sigma_eff = np.sqrt(np.trace(combined_cov) / 3.0)
        
        if sigma_eff > 0:
            # Tail probability of normal distribution
            x = d / (sigma_eff * np.sqrt(2))
            pc = 0.5 * erfc(x)
        else:
            pc = 0.0
        
        return max(0.0, min(pc, 1.0))
    
    def compute_pc_volume_based(self, relative_position: np.ndarray,
                               combined_cov: np.ndarray,
                               conjunction_radius: float = 2.0) -> float:
        """
        Volume-based probability considering collision sphere
        
        Based on combined uncertainty and collision criteria
        """
        d = np.linalg.norm(relative_position)
        sigma_eff = np.sqrt(np.trace(combined_cov) / 3.0)
        
        # Probability within conjunction sphere
        if sigma_eff > 0:
            # Normalized miss distance
            z = d / sigma_eff
            
            # Probability density integrated over collision volume
            # Simplified: gaussian probability at miss distance
            pc = np.exp(-z**2 / 2) / (sigma_eff * np.sqrt(2 * np.pi))
            
            # Scale by conjunction radius
            pc = pc * conjunction_radius**2 / 100.0
        else:
            pc = 0.0
        
        return max(0.0, min(pc, 1.0))
    
    def classify_risk(self, pc: float) -> str:
        """
        Classify collision risk by probability (Step 4)
        
        - HIGH RISK: Pc > 1e-3
        - MEDIUM: Pc > 1e-5
        - LOW: Pc ≤ 1e-5
        """
        if pc > 1e-3:
            return "HIGH"
        elif pc > 1e-5:
            return "MEDIUM"
        else:
            return "LOW"
    
    def classify_decision(self, pc: float) -> str:
        """
        Decision recommendation based on Pc (Step 6)
        
        - EXECUTE: If Pc high → perform maneuver
        - MONITOR: If Pc medium → increase tracking
        - IGNORE: If Pc low → routine monitoring
        """
        if pc > 1e-3:
            return "EXECUTE_MANEUVER"
        elif pc > 1e-5:
            return "MONITOR_CLOSE"
        else:
            return "ROUTINE"


class MonteCarloSimulation:
    """Monte Carlo-based Pc estimation (Step 8 - Bonus)"""
    
    def __init__(self, n_samples: int = 1000, uncertainty_model: UncertaintyModel = None):
        """
        Initialize Monte Carlo simulator
        
        Args:
            n_samples: Number of position samples
            uncertainty_model: UncertaintyModel instance
        """
        self.n_samples = n_samples
        self.uncertainty = uncertainty_model or UncertaintyModel()
    
    def simulate_collision_probability(self, relative_position: np.ndarray,
                                      combined_cov: np.ndarray,
                                      conjunction_radius: float = 2.0) -> Tuple[float, Dict]:
        """
        Estimate Pc by Monte Carlo sampling (1000 possible positions)
        
        Args:
            relative_position: Relative position at TCA
            combined_cov: Combined covariance matrix
            conjunction_radius: Collision threshold
        
        Returns:
            pc_monte_carlo: Empirical collision probability
            stats: Distribution statistics
        """
        np.random.seed(42)
        
        # Sample from multivariate normal distribution
        samples = np.random.multivariate_normal(
            relative_position,
            combined_cov,
            self.n_samples
        )
        
        # Compute distances from origin (TCA point)
        distances = np.linalg.norm(samples, axis=1)
        
        # Count collisions (within sphere)
        collisions = np.sum(distances <= conjunction_radius)
        
        # Empirical Pc
        pc_mc = collisions / self.n_samples
        
        # Distribution statistics
        stats = {
            "n_samples": self.n_samples,
            "collisions": int(collisions),
            "mean_distance_km": float(np.mean(distances)),
            "std_distance_km": float(np.std(distances)),
            "min_distance_km": float(np.min(distances)),
            "max_distance_km": float(np.max(distances)),
            "percentile_5": float(np.percentile(distances, 5)),
            "percentile_50": float(np.percentile(distances, 50)),
            "percentile_95": float(np.percentile(distances, 95))
        }
        
        return pc_mc, stats


class UncertaintyProcessor:
    """Main processor for uncertainty analysis on datasets"""
    
    def __init__(self, state_vectors_file: Path, collision_alerts_file: Path):
        """Initialize processor with data files"""
        self.state_vectors_file = state_vectors_file
        self.collision_alerts_file = collision_alerts_file
        self.uncertainty = UncertaintyModel()
        self.pc_calc = CollisionProbabilityCalculator(self.uncertainty)
        self.mc_sim = MonteCarloSimulation(n_samples=1000, uncertainty_model=self.uncertainty)
        
        # Load data
        self.state_vectors = self._load_json(state_vectors_file)
        self.collision_alerts = self._load_json(collision_alerts_file)
        
        logger.info(f"Loaded {len(self.state_vectors)} state vectors")
        logger.info(f"Loaded {len(self.collision_alerts)} collision alerts")
    
    def _load_json(self, filepath: Path) -> List[Dict]:
        """Load JSON file"""
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def _save_json(self, filepath: Path, data: List[Dict]):
        """Save JSON file with pretty formatting"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {len(data)} records to {filepath}")
    
    def add_uncertainty_to_vectors(self) -> List[Dict]:
        """
        Step 1: Add covariance matrices to state vectors
        """
        enhanced_vectors = []
        
        for sv in self.state_vectors:
            enhanced = sv.copy()
            
            # Add uncertainty model
            enhanced["uncertainty"] = self.uncertainty.to_dict()
            enhanced["covariance_matrix"] = self.uncertainty.get_covariance().tolist()
            
            enhanced_vectors.append(enhanced)
        
        logger.info(f"Added uncertainty model to {len(enhanced_vectors)} vectors")
        return enhanced_vectors
    
    def process_collision_alerts(self) -> Tuple[List[Dict], Dict]:
        """
        Steps 2-4: Process collision alerts with uncertainty and Pc
        
        Returns:
            enhanced_alerts: Alerts with Pc and classification
            summary_stats: Summary statistics
        """
        enhanced_alerts = []
        pc_values = []
        
        for alert in self.collision_alerts:
            enhanced = alert.copy()
            
            # Step 2: Combined covariance
            cov1 = self.uncertainty.get_covariance()
            cov2 = self.uncertainty.get_covariance()
            combined_cov = self.pc_calc.combine_covariance(cov1, cov2)
            
            # Relative position (using miss distance)
            relative_position = np.array([0, 0, 0])  # At TCA, position is minimum
            # Use distance_km as miss distance indicator
            miss_distance = alert.get("distance_km", 1.0)
            
            # Add some realistic position uncertainty
            relative_position[0] = miss_distance / np.sqrt(3)
            relative_position[1] = miss_distance / np.sqrt(3)
            relative_position[2] = miss_distance / np.sqrt(3)
            
            # Step 3: Compute Pc using three methods
            pc_gaussian = self.pc_calc.compute_pc_gaussian(
                relative_position, combined_cov
            )
            pc_tail = self.pc_calc.compute_pc_tail_probability(
                relative_position, combined_cov
            )
            pc_volume = self.pc_calc.compute_pc_volume_based(
                relative_position, combined_cov
            )
            
            # Step 8 Bonus: Monte Carlo estimation
            pc_monte_carlo, mc_stats = self.mc_sim.simulate_collision_probability(
                relative_position, combined_cov
            )
            
            # Use averaged Pc (can be customized)
            pc_average = np.mean([pc_gaussian, pc_tail, pc_volume, pc_monte_carlo])
            
            # Uncertainty metrics
            uncertainty_km = np.sqrt(np.trace(combined_cov) / 3.0)
            
            # Step 4: Classification
            risk_level = self.pc_calc.classify_risk(pc_average)
            decision = self.pc_calc.classify_decision(pc_average)
            
            # Add to enhanced alert
            enhanced["collision_probability"] = float(pc_average)
            enhanced["uncertainty_km"] = float(uncertainty_km)
            enhanced["pc_methods"] = {
                "gaussian": float(pc_gaussian),
                "tail_probability": float(pc_tail),
                "volume_based": float(pc_volume),
                "monte_carlo": float(pc_monte_carlo)
            }
            enhanced["monte_carlo_stats"] = mc_stats
            enhanced["pc_classification"] = risk_level  # Step 4
            enhanced["decision_recommendation"] = decision  # Step 6
            enhanced["combined_covariance_diag"] = np.diag(combined_cov).tolist()
            
            enhanced_alerts.append(enhanced)
            pc_values.append(pc_average)
        
        # Compute summary statistics
        pc_values = np.array(pc_values)
        summary_stats = {
            "total_alerts": len(enhanced_alerts),
            "highest_pc": float(np.max(pc_values)),
            "average_pc": float(np.mean(pc_values)),
            "median_pc": float(np.median(pc_values)),
            "std_pc": float(np.std(pc_values)),
            "min_pc": float(np.min(pc_values)),
            "distribution": {
                "high_risk_count": int(np.sum(pc_values > 1e-3)),
                "medium_risk_count": int(np.sum((pc_values > 1e-5) & (pc_values <= 1e-3))),
                "low_risk_count": int(np.sum(pc_values <= 1e-5))
            }
        }
        
        logger.info(f"Processed {len(enhanced_alerts)} collision alerts")
        logger.info(f"Summary: Highest Pc = {summary_stats['highest_pc']:.2e}, " +
                   f"Average Pc = {summary_stats['average_pc']:.2e}")
        
        return enhanced_alerts, summary_stats
    
    def generate_probability_visualization(self, enhanced_alerts: List[Dict],
                                          output_path: Path):
        """
        Step 7: Generate histogram of Pc distribution
        """
        pc_values = [alert["collision_probability"] for alert in enhanced_alerts]
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Probability of Collision Analysis', fontsize=16, fontweight='bold')
        
        # Histogram (log scale)
        ax1 = axes[0, 0]
        ax1.hist(pc_values, bins=30, edgecolor='black', alpha=0.7, color='steelblue')
        ax1.set_xlabel('Collision Probability (Pc)', fontsize=11)
        ax1.set_ylabel('Frequency', fontsize=11)
        ax1.set_title('Distribution of Collision Probabilities', fontweight='bold')
        ax1.grid(True, alpha=0.3)
        
        # Log-scale histogram
        ax2 = axes[0, 1]
        pc_nonzero = [p for p in pc_values if p > 0]
        if pc_nonzero:
            ax2.hist(np.log10(pc_nonzero), bins=30, edgecolor='black', alpha=0.7, color='coral')
            ax2.set_xlabel('log₁₀(Pc)', fontsize=11)
            ax2.set_ylabel('Frequency', fontsize=11)
            ax2.set_title('Distribution of log₁₀(Pc)', fontweight='bold')
            ax2.grid(True, alpha=0.3)
        
        # Risk classification pie chart
        ax3 = axes[1, 0]
        risk_counts = {
            'HIGH (Pc > 1e-3)': sum(1 for p in pc_values if p > 1e-3),
            'MEDIUM (1e-5 < Pc ≤ 1e-3)': sum(1 for p in pc_values if 1e-5 < p <= 1e-3),
            'LOW (Pc ≤ 1e-5)': sum(1 for p in pc_values if p <= 1e-5)
        }
        colors = ['red', 'orange', 'green']
        ax3.pie(risk_counts.values(), labels=risk_counts.keys(), autopct='%1.1f%%',
               colors=colors, startangle=90)
        ax3.set_title('Risk Classification', fontweight='bold')
        
        # Distance vs Pc scatter
        ax4 = axes[1, 1]
        distances = [alert.get("distance_km", 0) for alert in enhanced_alerts]
        scatter = ax4.scatter(distances, pc_values, c=pc_values, cmap='RdYlGn_r',
                             s=100, alpha=0.6, edgecolors='black')
        ax4.set_xlabel('Miss Distance (km)', fontsize=11)
        ax4.set_ylabel('Collision Probability (Pc)', fontsize=11)
        ax4.set_title('Miss Distance vs Collision Probability', fontweight='bold')
        ax4.grid(True, alpha=0.3)
        cbar = plt.colorbar(scatter, ax=ax4)
        cbar.set_label('Pc', fontsize=10)
        
        plt.tight_layout()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"Saved visualization to {output_path}")
        plt.close()
    
    def generate_summary_report(self, summary_stats: Dict, enhanced_alerts: List[Dict],
                               output_path: Path):
        """Generate summary report of uncertainty analysis"""
        
        report = f"""# Uncertainty Modeling and Probability of Collision Analysis
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary

### System Configuration
- Uncertainty Model: Diagonal covariance with sigma_x = sigma_y = sigma_z = 0.5 km (LEO)
- Conjunction Radius: 2.0 km
- Monte Carlo Samples: 1000 per conjunction

### Key Statistics
- **Total Alerts Analyzed**: {summary_stats['total_alerts']}
- **Highest Pc**: {summary_stats['highest_pc']:.4e}
- **Average Pc**: {summary_stats['average_pc']:.4e}
- **Median Pc**: {summary_stats['median_pc']:.4e}
- **Std Dev Pc**: {summary_stats['std_pc']:.4e}
- **Minimum Pc**: {summary_stats['min_pc']:.4e}

### Risk Distribution
- **HIGH RISK** (Pc > 1e-3): {summary_stats['distribution']['high_risk_count']} events
- **MEDIUM RISK** (1e-5 < Pc <= 1e-3): {summary_stats['distribution']['medium_risk_count']} events
- **LOW RISK** (Pc <= 1e-5): {summary_stats['distribution']['low_risk_count']} events

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

"""
        
        # Sort by Pc and show top 10
        sorted_alerts = sorted(enhanced_alerts, key=lambda x: x['collision_probability'], reverse=True)
        
        for i, alert in enumerate(sorted_alerts[:10], 1):
            report += f"""
### {i}. {alert['object_1']} <-> {alert['object_2']}
- **Collision Probability**: {alert['collision_probability']:.4e}
- **Risk Classification**: {alert['pc_classification']}
- **Decision**: {alert['decision_recommendation']}
- **Miss Distance**: {alert['distance_km']:.2f} km
- **Time to CA**: {alert['tca_seconds']:.1f} seconds
- **Relative Velocity**: {alert['relative_velocity_kms']:.3f} km/s
- **Uncertainty (sigma_eff)**: {alert['uncertainty_km']:.3f} km
- **Pc Breakdown**:
  - Gaussian: {alert['pc_methods']['gaussian']:.4e}
  - Tail Probability: {alert['pc_methods']['tail_probability']:.4e}
  - Volume-Based: {alert['pc_methods']['volume_based']:.4e}
  - Monte Carlo: {alert['pc_methods']['monte_carlo']:.4e}
"""
        
        report += """

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
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"Saved report to {output_path}")
    
    def run_complete_analysis(self):
        """Execute complete uncertainty analysis pipeline"""
        
        logger.info("=" * 60)
        logger.info("Starting Complete Uncertainty Analysis")
        logger.info("=" * 60)
        
        # Step 1: Add uncertainty to vectors
        enhanced_vectors = self.add_uncertainty_to_vectors()
        
        # Steps 2-4: Process alerts and compute Pc
        enhanced_alerts, summary_stats = self.process_collision_alerts()
        
        # Step 7: Generate visualization
        output_dir = Path(self.collision_alerts_file).parent.parent / "outputs" / "plots"
        viz_path = output_dir / "probability_distribution.png"
        self.generate_probability_visualization(enhanced_alerts, viz_path)
        
        # Generate reports
        summary_path = Path(self.collision_alerts_file).parent.parent / "outputs" / "uncertainty_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary_stats, f, indent=2)
        logger.info(f"Saved summary to {summary_path}")
        
        report_path = Path(self.collision_alerts_file).parent.parent / "outputs" / "uncertainty_analysis_report.md"
        self.generate_summary_report(summary_stats, enhanced_alerts, report_path)
        
        # Step 5: Save enhanced alerts
        alerts_output = Path(self.collision_alerts_file).parent.parent / "outputs" / "collision_alerts_enhanced.json"
        self._save_json(alerts_output, enhanced_alerts)
        
        # Save enhanced vectors
        vectors_output = Path(self.collision_alerts_file).parent.parent / "outputs" / "state_vectors_enhanced.json"
        self._save_json(vectors_output, enhanced_vectors)
        
        logger.info("=" * 60)
        logger.info("Analysis Complete!")
        logger.info("=" * 60)
        
        return enhanced_alerts, summary_stats


if __name__ == "__main__":
    # Paths
    project_dir = Path(__file__).parent
    state_vectors_file = project_dir / "dataset" / "state_vectors.json"
    collision_alerts_file = project_dir / "dataset" / "collision_alerts.json"
    
    # Run analysis
    processor = UncertaintyProcessor(state_vectors_file, collision_alerts_file)
    enhanced_alerts, summary_stats = processor.run_complete_analysis()
    
    # Print summary
    print("\n" + "="*60)
    print("UNCERTAINTY ANALYSIS SUMMARY")
    print("="*60)
    print(f"Total Alerts: {summary_stats['total_alerts']}")
    print(f"Highest Pc: {summary_stats['highest_pc']:.4e}")
    print(f"Average Pc: {summary_stats['average_pc']:.4e}")
    print(f"\nRisk Distribution:")
    print(f"  HIGH: {summary_stats['distribution']['high_risk_count']}")
    print(f"  MEDIUM: {summary_stats['distribution']['medium_risk_count']}")
    print(f"  LOW: {summary_stats['distribution']['low_risk_count']}")
    print("="*60)
