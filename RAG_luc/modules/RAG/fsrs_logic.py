import math
from datetime import datetime, timedelta

class FSRS:
    def __init__(self):
        # Bộ tham số mặc định (Weights) của FSRS v4
        self.w = [
            0.4022, 1.1047, 2.8547, 21.4781, # Initial stability for 4 ratings
            5.1093, 1.3507, 0.9411, 0.0422,  # Stability updates
            1.619, 0.1117, 0.9361,           # Difficulty updates
            2.1323, 0.3128, 0.3412, 1.1468,  # Retrievability factors
            0.202, 2.6174                    # Bonus factors
        ]
        self.request_retention = 0.9  # Mục tiêu nhớ 90%

    def init_stability(self, rating):
        # rating: 1: Again, 2: Hard, 3: Good, 4: Easy
        return self.w[rating - 1]

    def init_difficulty(self, rating):
        return min(max(self.w[4] - self.w[5] * (rating - 3), 1), 10)

    def next_interval(self, stability):
        new_interval = stability * math.log(self.request_retention) / math.log(0.9)
        return max(1, round(new_interval))

    def step(self, rating, stability, difficulty, elapsed_days):
        # 1. Tính toán khả năng nhớ hiện tại (Retrievability)
        retrievability = math.pow(1 + elapsed_days / (9 * stability), -1)

        # 2. Cập nhật Độ khó (Difficulty)
        new_diff = difficulty - self.w[6] * (rating - 3)
        # Áp dụng Mean Reversion để tránh Difficulty bị cực đoan
        new_diff = self.w[7] * self.init_difficulty(3) + (1 - self.w[7]) * new_diff
        new_diff = min(max(new_diff, 1), 10)

        # 3. Cập nhật Độ ổn định (Stability)
        if rating == 1: # Again
            new_stab = self.w[8] * math.pow(difficulty, -self.w[9]) * (math.pow(stability + 1, self.w[10]) - 1) * math.exp((1 - retrievability) * self.w[11])
        else: # Hard, Good, Easy
            hard_penalty = self.w[12] if rating == 2 else 1
            easy_bonus = self.w[13] if rating == 4 else 1
            new_stab = stability * (1 + math.exp(self.w[14]) * (11 - new_diff) * math.pow(stability, -self.w[15]) * (math.exp((1 - retrievability) * self.w[16]) - 1) * hard_penalty * easy_bonus)

        return round(new_stab, 2), round(new_diff, 2)
