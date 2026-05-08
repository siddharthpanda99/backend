# Fix 500 Error in Memory Dashboard Stats API

The `/api/v1/memory/dashboard/stats` endpoint is currently throwing a 500 Internal Server Error because the asynchronous call to `service.get_stats()` is not being awaited. This results in a coroutine object being passed to the `APIResponse` Pydantic model, which triggers a validation error.

## Proposed Changes

### Backend Components

#### [MODIFY] [index.py](file:///c:/Users/91797/Documents/Dev/JS/Monorepo/Backend%20Monorepo/Backend/app/modules/memories/routes/index.py)
- Add `await` to the `service.get_stats()` call in the `get_dashboard_stats` handler.

#### [MODIFY] [test_memory_service.py](file:///c:/Users/91797/Documents/Dev/JS/Monorepo/Backend%20Monorepo/Backend/scratch/test_memory_service.py)
- Add `await` to the `service.get_stats()` call in the test script to ensure it correctly prints stats instead of a coroutine object.

## Verification Plan

### Automated Tests
- Run the updated `scratch/test_memory_service.py` using the virtual environment's python.
- Verify that stats are printed as a dictionary and no `RuntimeWarning` is issued.

### Manual Verification
- Test the API endpoint `/api/v1/memory/dashboard/stats` (if possible, or simulate the call).
