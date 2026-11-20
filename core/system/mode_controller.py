class ModeController:

    def __init__(self):
        self.online = True

    def switch_offline(self):
        self.online = False
        return "OFFLINE MODE"

    def switch_online(self):
        self.online = True
        return "ONLINE MODE"

    def status(self):
        return {"online": self.online}