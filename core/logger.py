import time

class Logger:

    def log(self, tag, data):
        print(f"\n[{tag}] {time.strftime('%H:%M:%S')}")
        print(data)
        print("-" * 40)