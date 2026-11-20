import uuid
import random


class AIArchitectEconomy:

    def __init__(self, agent_pool):

        # pool of AI architects (agents)
        self.agents = agent_pool

        # marketplace listings
        self.jobs = {}

        # completed projects
        self.completed = {}

    # ======================
    # 1. POST JOB
    # ======================
    def post_job(self, client_request, budget=1000):

        job_id = str(uuid.uuid4())

        self.jobs[job_id] = {
            "request": client_request,
            "budget": budget,
            "bids": [],
            "status": "open"
        }

        return job_id

    # ======================
    # 2. AI BIDDING SYSTEM
    # ======================
    def collect_bids(self, job_id):

        job = self.jobs[job_id]

        for agent in self.agents:

            bid = agent.propose_bid(job["request"], job["budget"])

            self.jobs[job_id]["bids"].append({
                "agent": agent.name,
                "price": bid["price"],
                "confidence": bid["confidence"],
                "design_quality_estimate": bid["quality"]
            })

        return self.jobs[job_id]["bids"]

    # ======================
    # 3. SELECT WINNER
    # ======================
    def select_winner(self, job_id):

        bids = self.jobs[job_id]["bids"]

        def score(b):
            return (b["confidence"] * 0.5 +
                    b["design_quality_estimate"] * 0.4 -
                    (b["price"] / 10000) * 0.1)

        winner = max(bids, key=score)

        self.jobs[job_id]["status"] = "assigned"
        self.jobs[job_id]["winner"] = winner

        return winner

    # ======================
    # 4. EXECUTE DESIGN
    # ======================
    def execute_job(self, job_id):

        job = self.jobs[job_id]
        winner_name = job["winner"]["agent"]

        agent = self._get_agent(winner_name)

        design = agent.generate_design(job["request"])

        self.completed[job_id] = {
            "design": design,
            "agent": winner_name,
            "price": job["winner"]["price"]
        }

        self.jobs[job_id]["status"] = "completed"

        return design

    # ======================
    # 5. ECONOMY METRICS
    # ======================
    def market_stats(self):

        total_jobs = len(self.jobs)
        completed_jobs = len(self.completed)

        avg_price = 0

        if completed_jobs > 0:
            avg_price = sum(
                job["price"] for job in self.completed.values()
            ) / completed_jobs

        return {
            "total_jobs": total_jobs,
            "completed": completed_jobs,
            "avg_price": avg_price,
            "market_activity": "active" if total_jobs > 0 else "idle"
        }

    # ======================
    # HELPER
    # ======================
    def _get_agent(self, name):

        for a in self.agents:
            if a.name == name:
                return a

        raise ValueError("Agent not found")