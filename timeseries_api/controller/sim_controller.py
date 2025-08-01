# sim_controller.py
class PlaybackController:
    def __init__(self):
        self.paused = True

    def play(self):
        self.paused = False

    def pause(self):
        self.paused = True

    def reset(self):
        self.paused = True

    def get_status(self):
        return {"paused": self.paused}
