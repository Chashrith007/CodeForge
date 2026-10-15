from runner import OUTPUT_LIMIT, run_code

result = run_code("print('x' * 20000)")

print("Status:", result["status"])
print("Stored bytes:", len(result["output"].encode("utf-8")))
print("Allowed bytes:", OUTPUT_LIMIT)