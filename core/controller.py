class BrainController:

    def __init__(self, bim_engine, comfy_client):
        self.bim = bim_engine
        self.comfy = comfy_client

    def route(self, user_input):

        if "draw" in user_input or "image" in user_input:
            return self.comfy.generate(user_input)

        if "house" in user_input or "floor" in user_input:
            return self.bim.generate(user_input)

        return {"type": "chat", "msg": "unknown request"}