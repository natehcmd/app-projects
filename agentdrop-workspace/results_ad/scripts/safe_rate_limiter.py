import time
from collections import defaultdict

class RateLimiter:
    """
    A simple token bucket or time-window rate limiter to prevent the $22K cloud bill scenario.
    """
    def __init__(self, max_requests, time_window_seconds, prune_interval_seconds=None, prune_size_threshold=1000):
        self.max_requests = max_requests
        self.time_window = time_window_seconds
        self.requests = defaultdict(list)
        # Entries for an IP were previously only pruned when that IP made a
        # new request, so IPs that hit once and never return grow the dict
        # forever. Sweep periodically (by wall-clock interval, default 10x
        # the window) or once the dict gets large, whichever comes first.
        self.prune_interval = prune_interval_seconds or (time_window_seconds * 10)
        self.prune_size_threshold = prune_size_threshold
        self._last_prune = time.time()

    def _prune_all_stale(self, current_time):
        """Remove every IP whose requests have all aged out of the window."""
        stale_ips = [
            ip for ip, times in self.requests.items()
            if not any(current_time - t < self.time_window for t in times)
        ]
        for ip in stale_ips:
            del self.requests[ip]
        self._last_prune = current_time

    def is_allowed(self, ip_address):
        current_time = time.time()

        # Periodic/size-triggered full sweep so IPs that never come back
        # don't leak memory forever.
        if (current_time - self._last_prune >= self.prune_interval
                or len(self.requests) >= self.prune_size_threshold):
            self._prune_all_stale(current_time)

        # Clean up old requests
        self.requests[ip_address] = [
            req_time for req_time in self.requests[ip_address]
            if current_time - req_time < self.time_window
        ]
        if not self.requests[ip_address]:
            del self.requests[ip_address]

        if len(self.requests.get(ip_address, [])) < self.max_requests:
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
