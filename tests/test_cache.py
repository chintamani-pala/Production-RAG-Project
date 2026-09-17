# pyrefly: ignore [missing-import]
import sys
import time
from app.cache import ResponseCache

# ANSI Escape Sequences for colorful output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(title: str):
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*60}")
    print(f" {title}")
    print(f"{'='*60}{Colors.RESET}")

def print_sub_header(title: str):
    print(f"\n{Colors.MAGENTA}--- {title} ---{Colors.RESET}")

def print_result(passed: bool, message: str):
    if passed:
        print(f"  {Colors.BOLD}Result:{Colors.RESET} {Colors.GREEN}PASS{Colors.RESET} - {message}")
    else:
        print(f"  {Colors.BOLD}Result:{Colors.RESET} {Colors.RED}FAIL{Colors.RESET} - {message}")

def test_cache():
    print_header("Response Cache Functionality Demonstration")
    
    total_tests = 0
    passed_tests = 0

    def run_test(name, passed, message):
        nonlocal total_tests, passed_tests
        total_tests += 1
        print(f"\n{Colors.BLUE}Test #{total_tests}:{Colors.RESET} {name}")
        print_result(passed, message)
        if passed:
            passed_tests += 1

    # Initialize a cache with a short TTL for testing
    cache = ResponseCache(ttl_seconds=2)
    
    print_sub_header("1. Basic Set and Get (Cache Miss vs Cache Hit)")
    
    query1 = "What is the capital of France?"
    response1 = {"text": "The capital of France is Paris."}
    
    # Try to get before setting
    miss_result = cache.get(query1)
    run_test("Initial Get (Should be Miss)", 
             miss_result is None, 
             "Cache correctly returned None for uncached query.")
    
    # Set the value
    cache.set(query1, response1)
    
    # Try to get after setting
    hit_result = cache.get(query1)
    run_test("Get after Set (Should be Hit)", 
             hit_result == response1, 
             "Cache successfully returned the stored response.")

    print_sub_header("2. Query Normalization (Case and Whitespace)")
    
    query2_variations = [
        "What is Python?",
        "what is python?",
        "  What is Python?  ",
        "WHAT IS PYTHON?"
    ]
    response2 = {"text": "Python is a programming language."}
    
    # Set with the first variation
    cache.set(query2_variations[0], response2)
    
    # Verify we can retrieve it using ALL other variations
    normalization_passed = True
    for q in query2_variations[1:]:
        if cache.get(q) != response2:
            normalization_passed = False
            break
            
    run_test("Retrieve using different cases/spaces", 
             normalization_passed, 
             "Cache successfully normalized all variations to the same key.")

    print_sub_header("3. Cache Statistics Tracking")
    
    stats = cache.stats
    # We had 1 miss initially, then 1 hit for query1, then 3 hits for query2 variations = 4 hits total
    # Cached entries should be 2 (query1 and query2)
    stats_passed = (stats['hits'] == 4 and stats['misses'] == 1 and stats['cached_entries'] == 2)
    
    run_test("Check if hits/misses are counted correctly", 
             stats_passed, 
             f"Stats verified: Hits={stats['hits']}, Misses={stats['misses']}, Hit Rate={stats['hit_rate']:.1f}%")

    print_sub_header("4. Time-To-Live (TTL) Expiration")
    
    # Set a new value with a fast-expiring cache
    fast_cache = ResponseCache(ttl_seconds=1)
    fast_cache.set("temporary query", {"data": "temp"})
    
    # Retrieve immediately
    immediate_get = fast_cache.get("temporary query") is not None
    run_test("Immediate retrieval before TTL expires", 
             immediate_get, 
             "Successfully retrieved item immediately.")
             
    print(f"  {Colors.YELLOW}Waiting for 1.5 seconds for cache to expire...{Colors.RESET}")
    time.sleep(1.5)
    
    # Retrieve after TTL
    expired_get = fast_cache.get("temporary query") is None
    run_test("Retrieval after TTL expires (Should be Miss)", 
             expired_get, 
             "Cache successfully removed the expired item.")
             
    stats_after_expire = fast_cache.stats
    run_test("Stats reflect expired item removal",
             stats_after_expire['cached_entries'] == 0,
             f"Cached entries count dropped to {stats_after_expire['cached_entries']}")

    print_header(f"Final Results: {passed_tests}/{total_tests} Tests Passed")

if __name__ == "__main__":
    test_cache()
