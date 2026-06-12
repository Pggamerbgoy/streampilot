import time
import json
from data_engine import StreamPilotDataEngine
from math_engine import StreamPilotMathEngine

class StreamPilotAgent:
    """
    Main Autonomous Agent controlling the StreamPilot AI platform.
    Integrates the 4-Layer Data Engine with the Math/AI Engine to produce actionable insights.
    """

    def __init__(self):
        print("🚀 Initializing StreamPilot Autonomous Agent...")
        self.data_engine = StreamPilotDataEngine(niche="tech")
        self.math_engine = StreamPilotMathEngine()
        self.state = {
            "insights": [],
            "schedule": {},
            "metrics": {}
        }
        print("✅ Initialization Complete.\n")

    def run_training_pipeline(self):
        """
        Simulates the background 'training' and processing of user data using the math models.
        """
        print("=========================================")
        print("⚙️ RUNNING DATA & TRAINING PIPELINE ⚙️")
        print("=========================================")

        # 1. Fetch User Data
        user_data = self.data_engine.fetch_layer3_data()
        views_history = [v['views'] for v in user_data['videos']]

        # 2. Run Kalman Filter for True Growth
        smoothed_views, growth_rate = self.math_engine.kalman_filter_growth(views_history)
        self.state['metrics']['true_growth_rate'] = growth_rate

        if growth_rate > 2.0:
            self.state['insights'].append(f"Channel is experiencing strong Kalman-smoothed growth ({growth_rate}%).")
        else:
            self.state['insights'].append(f"Growth is stagnant ({growth_rate}%). Immediate strategy shift required.")

        # 3. Simulate A/B Test Training
        print("\n[AGENT] Evaluating recent thumbnail performance with Bayesian A/B testing...")
        historical_ctr = [video.get("ctr", 5.0) / 100 for video in user_data.get("videos", [])]
        ab_result = self.math_engine.bayesian_ab_test(
            3000,
            114,
            3050,
            164,
            historical_ctr=historical_ctr,
            seed=42,
        )
        if ab_result['winner'] != "Inconclusive":
            self.state['insights'].append(f"A/B Test Concluded: Variant {ab_result['winner']} wins with {ab_result['confidence']}% confidence.")

        # 4. Generate Optimal Schedule
        print("\n[AGENT] Optimizing Content Pipeline Schedule...")
        pending_videos = [
            {'id': 'RTX 5090 Review', 'priority': 95, 'type': 'review'},
            {'id': 'Budget PC Build', 'priority': 70, 'type': 'build'},
            {'id': 'Setup Tour', 'priority': 40, 'type': 'tour'}
        ]
        available_slots = ["Thursday_14:00", "Saturday_10:00", "Tuesday_16:00"]
        schedule = self.math_engine.slot_thompson_optimizer(pending_videos, available_slots, seed=42)
        self.state['schedule'] = schedule

        print("\n=========================================")
        print("🧠 PIPELINE COMPLETE. READY FOR DASHBOARD.")
        print("=========================================")

    def get_dashboard_payload(self):
        """Returns the synthesized data for the JS frontend."""
        user_kb = self.data_engine.knowledge_base.get('user', {})
        channel_name = user_kb.get('channel_name', 'Unknown')
        subs = user_kb.get('subscribers', 0)
        views = user_kb.get('total_views', 0)
        videos = user_kb.get('video_count', 0)

        return {
            "channel_name": channel_name,
            "real_subscribers": subs,
            "total_views": views,
            "video_count": videos,
            "channel_health": 85 if self.state['metrics'].get('true_growth_rate', 0) > 0 else 60,
            "insights": self.state['insights'],
            "optimal_schedule": self.state['schedule']
        }

if __name__ == "__main__":
    agent = StreamPilotAgent()
    agent.run_training_pipeline()

    print("\n--- Final Dashboard Payload ---")
    print(json.dumps(agent.get_dashboard_payload(), indent=2))
