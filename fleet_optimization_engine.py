"""
Fleet Optimization Engine for Multi-Satellite Coordination
Global optimization of collision avoidance maneuvers with risk minimization
"""

import json
import numpy as np
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any, Set, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import networkx as nx
import matplotlib.pyplot as plt
from scipy.optimize import minimize_scalar, differential_evolution
import itertools

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Satellite:
    """Represents a satellite with state and uncertainty"""
    name: str
    norad_id: int
    position: np.ndarray
    velocity: np.ndarray
    covariance_matrix: np.ndarray
    uncertainty_km: float = 0.707  # sqrt(0.5^2) for diagonal

    def get_covariance(self) -> np.ndarray:
        """Return covariance matrix"""
        return self.covariance_matrix

    def to_dict(self) -> Dict[str, Any]:
        """Serialize satellite data"""
        return {
            "name": self.name,
            "norad_id": self.norad_id,
            "position": self.position.tolist(),
            "velocity": self.velocity.tolist(),
            "covariance_matrix": self.covariance_matrix.tolist(),
            "uncertainty_km": self.uncertainty_km
        }


@dataclass
class CollisionRisk:
    """Represents collision risk between two satellites"""
    satellite_1: str
    satellite_2: str
    collision_probability: float
    miss_distance_km: float
    tca_seconds: float
    relative_velocity_kms: float
    uncertainty_km: float
    pc_classification: str
    decision_recommendation: str

    @property
    def risk_weight(self) -> float:
        """Calculate risk weight combining Pc and TCA"""
        # Higher Pc = higher weight
        pc_weight = self.collision_probability

        # Shorter TCA = higher weight (urgency)
        tca_weight = max(0, 1 - (self.tca_seconds / 86400))  # Normalize to 24 hours

        # Combine with emphasis on Pc
        return pc_weight * (1 + tca_weight)

    @property
    def is_high_risk(self) -> bool:
        """Check if this is a high-risk conjunction"""
        return self.collision_probability > 1e-3

    @property
    def is_medium_risk(self) -> bool:
        """Check if this is a medium-risk conjunction"""
        return 1e-5 < self.collision_probability <= 1e-3


@dataclass
class ManeuverCandidate:
    """Represents a potential maneuver for a satellite"""
    satellite: str
    delta_v_vector: np.ndarray  # 3D delta-V vector (m/s)
    fuel_cost: float  # Fuel cost (kg or arbitrary units)
    execution_time: float  # Time to execute (seconds)
    risk_reduction: float = 0.0  # Expected risk reduction
    secondary_risks: List[Dict] = field(default_factory=list)  # New risks created

    @property
    def delta_v_magnitude(self) -> float:
        """Magnitude of delta-V"""
        return np.linalg.norm(self.delta_v_vector)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize maneuver candidate"""
        return {
            "satellite": self.satellite,
            "delta_v_vector": self.delta_v_vector.tolist(),
            "delta_v_magnitude": self.delta_v_magnitude,
            "fuel_cost": self.fuel_cost,
            "execution_time": self.execution_time,
            "risk_reduction": self.risk_reduction,
            "secondary_risks": self.secondary_risks
        }


@dataclass
class OptimizationResult:
    """Result of fleet optimization"""
    satellite_decisions: Dict[str, Dict[str, Any]]
    total_risk_before: float
    total_risk_after: float
    total_fuel_cost: float
    efficiency_gain_percent: float
    clusters_processed: int
    maneuvers_planned: int
    secondary_risks_created: int

    def to_dict(self) -> Dict[str, Any]:
        """Serialize optimization result"""
        return {
            "satellite_decisions": self.satellite_decisions,
            "total_risk_before": self.total_risk_before,
            "total_risk_after": self.total_risk_after,
            "total_fuel_cost": self.total_fuel_cost,
            "efficiency_gain_percent": self.efficiency_gain_percent,
            "clusters_processed": self.clusters_processed,
            "maneuvers_planned": self.maneuvers_planned,
            "secondary_risks_created": self.secondary_risks_created,
            "timestamp": datetime.now().isoformat()
        }


class InteractionGraph:
    """Graph representation of satellite interactions and collision risks"""

    def __init__(self):
        """Initialize empty interaction graph"""
        self.graph = nx.Graph()
        self.satellites: Dict[str, Satellite] = {}
        self.collision_risks: List[CollisionRisk] = []

    def add_satellite(self, satellite: Satellite):
        """Add satellite as node"""
        self.satellites[satellite.name] = satellite
        self.graph.add_node(
            satellite.name,
            satellite=satellite,
            type='satellite'
        )

    def add_collision_risk(self, risk: CollisionRisk):
        """Add collision risk as weighted edge"""
        # Add edge with risk weight
        self.graph.add_edge(
            risk.satellite_1,
            risk.satellite_2,
            risk=risk,
            weight=risk.risk_weight,
            pc=risk.collision_probability,
            tca=risk.tca_seconds,
            type='collision_risk'
        )
        self.collision_risks.append(risk)

    def get_connected_components(self) -> List[List[str]]:
        """Get connected components (conflict clusters)"""
        return [list(component) for component in nx.connected_components(self.graph)]

    def get_high_risk_edges(self) -> List[Tuple[str, str, Dict]]:
        """Get edges with high collision risk"""
        high_risk = []
        for u, v, data in self.graph.edges(data=True):
            if data.get('type') == 'collision_risk':
                risk = data['risk']
                if risk.is_high_risk:
                    high_risk.append((u, v, data))
        return high_risk

    def get_cluster_risks(self, cluster: List[str]) -> List[CollisionRisk]:
        """Get all collision risks within a cluster"""
        cluster_risks = []
        for risk in self.collision_risks:
            if risk.satellite_1 in cluster and risk.satellite_2 in cluster:
                cluster_risks.append(risk)
        return cluster_risks

    def calculate_total_risk(self, cluster: Optional[List[str]] = None) -> float:
        """Calculate total collision risk for cluster or entire graph"""
        total_risk = 0.0

        edges = []
        if cluster:
            # Get edges within cluster
            for u, v in itertools.combinations(cluster, 2):
                if self.graph.has_edge(u, v):
                    edges.append((u, v, self.graph.get_edge_data(u, v)))
        else:
            # Get all edges
            edges = list(self.graph.edges(data=True))

        for u, v, data in edges:
            if data.get('type') == 'collision_risk':
                total_risk += data['risk'].collision_probability

        return total_risk


class ManeuverGenerator:
    """Generates candidate maneuvers for satellites"""

    def __init__(self, max_delta_v_mps: float = 50.0, fuel_efficiency: float = 1.0):
        """
        Initialize maneuver generator

        Args:
            max_delta_v_mps: Maximum delta-V per maneuver (m/s)
            fuel_efficiency: Fuel cost factor (kg per m/s delta-V)
        """
        self.max_delta_v = max_delta_v_mps
        self.fuel_efficiency = fuel_efficiency

    def generate_candidates(self, satellite: Satellite,
                          n_candidates: int = 10) -> List[ManeuverCandidate]:
        """
        Generate candidate maneuvers for a satellite

        Args:
            satellite: Satellite to maneuver
            n_candidates: Number of candidates to generate

        Returns:
            List of maneuver candidates
        """
        candidates = []

        # Generate random maneuver directions (spherical distribution)
        for i in range(n_candidates):
            # Random direction (unit vector)
            phi = np.random.uniform(0, 2*np.pi)
            theta = np.random.uniform(0, np.pi)

            direction = np.array([
                np.sin(theta) * np.cos(phi),
                np.sin(theta) * np.sin(phi),
                np.cos(theta)
            ])

            # Random magnitude (0 to max_delta_v)
            magnitude = np.random.uniform(0.1, self.max_delta_v)

            # Delta-V vector
            delta_v = magnitude * direction

            # Fuel cost (simplified: mass * delta_v, assuming unit mass)
            fuel_cost = magnitude * self.fuel_efficiency

            # Execution time (simplified: proportional to delta_v)
            execution_time = magnitude * 10  # 10 seconds per m/s

            candidate = ManeuverCandidate(
                satellite=satellite.name,
                delta_v_vector=delta_v,
                fuel_cost=fuel_cost,
                execution_time=execution_time
            )

            candidates.append(candidate)

        # Add "no maneuver" option
        no_maneuver = ManeuverCandidate(
            satellite=satellite.name,
            delta_v_vector=np.zeros(3),
            fuel_cost=0.0,
            execution_time=0.0
        )
        candidates.append(no_maneuver)

        return candidates

    def evaluate_maneuver_risk_reduction(self, candidate: ManeuverCandidate,
                                        cluster_risks: List[CollisionRisk],
                                        satellite: Satellite) -> ManeuverCandidate:
        """
        Evaluate risk reduction for a maneuver candidate

        Args:
            candidate: Maneuver candidate to evaluate
            cluster_risks: Collision risks in the cluster
            satellite: Satellite being maneuvered

        Returns:
            Updated candidate with risk reduction estimate
        """
        # Simplified risk reduction calculation
        # In reality, this would require orbital propagation
        risk_reduction = 0.0
        secondary_risks = []

        # For each risk involving this satellite
        for risk in cluster_risks:
            if risk.satellite_1 == satellite.name or risk.satellite_2 == satellite.name:
                # Estimate risk reduction based on delta-V magnitude
                # Larger maneuvers reduce risk more
                reduction_factor = min(1.0, candidate.delta_v_magnitude / 10.0)
                risk_reduction += risk.collision_probability * reduction_factor

                # Check for potential secondary risks (simplified)
                # In reality, would need to check against all other satellites
                if candidate.delta_v_magnitude > 20.0:  # Large maneuver
                    secondary_risks.append({
                        "potential_new_risk": f"Large maneuver may create new conjunction with nearby satellites",
                        "estimated_pc_increase": 1e-5 * (candidate.delta_v_magnitude / 20.0)
                    })

        candidate.risk_reduction = risk_reduction
        candidate.secondary_risks = secondary_risks

        return candidate


class FleetOptimizer:
    """Global optimization engine for fleet maneuver coordination"""

    def __init__(self, interaction_graph: InteractionGraph,
                 maneuver_generator: ManeuverGenerator):
        """
        Initialize fleet optimizer

        Args:
            interaction_graph: Graph of satellite interactions
            maneuver_generator: Generator for maneuver candidates
        """
        self.graph = interaction_graph
        self.maneuver_gen = maneuver_generator
        self.optimization_results: List[OptimizationResult] = []

    def optimize_cluster(self, cluster: List[str],
                        n_candidates_per_satellite: int = 5) -> Dict[str, ManeuverCandidate]:
        """
        Optimize maneuvers for a cluster of satellites

        Args:
            cluster: List of satellite names in cluster
            n_candidates_per_satellite: Number of maneuver candidates per satellite

        Returns:
            Optimal maneuver assignment for cluster
        """
        logger.info(f"Optimizing cluster with {len(cluster)} satellites")

        # Get cluster satellites and risks
        cluster_satellites = [self.graph.satellites[name] for name in cluster]
        cluster_risks = self.graph.get_cluster_risks(cluster)

        # Generate maneuver candidates for each satellite
        all_candidates = {}
        for satellite in cluster_satellites:
            candidates = self.maneuver_gen.generate_candidates(
                satellite, n_candidates_per_satellite
            )

            # Evaluate risk reduction for each candidate
            evaluated_candidates = []
            for candidate in candidates:
                evaluated = self.maneuver_gen.evaluate_maneuver_risk_reduction(
                    candidate, cluster_risks, satellite
                )
                evaluated_candidates.append(evaluated)

            all_candidates[satellite.name] = evaluated_candidates

        # Find optimal combination using greedy approach
        optimal_assignment = self._greedy_optimization(
            cluster, all_candidates, cluster_risks
        )

        return optimal_assignment

    def _greedy_optimization(self, cluster: List[str],
                           candidates: Dict[str, List[ManeuverCandidate]],
                           cluster_risks: List[CollisionRisk]) -> Dict[str, ManeuverCandidate]:
        """
        Greedy optimization for maneuver selection

        Args:
            cluster: Satellite names
            candidates: Maneuver candidates per satellite
            cluster_risks: Collision risks in cluster

        Returns:
            Optimal maneuver assignment
        """
        # Start with no maneuvers
        assignment = {sat: candidates[sat][-1] for sat in cluster}  # Last is "no maneuver"

        # Calculate initial total risk
        initial_risk = self._calculate_total_risk_with_maneuvers(
            assignment, cluster_risks
        )

        # Greedily add maneuvers that provide best risk reduction per fuel cost
        improved = True
        while improved:
            improved = False
            best_improvement = 0.0
            best_satellite = None
            best_maneuver = None

            # Try changing each satellite's maneuver
            for sat_name in cluster:
                current_maneuver = assignment[sat_name]

                # Try each alternative maneuver
                for candidate in candidates[sat_name]:
                    if candidate.delta_v_magnitude == current_maneuver.delta_v_magnitude:
                        continue  # Skip same maneuver

                    # Test this assignment
                    test_assignment = assignment.copy()
                    test_assignment[sat_name] = candidate

                    test_risk = self._calculate_total_risk_with_maneuvers(
                        test_assignment, cluster_risks
                    )

                    # Calculate improvement (risk reduction minus fuel cost penalty)
                    risk_improvement = initial_risk - test_risk
                    fuel_penalty = candidate.fuel_cost * 0.1  # Weight fuel cost
                    net_improvement = risk_improvement - fuel_penalty

                    if net_improvement > best_improvement:
                        best_improvement = net_improvement
                        best_satellite = sat_name
                        best_maneuver = candidate

            # Apply best improvement if significant
            if best_improvement > 1e-6:  # Minimum improvement threshold
                assignment[best_satellite] = best_maneuver
                initial_risk -= best_improvement
                improved = True
                logger.info(f"Applied maneuver to {best_satellite}: "
                          f"ΔV={best_maneuver.delta_v_magnitude:.2f} m/s, "
                          f"improvement={best_improvement:.4e}")

        return assignment

    def _calculate_total_risk_with_maneuvers(self,
                                           assignment: Dict[str, ManeuverCandidate],
                                           cluster_risks: List[CollisionRisk]) -> float:
        """
        Calculate total collision risk given maneuver assignment

        Args:
            assignment: Maneuver assignment per satellite
            cluster_risks: Collision risks in cluster

        Returns:
            Total collision risk
        """
        total_risk = 0.0

        for risk in cluster_risks:
            sat1_maneuver = assignment[risk.satellite_1]
            sat2_maneuver = assignment[risk.satellite_2]

            # Simplified risk calculation
            # In reality, would need orbital propagation
            base_risk = risk.collision_probability

            # Risk reduction from maneuvers
            reduction1 = sat1_maneuver.risk_reduction * 0.5  # Split between pair
            reduction2 = sat2_maneuver.risk_reduction * 0.5

            # Secondary risks from large maneuvers
            secondary_risk = 0.0
            for sec_risk in sat1_maneuver.secondary_risks + sat2_maneuver.secondary_risks:
                secondary_risk += sec_risk.get("estimated_pc_increase", 0)

            # Adjusted risk
            adjusted_risk = max(0, base_risk - reduction1 - reduction2 + secondary_risk)
            total_risk += adjusted_risk

        return total_risk

    def optimize_fleet(self) -> OptimizationResult:
        """
        Perform fleet-wide optimization

        Returns:
            Complete optimization result
        """
        logger.info("Starting fleet-wide optimization")

        # Get conflict clusters
        clusters = self.graph.get_connected_components()
        logger.info(f"Found {len(clusters)} conflict clusters")

        # Calculate total risk before optimization
        total_risk_before = self.graph.calculate_total_risk()

        # Optimize each cluster
        all_decisions = {}
        total_fuel_cost = 0.0
        maneuvers_planned = 0
        secondary_risks_created = 0

        for i, cluster in enumerate(clusters):
            logger.info(f"Optimizing cluster {i+1}/{len(clusters)} "
                       f"({len(cluster)} satellites)")

            if len(cluster) > 1:  # Only optimize multi-satellite clusters
                cluster_decisions = self.optimize_cluster(cluster)
                all_decisions.update(cluster_decisions)

                # Accumulate metrics
                for maneuver in cluster_decisions.values():
                    total_fuel_cost += maneuver.fuel_cost
                    if maneuver.delta_v_magnitude > 0.1:  # Non-trivial maneuver
                        maneuvers_planned += 1
                    secondary_risks_created += len(maneuver.secondary_risks)
            else:
                # Single satellite - no optimization needed
                satellite = self.graph.satellites[cluster[0]]
                no_maneuver = ManeuverCandidate(
                    satellite=satellite.name,
                    delta_v_vector=np.zeros(3),
                    fuel_cost=0.0,
                    execution_time=0.0
                )
                all_decisions[satellite.name] = no_maneuver

        # Calculate total risk after optimization
        total_risk_after = self._calculate_total_risk_with_maneuvers(
            all_decisions, self.graph.collision_risks
        )

        # Calculate efficiency gain
        if total_risk_before > 0:
            efficiency_gain = (total_risk_before - total_risk_after) / total_risk_before * 100
        else:
            efficiency_gain = 0.0

        # Convert decisions to output format
        satellite_decisions = {}
        for sat_name, maneuver in all_decisions.items():
            satellite_decisions[sat_name] = {
                "satellite": sat_name,
                "action": "MANEUVER" if maneuver.delta_v_magnitude > 0.1 else "HOLD",
                "delta_v": maneuver.delta_v_vector.tolist(),
                "fuel_cost": maneuver.fuel_cost,
                "risk_reduction": maneuver.risk_reduction,
                "secondary_risk": sum(r.get("estimated_pc_increase", 0)
                                    for r in maneuver.secondary_risks)
            }

        result = OptimizationResult(
            satellite_decisions=satellite_decisions,
            total_risk_before=total_risk_before,
            total_risk_after=total_risk_after,
            total_fuel_cost=total_fuel_cost,
            efficiency_gain_percent=efficiency_gain,
            clusters_processed=len(clusters),
            maneuvers_planned=maneuvers_planned,
            secondary_risks_created=secondary_risks_created
        )

        self.optimization_results.append(result)
        logger.info(f"Fleet optimization complete: "
                   f"{maneuvers_planned} maneuvers planned, "
                   f"efficiency gain: {efficiency_gain:.1f}%")

        return result


class FleetOptimizationEngine:
    """Main engine for fleet optimization"""

    def __init__(self, state_vectors_file: Path, collision_alerts_file: Path,
                 decision_log_file: Path):
        """
        Initialize fleet optimization engine

        Args:
            state_vectors_file: Path to enhanced state vectors
            collision_alerts_file: Path to enhanced collision alerts
            decision_log_file: Path to decision log
        """
        self.state_vectors_file = state_vectors_file
        self.collision_alerts_file = collision_alerts_file
        self.decision_log_file = decision_log_file

        # Load data
        self.satellites = self._load_satellites()
        self.collision_alerts = self._load_collision_alerts()
        self.decision_log = self._load_decision_log()

        # Initialize components
        self.interaction_graph = self._build_interaction_graph()
        self.maneuver_generator = ManeuverGenerator(max_delta_v_mps=50.0)
        self.optimizer = FleetOptimizer(self.interaction_graph, self.maneuver_generator)

        logger.info(f"Initialized fleet optimization engine with "
                   f"{len(self.satellites)} satellites and "
                   f"{len(self.collision_alerts)} collision alerts")

    def _load_satellites(self) -> Dict[str, Satellite]:
        """Load satellite data from enhanced state vectors"""
        with open(self.state_vectors_file, 'r') as f:
            data = json.load(f)

        satellites = {}
        for item in data:
            satellite = Satellite(
                name=item['name'],
                norad_id=item['norad_id'],
                position=np.array(item['position']),
                velocity=np.array(item['velocity']),
                covariance_matrix=np.array(item['covariance_matrix']),
                uncertainty_km=item.get('uncertainty_km', 0.707)
            )
            satellites[satellite.name] = satellite

        return satellites

    def _load_collision_alerts(self) -> List[Dict]:
        """Load collision alerts"""
        with open(self.collision_alerts_file, 'r') as f:
            return json.load(f)

    def _load_decision_log(self) -> Dict:
        """Load decision log"""
        with open(self.decision_log_file, 'r') as f:
            return json.load(f)

    def _build_interaction_graph(self) -> InteractionGraph:
        """Build interaction graph from data"""
        graph = InteractionGraph()

        # Add satellites as nodes
        for satellite in self.satellites.values():
            graph.add_satellite(satellite)

        # Add collision risks as edges (focus on HIGH and MEDIUM risk)
        for alert in self.collision_alerts:
            pc = alert.get('collision_probability', 0)
            if pc > 1e-5:  # Include MEDIUM and HIGH risk
                risk = CollisionRisk(
                    satellite_1=alert['object_1'],
                    satellite_2=alert['object_2'],
                    collision_probability=pc,
                    miss_distance_km=alert.get('distance_km', 0),
                    tca_seconds=alert.get('tca_seconds', 0),
                    relative_velocity_kms=alert.get('relative_velocity_kms', 0),
                    uncertainty_km=alert.get('uncertainty_km', 0.707),
                    pc_classification=alert.get('pc_classification', 'LOW'),
                    decision_recommendation=alert.get('decision_recommendation', 'ROUTINE')
                )
                graph.add_collision_risk(risk)

        return graph

    def run_optimization(self) -> OptimizationResult:
        """Run complete fleet optimization"""
        logger.info("Starting fleet optimization process")

        # Step 1: Load system state ✓ (already done in init)

        # Step 2: Build interaction graph ✓ (already done)

        # Step 3: Conflict grouping ✓ (handled in optimizer)

        # Step 4-5: Global optimization with constraints
        result = self.optimizer.optimize_fleet()

        # Step 6: Decision output ✓ (in result)

        return result

    def generate_visualizations(self, result: OptimizationResult, output_dir: Path):
        """Generate visualizations (Step 7)"""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Fleet interaction graph
        self._plot_interaction_graph(output_dir / "fleet_graph.png")

        # Risk comparison
        self._plot_risk_comparison(result, output_dir / "before_after_risk.png")

    def _plot_interaction_graph(self, output_path: Path):
        """Plot satellite interaction graph"""
        plt.figure(figsize=(12, 8))

        # Create layout
        pos = nx.spring_layout(self.interaction_graph.graph, k=2, iterations=50)

        # Draw nodes (satellites)
        satellite_nodes = [n for n, d in self.interaction_graph.graph.nodes(data=True)
                          if d.get('type') == 'satellite']
        nx.draw_networkx_nodes(self.interaction_graph.graph, pos,
                             nodelist=satellite_nodes,
                             node_color='lightblue',
                             node_size=300,
                             alpha=0.8)

        # Draw edges (collision risks) with thickness based on risk
        edges = self.interaction_graph.graph.edges(data=True)
        edge_colors = []
        edge_widths = []

        for u, v, data in edges:
            if data.get('type') == 'collision_risk':
                pc = data['pc']
                if pc > 1e-3:  # HIGH risk
                    edge_colors.append('red')
                    edge_widths.append(3)
                elif pc > 1e-5:  # MEDIUM risk
                    edge_colors.append('orange')
                    edge_widths.append(2)
                else:  # LOW risk
                    edge_colors.append('green')
                    edge_widths.append(1)

        nx.draw_networkx_edges(self.interaction_graph.graph, pos,
                             edge_color=edge_colors,
                             width=edge_widths,
                             alpha=0.6)

        # Labels
        labels = {node: node.split()[-1] for node in satellite_nodes}  # Short names
        nx.draw_networkx_labels(self.interaction_graph.graph, pos, labels,
                              font_size=8, font_weight='bold')

        plt.title('Satellite Fleet Interaction Graph\n'
                 'Red: HIGH risk (Pc > 1e-3), Orange: MEDIUM risk, Green: LOW risk',
                 fontsize=14, fontweight='bold')
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"Saved interaction graph to {output_path}")

    def _plot_risk_comparison(self, result: OptimizationResult, output_path: Path):
        """Plot before/after risk comparison"""
        plt.figure(figsize=(10, 6))

        categories = ['Before Optimization', 'After Optimization']
        risks = [result.total_risk_before, result.total_risk_after]

        bars = plt.bar(categories, risks, color=['red', 'green'], alpha=0.7)

        # Add value labels
        for bar, risk in zip(bars, risks):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(risks)*0.01,
                    f'{risk:.4e}', ha='center', va='bottom', fontweight='bold')

        plt.ylabel('Total Collision Risk (Sum of Pc)', fontsize=12)
        plt.title('Fleet Optimization Risk Reduction', fontsize=14, fontweight='bold')
        plt.grid(True, alpha=0.3)

        # Add efficiency annotation
        efficiency_text = f"Efficiency Gain: {result.efficiency_gain_percent:.1f}%"
        plt.text(0.5, max(risks)*0.8, efficiency_text,
                ha='center', va='center', fontsize=12,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.8))

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"Saved risk comparison to {output_path}")

    def save_results(self, result: OptimizationResult, output_dir: Path):
        """Save optimization results (Step 6)"""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Fleet optimization results
        fleet_output = output_dir / "fleet_optimization.json"
        with open(fleet_output, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)

        # Fleet summary
        summary = {
            "optimization_summary": {
                "timestamp": datetime.now().isoformat(),
                "total_satellites": len(self.satellites),
                "total_collision_alerts": len(self.collision_alerts),
                "high_risk_alerts": len([a for a in self.collision_alerts
                                       if a.get('collision_probability', 0) > 1e-3]),
                "medium_risk_alerts": len([a for a in self.collision_alerts
                                         if 1e-5 < a.get('collision_probability', 0) <= 1e-3]),
                "clusters_identified": result.clusters_processed,
                "maneuvers_planned": result.maneuvers_planned,
                "total_fuel_cost": result.total_fuel_cost,
                "risk_reduction": result.total_risk_before - result.total_risk_after,
                "efficiency_gain_percent": result.efficiency_gain_percent
            },
            "performance_metrics": {
                "total_risk_before": result.total_risk_before,
                "total_risk_after": result.total_risk_after,
                "fuel_efficiency": result.efficiency_gain_percent / max(result.total_fuel_cost, 1e-6),
                "maneuver_efficiency": (result.total_risk_before - result.total_risk_after) / max(result.maneuvers_planned, 1),
                "secondary_risks_created": result.secondary_risks_created
            }
        }

        summary_output = output_dir / "fleet_summary.json"
        with open(summary_output, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Saved fleet optimization results to {fleet_output}")
        logger.info(f"Saved fleet summary to {summary_output}")

    def run_complete_analysis(self):
        """Run complete fleet optimization analysis"""
        logger.info("=" * 60)
        logger.info("FLEET OPTIMIZATION ENGINE")
        logger.info("=" * 60)

        # Run optimization
        result = self.run_optimization()

        # Generate visualizations
        output_dir = Path(self.state_vectors_file).parent.parent / "outputs" / "fleet_optimization"
        self.generate_visualizations(result, output_dir)

        # Save results
        self.save_results(result, output_dir)

        # Print summary
        print("\n" + "="*70)
        print("FLEET OPTIMIZATION RESULTS")
        print("="*70)
        print(f"Total Satellites:        {len(self.satellites):3d}")
        print(f"Collision Alerts:        {len(self.collision_alerts):3d}")
        print(f"Conflict Clusters:       {result.clusters_processed:3d}")
        print(f"Maneuvers Planned:       {result.maneuvers_planned:3d}")
        print(f"Total Fuel Cost:         {result.total_fuel_cost:.2f}")
        print(f"Risk Before:             {result.total_risk_before:.4e}")
        print(f"Risk After:              {result.total_risk_after:.4e}")
        print(f"Efficiency Gain:         {result.efficiency_gain_percent:.1f}%")
        print(f"Secondary Risks:         {result.secondary_risks_created:3d}")
        print("="*70)

        logger.info("Fleet optimization analysis complete")

        return result


def main():
    """Main execution"""
    project_dir = Path(__file__).parent

    # Input files
    state_vectors_file = project_dir / "outputs" / "state_vectors_enhanced.json"
    collision_alerts_file = project_dir / "outputs" / "collision_alerts_enhanced.json"
    decision_log_file = project_dir / "outputs" / "decision_log_pc_enhanced.json"

    # Check if files exist
    for file_path in [state_vectors_file, collision_alerts_file, decision_log_file]:
        if not file_path.exists():
            logger.error(f"Required file not found: {file_path}")
            return

    # Run fleet optimization
    engine = FleetOptimizationEngine(
        state_vectors_file, collision_alerts_file, decision_log_file
    )

    result = engine.run_complete_analysis()

    print(f"\nOptimization complete! Results saved to outputs/fleet_optimization/")


if __name__ == "__main__":
    main()