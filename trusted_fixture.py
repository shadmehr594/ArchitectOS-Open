class Calculator:
    def __init__(self):
        self.operand1 = 0
    def on_digit(self, digit):
        self.operand1 = self.operand1 * 10 + int(digit)