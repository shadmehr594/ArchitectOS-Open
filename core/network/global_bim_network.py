import uuid


class GlobalBIMNetwork:

    def __init__(self):
        self.nodes = {}
        self.global_models = {}

    # ======================
    # REGISTER NODE
    # ======================
    def register_node(self, name, location):

        node_id = str(uuid.uuid4())

        self.nodes[node_id] = {
            "name": name,
            "location": location,
            "models": []
        }

        return node_id

    # ======================
    # UPLOAD BIM MODEL
    # ======================
    def upload_model(self, node_id, model):

        model_id = str(uuid.uuid4())

        self.global_models[model_id] = {
            "data": model,
            "owner": node_id,
            "version": 1
        }

        self.nodes[node_id]["models"].append(model_id)

        return model_id

    # ======================
    # SHARE MODEL
    # ======================
    def share_model(self, model_id, target_node_id):

        if model_id not in self.global_models:
            return {"error": "model not found"}

        shared_copy = {
            "data": self.global_models[model_id]["data"],
            "shared_from": self.global_models[model_id]["owner"]
        }

        self.nodes[target_node_id]["models"].append(model_id)

        return shared_copy

    # ======================
    # GLOBAL SEARCH
    # ======================
    def search_models(self, keyword):

        return [
            m for m in self.global_models.values()
            if keyword.lower() in str(m["data"]).lower()
        ]

    # ======================
    # NETWORK STATS
    # ======================
    def stats(self):

        return {
            "nodes": len(self.nodes),
            "models": len(self.global_models),
            "status": "global_bim_network_active"
        }