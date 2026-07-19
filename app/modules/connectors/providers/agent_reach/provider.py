import sys
import os
import subprocess
import logging
import time
import httpx
from typing import Any, Dict
from ..base import BaseConnectorProvider
from common_lib.modules.plugins.connectors.exceptions import ExecutionError
from common_lib.modules.plugins.connectors.models.connection import Connection

logger = logging.getLogger(__name__)


def _get_executable(name: str) -> str:
    py_dir = os.path.dirname(sys.executable)
    exe_name = f"{name}.exe" if sys.platform == "win32" else name
    local_path = os.path.join(py_dir, exe_name)
    if os.path.exists(local_path):
        return local_path
    return name


class Provider(BaseConnectorProvider):
    provider_id = "agent-reach"

    def execute(
        self,
        tool_id: str,
        params: Dict[str, Any],
        connection: Connection,
        form_data: Dict[str, Any],
    ) -> Any:
        start_time = time.monotonic()
        
        # Extracted credentials / proxy
        cookies = form_data.get("cookies", "")
        proxy = form_data.get("proxy_url", "")
        
        # Prepare subprocess environment
        env = dict(os.environ)
        if cookies:
            env["AGENT_REACH_COOKIES"] = cookies
        if proxy:
            env["HTTP_PROXY"] = proxy
            env["HTTPS_PROXY"] = proxy

        try:
            if tool_id == "agent_reach.web_search":
                query = params.get("query", "")
                num_results = params.get("num_results", 5)
                # Call Jina Search API (free, no API key needed, returns markdown)
                headers = {"X-With-Links-Summary": "true"}
                url = f"https://s.jina.ai/{query}"
                with httpx.Client(timeout=30) as client:
                    resp = client.get(url, headers=headers)
                    resp.raise_for_status()
                    return {"result": resp.text}

            elif tool_id == "agent_reach.read_url":
                url = params.get("url", "")
                # Call Jina Reader API (free, returns clean markdown of any URL)
                reader_url = f"https://r.jina.ai/{url}"
                with httpx.Client(timeout=30) as client:
                    resp = client.get(reader_url)
                    resp.raise_for_status()
                    return {"result": resp.text}

            elif tool_id == "agent_reach.search_social":
                platform = params.get("platform", "")
                query = params.get("query", "")
                limit = params.get("limit", 10)

                if platform == "v2ex":
                    # Call V2EX public hot topics endpoint
                    with httpx.Client(timeout=15) as client:
                        resp = client.get("https://www.v2ex.com/api/topics/hot.json", headers={"User-Agent": "agent-reach/1.0"})
                        resp.raise_for_status()
                        topics = resp.json()
                        filtered = [t for t in topics if query.lower() in t.get("title", "").lower() or query.lower() in t.get("content", "").lower()]
                        return {"topics": filtered[:limit]}

                elif platform == "bilibili":
                    cmd = [_get_executable("bili"), "search", query, "--type", "video", "-n", str(limit)]
                    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
                    return {"stdout": res.stdout, "stderr": res.stderr}

                elif platform == "twitter":
                    cmd = [_get_executable("twitter"), "search", query, "-n", str(limit)]
                    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
                    return {"stdout": res.stdout, "stderr": res.stderr}

                elif platform == "reddit":
                    cmd = [_get_executable("rdt"), "search", query, "--limit", str(limit)]
                    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
                    return {"stdout": res.stdout, "stderr": res.stderr}

                elif platform == "xiaohongshu":
                    cmd = [_get_executable("xhs"), "search", query]
                    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
                    return {"stdout": res.stdout, "stderr": res.stderr}

                else:
                    raise ExecutionError(f"Social search platform '{platform}' not supported via subprocess")

            elif tool_id == "agent_reach.get_youtube_transcript":
                url = params.get("url", "")
                # Create a temp output file name
                import tempfile
                with tempfile.TemporaryDirectory() as tmpdir:
                    out_template = os.path.join(tmpdir, "%(id)s")
                    cmd = [_get_executable("yt-dlp"), "--write-sub", "--skip-download", "-o", out_template, url]
                    subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
                    
                    # Read the generated subtitle files if any
                    subs = []
                    for f in os.listdir(tmpdir):
                        fpath = os.path.join(tmpdir, f)
                        if os.path.isfile(fpath):
                            with open(fpath, "r", encoding="utf-8", errors="ignore") as subfile:
                                subs.append(subfile.read())
                    if subs:
                        return {"transcript": "\n".join(subs)}
                    return {"error": "No subtitles or transcript found for the video"}

            elif tool_id == "agent_reach.read_social_user":
                platform = params.get("platform", "")
                username = params.get("username", "")

                if platform == "twitter":
                    cmd = [_get_executable("twitter"), "user-posts", f"@{username}", "-n", "10"]
                    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
                    return {"stdout": res.stdout, "stderr": res.stderr}
                
                elif platform == "instagram":
                    cmd = [_get_executable("opencli"), "instagram", "user", username, "-f", "yaml"]
                    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
                    return {"stdout": res.stdout, "stderr": res.stderr}
                
                elif platform == "github":
                    cmd = [_get_executable("gh"), "search", "repos", f"owner:{username}", "--limit", "10"]
                    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
                    return {"stdout": res.stdout, "stderr": res.stderr}

                else:
                    raise ExecutionError(f"User read platform '{platform}' not supported via subprocess")

            else:
                raise ExecutionError(f"Tool ID '{tool_id}' not found on agent-reach provider")

        except subprocess.TimeoutExpired as te:
            raise ExecutionError(f"Subprocess execution timed out: {te}")
        except Exception as e:
            raise ExecutionError(f"Agent Reach execution failed: {e}")
