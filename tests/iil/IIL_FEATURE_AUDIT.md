# IIL Feature Audit - Backend Endpoints vs UI vs Test Coverage

## Backend Endpoints (31) x UI Panels (11) x Existing Tests (114)

| # | Method | Endpoint | UI Panel | Test File | Tests | Gap |
|---|--------|----------|----------|-----------|:-----:|-----|
| 1 | POST | /search | SearchPanel | test_search.py | 8 | Need: rate limiting, special chars, long queries |
| 2 | GET | /search | SearchPanel | test_search.py | 4 | Need: concurrent queries |
| 3 | POST | /scrape | (no panel) | test_scrape.py | 7 | Need: redirects, timeout, encoding |
| 4 | GET | /scrape | (no panel) | test_scrape.py | 3 | Need: pagination |
| 5 | POST | /research | ResearchPanel | test_research.py | 7 | Need: multi-step, citation validation |
| 6 | POST | /verify | VerifyPanel | test_research.py | 5 | Need: edge cases |
| 7 | POST | /knowledge/ingest | KnowledgePanel | test_knowledge.py | 3 | Need: batch, dedup, conflict |
| 8 | POST | /knowledge/search | KnowledgePanel | test_knowledge.py | 2 | Need: relevance ranking, filters |
| 9 | GET | /knowledge/stats | KnowledgePanel | test_knowledge.py | 2 | Need: empty state |
| 10 | GET | /monitors | MonitorPanel | test_monitors.py | 3 | Need: filter, pagination |
| 11 | GET | /monitors/{id} | MonitorPanel | test_monitors.py | 2 | Good |
| 12 | POST | /monitors | MonitorPanel | test_monitors.py | 2 | Good |
| 13 | PUT | /monitors/{id} | MonitorPanel | test_monitors.py | 2 | Good |
| 14 | DELETE | /monitors/{id} | MonitorPanel | test_monitors.py | 2 | Good |
| 15 | POST | /monitors/{id}/check | MonitorPanel | test_monitors.py | 2 | Need: timeout, retry |
| 16 | POST | /monitors/check-all | MonitorPanel | test_monitors.py | 2 | Need: partial failure |
| 17 | GET | /cache/stats | (no panel) | test_cache_analytics.py | 1 | Need: detailed breakdown |
| 18 | POST | /cache/clear | (no panel) | test_cache_analytics.py | 3 | Good |
| 19 | POST | /security/scan | SecurityPanel | test_security.py | 5 | Need: multi-vector |
| 20 | POST | /security/domains/block | SecurityPanel | test_security.py | 1 | Need: pattern matching |
| 21 | POST | /security/domains/unblock | SecurityPanel | test_security.py | 1 | Good |
| 22 | POST | /browse | BrowsePanel | test_browse_ocr_robots.py | 6 | Need: multi-step, auth |
| 23 | POST | /ocr | OCRPanel | test_browse_ocr_robots.py | 8 | Need: multi-page PDF |
| 24 | POST | /robots-check | RobotsCheckerPanel | test_browse_ocr_robots.py | 8 | Need: complex patterns |
| 25 | GET | /debug/tables | DebugPanel | test_cache_analytics.py | 1 | Need: table listing |
| 26 | GET | /debug/tables/{table} | DebugPanel | test_cache_analytics.py | 6 | Good |
| 27 | GET | /analytics | AnalyticsDashboard | test_browse_ocr_robots.py | 1 | Need: time-series |
| 28 | GET | /analytics/config | AnalyticsDashboard | test_cache_analytics.py | 1 | Good |
| 29 | PUT | /analytics/config | AnalyticsDashboard | test_cache_analytics.py | 4 | Good |
| 30 | POST | /analytics/reset | AnalyticsDashboard | test_cache_analytics.py | 1 | Good |
| 31 | GET | /health | (no panel) | test_browse_ocr_robots.py | 1 | Good |

## Test Coverage Summary

| Category | Backend | UI | Tests | Coverage |
|----------|:-------:|:--:|:-----:|:--------:|
| Search | 2 | 1 | 12 | Good |
| Scrape | 2 | 0 | 12 | Good (no UI needed) |
| Research | 1 | 1 | 7 | Need more |
| Verify | 1 | 1 | 5 | Need more |
| Knowledge | 3 | 1 | 8 | Need more |
| Monitors | 7 | 1 | 16 | Good |
| Cache | 2 | 0 | 4 | Good |
| Security | 3 | 1 | 10 | Good |
| Browse | 1 | 1 | 6 | Good |
| OCR | 1 | 1 | 8 | Good |
| Robots | 1 | 1 | 8 | Good |
| Debug | 2 | 1 | 7 | Good |
| Analytics | 4 | 1 | 6 | Good |
| Health | 1 | 0 | 1 | Good |
| **TOTAL** | **31** | **11** | **114** | |

## Real-World Test Scenarios to Add

### Search (add ~5 tests)
- Search with special characters in query
- Search with very long query string
- Search with empty providers list
- Search with invalid time_range format
- Search with rate limiting response

### Scrape (add ~4 tests)
- Scrape with redirect chain (301->302->200)
- Scrape with timeout handling
- Scrape with non-UTF8 encoding
- Scrape with very large page (1MB+)

### Research (add ~4 tests)
- Research with minimum sources constraint
- Research with code and papers mixed
- Research deep dive with caching
- Verify with conflicting sources

### Knowledge (add ~5 tests)
- Ingest with duplicate content (dedup)
- Ingest with large content (chunking)
- Search with relevance ranking
- Search with category filter
- Stats after multiple ingests

### Monitors (add ~3 tests)
- Monitor check with timeout
- Check-all with partial failures
- Monitor with custom headers

### Security (add ~3 tests)
- Scan with multiple attack vectors
- Block with wildcard domain
- Scan with nested injection

### Integration Flow (add ~4 tests)
- Search -> Scrape -> Ingest flow
- Browse -> OCR -> Knowledge flow
- Monitor -> Security scan flow
- Research -> Verify -> Knowledge flow
