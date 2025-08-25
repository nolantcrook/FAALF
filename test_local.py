import json
import requests

# Test the Lambda function
test_payload = {
    "task": "search the internet for hte latest AI news and summarize it",
    "execute": True
}

response = requests.post(
    "http://localhost:9000/2015-03-31/functions/function/invocations",
    headers={"Content-Type": "application/json"},
    json=test_payload
)

print("Status Code:", response.status_code)
print("Response Text:", response.text)
print("Response Headers:", dict(response.headers))

if response.status_code == 200:
    try:
        data = response.json()
    except:
        print("Failed to parse JSON response")
        exit(1)
else:
    print("Non-200 status code, exiting")
    exit(1)

if data.get("body"):
    body = json.loads(data["body"])
    
    print("Claude Output:", body.get("claude_output", ""))
    print("Claude Error:", body.get("claude_error", "")[:200] + "..." if body.get("claude_error") else "None")
    print("Execution Results:")
    for result in body.get("execution_results", []):
        print(f"  File: {result.get('file', 'unknown')}")
        if 'stdout' in result:
            print(f"  Stdout: {result['stdout']}")
            print(f"  Return Code: {result.get('return_code', 'N/A')}")
        if 'error' in result:
            print(f"  Error: {result['error']}")
else:
    # Direct response from HTTP server
    print("Claude Output:", data.get("claude_output", ""))
    print("Claude Error:", data.get("claude_error", "")[:200] + "..." if data.get("claude_error") else "None")
    print("Execution Results:")
    for result in data.get("execution_results", []):
        print(f"  File: {result.get('file', 'unknown')}")
        if 'stdout' in result:
            print(f"  Stdout: {result['stdout']}")
            print(f"  Return Code: {result.get('return_code', 'N/A')}")
        if 'error' in result:
            print(f"  Error: {result['error']}")