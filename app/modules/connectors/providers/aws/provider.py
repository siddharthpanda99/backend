from typing import Any, Dict

from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "aws"
    display_name = "AWS"
    base_url = ""
    endpoints = {
        "aws.s3_list_buckets": ("GET", "/"),
        "aws.s3_list_objects": ("GET", "/{bucket}"),
        "aws.ec2_describe_instances": ("POST", "/"),
    }

    def get_base_url(self, form_data: Dict[str, Any]) -> str:
        return f"https://s3.{form_data.get('region', 'us-east-1')}.amazonaws.com"
