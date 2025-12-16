import math

class WelfordState:
    def __init__(self):
        self.n = 0
        self.mean = 0.0
        self.M2 = 0.0  # Sum of squares of differences

    def update(self, x):
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        delta2 = x - self.mean
        self.M2 += delta * delta2

    @property
    def std_dev(self):
        if self.n < 2:
            return 0.0
        return math.sqrt(self.M2 / (self.n - 1))

    @property
    def z_score(self):
        # Returns function to calculate Z of current value x
        # Usage: state.z_score(current_price)
        return lambda x: (x - self.mean) / self.std_dev if self.std_dev > 0 else 0