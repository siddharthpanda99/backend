from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "github"
    display_name = "GitHub"
    base_url = "https://api.github.com"
    endpoints = {
        "github.list_repos": ("GET", "/user/repos"),
        "github.get_repo": ("GET", "/repos/{owner}/{repo}"),
        "github.list_issues": ("GET", "/repos/{owner}/{repo}/issues"),
        "github.create_issue": ("POST", "/repos/{owner}/{repo}/issues"),
        "github.list_pull_requests": ("GET", "/repos/{owner}/{repo}/pulls"),
    }
