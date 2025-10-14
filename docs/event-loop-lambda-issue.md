# Event Loop Issues in AWS Lambda with Async Python

## Problem Statement

When deploying async Python applications (FastAPI, Flask with async, etc.) to AWS Lambda using ASGI adapters like Mangum, you may encounter the following error:

```
RuntimeError: There is no current event loop in thread 'MainThread'
```

This occurs even though your application works perfectly in local development.

## Root Cause

### Understanding the Event Loop Lifecycle

Python's `asyncio` event loop has a specific lifecycle:

1. **Create** an event loop
2. **Run** async tasks within that loop
3. **Close** the event loop when done

The issue arises when you use `asyncio.run()` at the **module level** (during import):

```python
# ❌ PROBLEMATIC CODE - Module level
import asyncio

async def fetch_data():
    return await some_api_call()

# This runs during import
DATA = asyncio.run(fetch_data())  # Creates loop → Runs task → CLOSES loop
```

### Why This Breaks Lambda

**In Local Development (uvicorn/gunicorn):**
```
1. Module imported → asyncio.run() creates & closes loop
2. Uvicorn starts → Creates NEW event loop for requests
3. Everything works ✅
```

**In AWS Lambda (Mangum):**
```
1. Module imported → asyncio.run() creates & closes loop
2. Lambda handler invoked → Mangum tries to use existing loop
3. ERROR: No loop exists (it was closed in step 1) ❌
```

### Technical Details

- `asyncio.run()` is designed for **script entry points**, not library/module initialization
- It creates a new loop, runs the coroutine, then **closes and cleans up** the loop
- Mangum expects to **manage the event loop** for the entire Lambda lifecycle
- When Mangum calls `asyncio.get_event_loop()`, it finds no loop because the one created by `asyncio.run()` was already closed

## Real-World Example

### The Problem Code

```python
# api_server.py
import asyncio
from prompt_service import PromptService

# Module-level initialization
prompt_service = PromptService()

# ❌ THIS CAUSES THE ISSUE
async def fetch_prompt():
    return await prompt_service.get_prompt(id=2)

PROMPT_TEXT = asyncio.run(fetch_prompt())  # Closes event loop!

# ... rest of FastAPI app
from mangum import Mangum
handler = Mangum(app)  # Mangum expects to control the loop
```

**What happens:**
1. ✅ Lambda container starts, imports `api_server.py`
2. ✅ `asyncio.run(fetch_prompt())` executes successfully
3. ❌ Event loop is **closed** after fetching prompt
4. ❌ Request arrives → Mangum tries to handle it → **No event loop exists**

### Error Traceback

```
[ERROR] RuntimeError: There is no current event loop in thread 'MainThread'.
Traceback (most recent call last):
  File "/var/lang/lib/python3.12/site-packages/mangum/protocols/http.py", line 46, in __call__
    loop = asyncio.get_event_loop()  # ← FAILS HERE
  File "/var/lang/lib/python3.12/asyncio/events.py", line 702, in get_event_loop
    raise RuntimeError('There is no current event loop in thread %r.'
```

## Solutions

### Solution 1: Lazy Loading (Recommended)

Load data on first use within an async context:

```python
# ✅ CORRECT - Lazy loading
import asyncio
from prompt_service import PromptService

prompt_service = PromptService()
PROMPT_TEXT = None
PROMPT_LOADED = False

async def load_prompt_if_needed():
    """Load prompt on first use (within async context)"""
    global PROMPT_TEXT, PROMPT_LOADED

    if PROMPT_LOADED:
        return

    try:
        # This runs WITHIN Mangum's event loop
        PROMPT_TEXT = await prompt_service.get_prompt(id=2)
        print("✅ Prompt loaded dynamically")
    except Exception as e:
        print(f"❌ Error loading prompt: {e}")
        PROMPT_TEXT = "Fallback value"
    finally:
        PROMPT_LOADED = True

# In your endpoint
@app.post("/summarize")
async def summarize(data: dict):
    await load_prompt_if_needed()  # Load on first request
    # ... use PROMPT_TEXT
```

**Benefits:**
- ✅ No event loop conflicts
- ✅ Faster Lambda cold starts (no API call during init)
- ✅ Still uses async API calls
- ✅ Automatic caching after first load

### Solution 2: Synchronous Loading

Use sync HTTP libraries at module level:

```python
# ✅ CORRECT - Sync loading
import requests  # Not async

# This is fine - no event loop needed
PROMPT_TEXT = requests.get(
    "https://api.example.com/prompts/2"
).json()['text']

from mangum import Mangum
handler = Mangum(app)  # No conflicts
```

**Trade-offs:**
- ✅ Simple and straightforward
- ✅ No event loop issues
- ❌ Blocks during cold start (slower initialization)
- ❌ Can't use async features (connection pooling, etc.)

### Solution 3: File-Based Fallback

Load from files instead of API:

```python
# ✅ CORRECT - File loading
import os

# No event loop needed
prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "default.txt")
with open(prompt_path, 'r') as f:
    PROMPT_TEXT = f.read()

from mangum import Mangum
handler = Mangum(app)  # No conflicts
```

**Benefits:**
- ✅ Fastest initialization
- ✅ No external dependencies
- ✅ No event loop issues
- ❌ Less dynamic (requires redeployment to change)

### Solution 4: Lambda Layers with Pre-initialized Data

For expensive computations:

```python
# ✅ CORRECT - Pre-computed in Lambda Layer
# Layer build script (runs once during layer creation)
import json

data = expensive_computation()  # Run during layer build
with open('/opt/python/data.json', 'w') as f:
    json.dump(data, f)

# Lambda function (uses pre-computed data)
with open('/opt/python/data.json', 'r') as f:
    DATA = json.load(f)  # Fast, sync, no API calls
```

## Best Practices

### ✅ DO

1. **Use lazy loading for API calls**
   ```python
   async def load_if_needed():
       global DATA
       if not DATA:
           DATA = await fetch_from_api()
   ```

2. **Use sync libraries at module level**
   ```python
   import requests  # Not aiohttp
   DATA = requests.get(url).json()
   ```

3. **Load from files when possible**
   ```python
   with open('config.json') as f:
       CONFIG = json.load(f)
   ```

4. **Use Lambda environment variables**
   ```python
   API_KEY = os.getenv('API_KEY')  # Set in Lambda config
   ```

### ❌ DON'T

1. **Never use `asyncio.run()` at module level**
   ```python
   # ❌ BAD
   DATA = asyncio.run(fetch_data())
   ```

2. **Don't create new event loops manually**
   ```python
   # ❌ BAD
   loop = asyncio.new_event_loop()
   asyncio.set_event_loop(loop)
   DATA = loop.run_until_complete(fetch_data())
   ```

3. **Don't use `asyncio.get_event_loop()` at module level**
   ```python
   # ❌ BAD (no loop exists yet)
   loop = asyncio.get_event_loop()
   ```

## When Does This Apply?

### Affected Scenarios

✅ **This guide applies to:**
- AWS Lambda with async Python frameworks (FastAPI, Quart, etc.)
- Using ASGI adapters (Mangum, aws-lambda-adapter)
- Any serverless platform with similar lifecycle (Google Cloud Functions, Azure Functions)
- Applications that need initialization with async operations

❌ **This guide does NOT apply to:**
- Traditional servers (uvicorn, gunicorn) - they manage their own loops
- Fully synchronous applications (no async/await)
- Standalone scripts (where `asyncio.run()` is the correct pattern)

## Debugging Tips

### Check if You Have This Issue

Look for these patterns in your code:

```bash
# Search for asyncio.run at module level
grep -n "asyncio.run" *.py | grep -v "def \|class "

# Search for manual loop creation
grep -n "new_event_loop\|set_event_loop" *.py
```

### Verify the Fix

1. **Check Lambda logs for initialization**
   ```bash
   aws logs tail /aws/lambda/your-function --region us-east-1
   ```

2. **Look for successful lazy loading**
   ```
   ✅ Lambda handler configured with Mangum
   START RequestId: xxx
   ✅ Loaded data dynamically
   END RequestId: xxx
   ```

3. **Test cold start behavior**
   ```bash
   # Force cold start by updating environment variable
   aws lambda update-function-configuration \
       --function-name your-function \
       --environment Variables="{TEST=1}"

   # Wait for update
   sleep 10

   # Test endpoint
   curl https://your-api.execute-api.us-east-1.amazonaws.com/health
   ```

## Common Pitfalls

### Pitfall 1: Hidden `asyncio.run()` in Libraries

Some libraries use `asyncio.run()` internally:

```python
# Check library source
import inspect
print(inspect.getsource(library.initialize))

# If it uses asyncio.run(), consider:
# 1. Lazy loading the library
# 2. Using a sync alternative
# 3. Contributing a fix to the library
```

### Pitfall 2: Module Import Side Effects

```python
# ❌ BAD - Module import has side effects
# config.py
DATA = asyncio.run(fetch_config())  # Runs on import!

# main.py
import config  # ← This triggers the asyncio.run()
```

**Fix:** Make initialization explicit:

```python
# ✅ GOOD
# config.py
DATA = None

async def init():
    global DATA
    DATA = await fetch_config()

# main.py
import config
# Later, in an async context:
await config.init()
```

### Pitfall 3: Testing vs Production

Tests might pass while production fails:

```python
# test.py
def test_endpoint():
    # pytest-asyncio handles event loop
    response = client.get("/endpoint")  # Works!

# But in Lambda:
# ERROR: No event loop
```

**Solution:** Test with Lambda emulators (SAM Local, LocalStack)

## Performance Considerations

### Cold Start Impact

| Approach | Cold Start Time | Pros | Cons |
|----------|----------------|------|------|
| **Lazy Loading** | +50-200ms on first request | Dynamic, async-friendly | Slightly slower first request |
| **Sync Loading** | +100-500ms at init | Simple | Blocks initialization |
| **File Loading** | +1-10ms at init | Fastest | Static data only |
| **Lambda Layers** | +1-5ms at init | Pre-computed | Deployment complexity |

### Recommendation by Use Case

- **Configuration data**: File loading or environment variables
- **API-fetched prompts**: Lazy loading
- **ML models**: Lambda layers with pre-loaded data
- **Database connections**: Lazy loading with connection pooling

## Related Issues

This pattern also affects:

1. **Database connections** with async drivers (asyncpg, motor)
2. **HTTP client initialization** (aiohttp ClientSession)
3. **Cache warmup** (Redis, Memcached with async)
4. **ML model loading** with async I/O

Same solution applies: **Lazy load within async context**.

## References

- [Python asyncio Documentation](https://docs.python.org/3/library/asyncio.html)
- [Mangum Documentation](https://mangum.io/)
- [AWS Lambda Python Runtime](https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html)
- [FastAPI Deployment Best Practices](https://fastapi.tiangolo.com/deployment/)

## Conclusion

**Key Takeaway:** Never use `asyncio.run()` or create event loops at module level in Lambda applications. Instead, use lazy loading within async endpoint handlers.

This pattern ensures compatibility with ASGI adapters while maintaining clean, async Python code.

---

**Last Updated:** 2025-10-14
**Applies To:** Python 3.7+, AWS Lambda, Mangum, FastAPI, async frameworks
