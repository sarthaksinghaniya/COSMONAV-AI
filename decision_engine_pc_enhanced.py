"""
Enhanced Autonomous Decision System with Probability-Based Risk Assessment
Integrates Pc-based decision-making with uncertainty quantification
"""

import json
import numpy as np
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProbabilityBasedDecisionEngine:
    """Decision engine enhanced with collision probability analysis"""
    
    def __init__(self, enhanced_alerts_file: Path):
        """Load enhanced alerts with Pc values"""
        with open(enhanced_alerts_file, 'r') as f:
            self.alerts = json.load(f)
        logger.info(f"Loaded {len(self.alerts)} enhanced alerts")
    
    def make_decisions(self) -> Dict[str, List[Dict]]:
        """
        Make decisions based on Pc classification (Step 6)
        
        Returns:
            decisions: Organized by decision type
        """
        decisions = {
            "execute_maneuvers": [],      # Pc > 1e-3: Execute avoidance
            "monitor_close": [],          # Pc > 1e-5: Intensive tracking
            "routine_monitoring": [],     # Pc <= 1e-5: Standard schedule
            "unclassified": []
        }
        
        for alert in self.alerts:
            decision_info = {
                "object_1": alert["object_1"],
                "object_2": alert["object_2"],
                "collision_probability": alert["collision_probability"],
                "pc_classification": alert.get("pc_classification", "LOW"),
                "miss_distance_km": alert.get("distance_km", 0),
                "time_to_ca_seconds": alert.get("tca_seconds", 0),
                "relative_velocity_kms": alert.get("relative_velocity_kms", 0),
                "uncertainty_km": alert.get("uncertainty_km", 0),
                "action": self._get_action(alert),
                "urgency": self._get_urgency(alert),
                "priority": self._get_priority(alert),
                "reasoning": self._get_reasoning(alert),
                "maneuver_recommendation": self._get_maneuver_recommendation(alert),
                "tracking_frequency": self._get_tracking_frequency(alert)
            }
            
            decision_type = alert.get("decision_recommendation", "ROUTINE")
            
            if decision_type == "EXECUTE_MANEUVER":
                decisions["execute_maneuvers"].append(decision_info)
            elif decision_type == "MONITOR_CLOSE":
                decisions["monitor_close"].append(decision_info)
            elif decision_type == "ROUTINE":
                decisions["routine_monitoring"].append(decision_info)
            else:
                decisions["unclassified"].append(decision_info)
        
        return decisions
    
    def _get_action(self, alert: Dict) -> str:
        """Determine action based on Pc"""
        pc = alert["collision_probability"]
        
        if pc > 1e-3:
            return "IMMEDIATE_MANEUVER"
        elif pc > 1e-5:
            return "INCREASE_TRACKING"
        else:
            return "CONTINUE_ROUTINE"
    
    def _get_urgency(self, alert: Dict) -> str:
        """Classify urgency level"""
        pc = alert["collision_probability"]
        tca = alert.get("tca_seconds", 9999)
        
        # High Pc + Short TCA = CRITICAL
        if pc > 1e-3 and tca < 600:
            return "CRITICAL"
        elif pc > 1e-3:
            return "HIGH"
        elif pc > 1e-5:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _get_priority(self, alert: Dict) -> int:
        """Priority score (1=highest, 10=lowest)"""
        pc = alert["collision_probability"]
        tca = alert.get("tca_seconds", 9999)
        distance = alert.get("distance_km", 100)
        
        # Score based on Pc and TCA
        if pc > 1e-3 and tca < 600:
            return 1
        elif pc > 1e-3 and tca < 1800:
            return 2
        elif pc > 1e-3:
            return 3
        elif pc > 1e-4 and tca < 1800:
            return 4
        elif pc > 1e-4:
            return 5
        elif pc > 1e-5:
            return 6
        else:
            return 10
    
    def _get_reasoning(self, alert: Dict) -> str:
        """Explain the decision rationale"""
        pc = alert["collision_probability"]
        distance = alert.get("distance_km", 0)
        
        if pc > 1e-3:
            return f"High collision probability ({pc:.2e}). Miss distance {distance:.1f} km with significant uncertainty."
        elif pc > 1e-5:
            return f"Moderate collision probability ({pc:.2e}). Requires close monitoring."
        else:
            return f"Low collision probability ({pc:.2e}). Distance {distance:.1f} km provides safety margin."
    
    def _get_maneuver_recommendation(self, alert: Dict) -> Dict:
        """Recommend maneuver parameters"""
        pc = alert["collision_probability"]
        distance = alert.get("distance_km", 0)
        rel_velocity = alert.get("relative_velocity_kms", 0)
        tca_seconds = alert.get("tca_seconds", 0)
        
        if pc > 1e-3:
            # Conservative approach: modify velocity to create separation
            delta_v_mps = max(0.5, rel_velocity * 100)  # m/s
            
            return {
                "required": True,
                "maneuver_type": "velocity_adjustment",
                "delta_v_mps": float(delta_v_mps),
                "execution_window_seconds": max(60, tca_seconds - 300),
                "preferred_direction": "radial_outward",
                "abort_if_pc_drops_below": 1e-4,
                "post_maneuver_verification": True
            }
        elif pc > 1e-5:
            return {
                "required": False,
                "maneuver_type": "standby",
                "condition": "execute if Pc rises above 1e-3",
                "pre_planning": True,
                "delta_v_estimate_mps": 1.0
            }
        else:
            return {
                "required": False,
                "maneuver_type": "none",
                "condition": "continue nominal operations"
            }
    
    def _get_tracking_frequency(self, alert: Dict) -> Dict:
        """Recommended tracking schedule"""
        pc = alert["collision_probability"]
        
        if pc > 1e-3:
            return {
                "frequency": "1 minute",
                "duration": "until Pc drops to 1e-4",
                "ephemeris_update": "continuous",
                "tracking_mode": "high_precision"
            }
        elif pc > 1e-5:
            return {
                "frequency": "5 minutes",
                "duration": "24 hours",
                "ephemeris_update": "every 30 minutes",
                "tracking_mode": "precision"
            }
        else:
            return {
                "frequency": "6 hours (standard)",
                "duration": "ongoing",
                "ephemeris_update": "daily",
                "tracking_mode": "routine"
            }
    
    def generate_decision_log(self, decisions: Dict, output_path: Path):
        """Generate detailed decision log"""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "analysis_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_decisions": sum(len(v) for v in decisions.values()),
            "decisions_by_type": {k: len(v) for k, v in decisions.items()},
            "decisions": decisions,
            "summary": {
                "execute_count": len(decisions["execute_maneuvers"]),
                "monitor_count": len(decisions["monitor_close"]),
                "routine_count": len(decisions["routine_monitoring"]),
                "immediate_actions_required": len([d for d in decisions["execute_maneuvers"]
                                                  if d["urgency"] == "CRITICAL"])
            }
        }
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        logger.info(f"Decision log saved to {output_path}")
        return log_data
    
    def generate_decision_report(self, decisions: Dict, output_path: Path):
        """Generate human-readable decision report"""
        
        report = f"""# Autonomous Decision System Report - Pc-Enhanced
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Decision Summary

### Totals
- **Execute Maneuvers**: {len(decisions["execute_maneuvers"])} conjunctions
- **Monitor Closely**: {len(decisions["monitor_close"])} conjunctions
- **Routine Monitoring**: {len(decisions["routine_monitoring"])} conjunctions
- **Unclassified**: {len(decisions["unclassified"])} conjunctions

---

## CRITICAL ACTIONS REQUIRED

### Execute Maneuvers (Pc > 1e-3)
*These conjunctions require immediate collision avoidance actions*

"""
        
        if decisions["execute_maneuvers"]:
            for i, decision in enumerate(sorted(decisions["execute_maneuvers"],
                                               key=lambda x: x["priority"]), 1):
                report += f"""
#### {i}. {decision["object_1"]} <-> {decision["object_2"]}

**Risk Level**: {decision["urgency"]}
**Priority**: {decision["priority"]}/10

**Collision Data**:
- Probability of Collision: {decision["collision_probability"]:.4e}
- Miss Distance: {decision["miss_distance_km"]:.2f} km
- Time to Closest Approach: {decision["time_to_ca_seconds"]:.0f} seconds
- Relative Velocity: {decision["relative_velocity_kms"]:.3f} km/s
- Uncertainty: {decision["uncertainty_km"]:.3f} km

**Decision**: {decision["action"]}
**Reasoning**: {decision["reasoning"]}

**Maneuver Recommendation**:
- Type: {decision["maneuver_recommendation"]["maneuver_type"]}
- Delta V Required: {decision["maneuver_recommendation"].get("delta_v_mps", "N/A")} m/s
- Execution Window: {decision["maneuver_recommendation"].get("execution_window_seconds", "N/A")} seconds from NOW

**Tracking**:
- Frequency: {decision["tracking_frequency"]["frequency"]}
- Duration: {decision["tracking_frequency"]["duration"]}
- Mode: {decision["tracking_frequency"]["tracking_mode"]}

---
"""
        else:
            report += "\n*No HIGH-RISK conjunctions at this time.*\n\n"
        
        report += """
## MONITOR CLOSELY (1e-5 < Pc <= 1e-3)

*Increase tracking frequency and maintain readiness for maneuver execution*

"""
        
        if decisions["monitor_close"]:
            for i, decision in enumerate(sorted(decisions["monitor_close"],
                                               key=lambda x: x["priority"]), 1):
                report += f"""
#### {i}. {decision["object_1"]} <-> {decision["object_2"]}
- Pc = {decision["collision_probability"]:.4e}
- Miss Distance: {decision["miss_distance_km"]:.2f} km
- Tracking: {decision["tracking_frequency"]["frequency"]}
"""
        else:
            report += "\n*No MEDIUM-RISK conjunctions at this time.*\n"
        
        report += f"""

## ROUTINE MONITORING (Pc <= 1e-5)

Total: {len(decisions["routine_monitoring"])} conjunctions
- Continue standard 6-hour tracking schedule
- Update ephemeris daily
- Review daily conjunction assessment

---

## Recommendations for Operations

1. **CRITICAL**: Execute maneuvers for {len(decisions["execute_maneuvers"])} HIGH-RISK events
2. **URGENT**: Increase monitoring for {len(decisions["monitor_close"])} MEDIUM-RISK events
3. **ROUTINE**: Standard schedule for {len(decisions["routine_monitoring"])} LOW-RISK events

**Next Review**: In 1 hour or when Pc values change by >10%

---

Generated by Probability-Enhanced Autonomous Decision System
"""
        
        output_path.write_text(report, encoding='utf-8')
        logger.info(f"Decision report saved to {output_path}")


def main():
    """Main execution"""
    project_dir = Path(__file__).parent
    
    # Load enhanced alerts from uncertainty modeling
    enhanced_alerts_file = project_dir / "outputs" / "collision_alerts_enhanced.json"
    
    if not enhanced_alerts_file.exists():
        logger.error(f"Enhanced alerts file not found: {enhanced_alerts_file}")
        return
    
    # Create decision engine
    engine = ProbabilityBasedDecisionEngine(enhanced_alerts_file)
    
    # Make decisions
    decisions = engine.make_decisions()
    
    # Generate outputs
    decision_log_path = project_dir / "outputs" / "decision_log_pc_enhanced.json"
    decision_report_path = project_dir / "outputs" / "decision_report_pc_enhanced.md"
    
    log_data = engine.generate_decision_log(decisions, decision_log_path)
    engine.generate_decision_report(decisions, decision_report_path)
    
    # Print summary
    print("\n" + "="*70)
    print("ENHANCED DECISION ENGINE SUMMARY (Pc-Based)")
    print("="*70)
    print(f"Execute Maneuvers:       {log_data['summary']['execute_count']:3d}")
    print(f"Monitor Closely:         {log_data['summary']['monitor_count']:3d}")
    print(f"Routine Monitoring:      {log_data['summary']['routine_count']:3d}")
    print(f"CRITICAL URGENCY:        {log_data['summary']['immediate_actions_required']:3d}")
    print("="*70)
    print(f"\nDecision Log: {decision_log_path}")
    print(f"Decision Report: {decision_report_path}")


if __name__ == "__main__":
    main()
