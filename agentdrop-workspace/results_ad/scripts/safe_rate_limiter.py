import time
from collections import defaultdict

class RateLimiter:
    """
    A simple token bucket or time-window rate limiter to prevent the $22K cloud bill scenario.
    """
    def __init__(self, max_requests, time_window_seconds):
        self.max_requests = max_requests
        self.time_window = time_window_seconds
        self.requests = defaultdict(list)

    def is_allowed(self, ip_address):
        current_time = time.time()
        # Clean up old requests
        self.requests[ip_address] = [
            req_time for req_time in self.requests[ip_address] 
            if current_time - req_time < self.time_window
        ]
        
        if len(self.requests[ip_address]) < self.max_requests:
            self.requests[ip_address].append(current_time)
            return True
        else:
            return False

if __name__ == "__main__":
    limiter = RateLimiter(max_requests=5, time_window_seconds=10)
    test_ip = "192.168.1.100"
    
    print("Simulating traffic...")
    for i in range(7):
        allowed = limiter.is_allowed(test_ip)
        print(f"Request {i+1}: {'Allowed' if allowed else 'Blocked (Rate Limited)'}")
        time.sleep(0.5)
