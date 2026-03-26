import numpy as np


class HitBuffer:
    def __init__(self, window=5):
        self.window = window
        self.buf = []

    def push(self, hit: int):
        self.buf.append(1 if hit else 0)
        if len(self.buf) > self.window:
            self.buf.pop(0)

    def sum(self) -> int:
        return int(np.sum(self.buf))

    def reset(self):
        self.buf = []
