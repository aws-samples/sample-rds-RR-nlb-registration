import json
from typing import Any, Dict, List

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from common import logger, precondition

RETRY_CONFIG = Config(retries={"max_attempts": 3, "mode": "adaptive"})


class AwsServices:
    """
    Provides common methods to interact with AWS services (S3, ELBv2)
    """

    def __init__(self, region: str, bucket: str) -> None:
        precondition(region, "region is required")
        precondition(bucket, "bucket is required")

        self.s3 = boto3.resource("s3", region_name=region, config=RETRY_CONFIG)
        self.s3_client = boto3.client("s3", region_name=region, config=RETRY_CONFIG)
        self.elbv2 = boto3.client("elbv2", region_name=region, config=RETRY_CONFIG)
        self.region = region
        self.bucket = bucket

    def write_content_to_s3(self, content: str, object_key: str) -> None:
        """
        Adds an object to a bucket.
        :param content: bytes or seekable file-like object
        :param object_key: S3 object key
        :raises ClientError: on S3 API failure
        :raises BotoCoreError: on SDK-level failure
        """
        try:
            s3_object = self.s3.Object(self.bucket, object_key)
            s3_object.put(Body=content)
            logger.debug(
                f"Successfully wrote content to s3://{self.bucket}/{object_key}"
            )
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Failed to write to s3://{self.bucket}/{object_key}: {e}")
            raise

    def download_elb_ip_from_s3(self, object_key: str) -> Dict[str, Any]:
        """
        Download object from S3.
        :param object_key: S3 object key
        :return: Active or pending ELB node IP stored in S3
        :raises ClientError: on S3 API failure (except NoSuchKey)
        :raises json.JSONDecodeError: if state file content is not valid JSON
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=object_key)
            logger.info(f"Get {object_key} from S3 bucket - {self.bucket}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.info(
                    f"No state file at {object_key}. Expected on first invocation."
                )
                return {}
            raise
        try:
            return json.loads(response["Body"].read())
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted state file at {object_key}: {e}")
            raise

    def register_target(
        self, tg_arn: str, new_target_list: List[Dict[str, Any]]
    ) -> bool:
        """
        Register given targets to the given target group.
        :param tg_arn: ARN of target group
        :param new_target_list: list of targets
        :return: True if registration succeeded, False otherwise
        """
        logger.debug(f"Register new_target_list:{new_target_list}")
        is_registered = False
        try:
            self.elbv2.register_targets(TargetGroupArn=tg_arn, Targets=new_target_list)
            is_registered = True
        except ClientError as e:
            logger.error(
                f"Failed to register target to target group. "
                f"Targets: {new_target_list}. Target group: {tg_arn}. Error: {e}"
            )
        return is_registered

    def deregister_target(
        self, tg_arn: str, new_target_list: List[Dict[str, Any]]
    ) -> None:
        """
        Deregister given targets from the given target group.
        :param tg_arn: ARN of target group
        :param new_target_list: list of targets
        """
        logger.debug(f"Deregistering targets: {new_target_list}")
        try:
            self.elbv2.deregister_targets(
                TargetGroupArn=tg_arn, Targets=new_target_list
            )
        except ClientError as e:
            logger.error(
                f"Failed to deregister target from target group. "
                f"Targets: {new_target_list}. Target group: {tg_arn}. Error: {e}"
            )

    def get_ip_target_list_by_target_group_arn(self, tg_arn: str) -> List[str]:
        """
        Get a list of IP targets that are registered with the given target group.
        :param tg_arn: ARN of target group
        :return: list of target IP addresses
        :raises ClientError: if the DescribeTargetHealth API call fails
        """
        registered_ip_list: List[str] = []
        try:
            response = self.elbv2.describe_target_health(TargetGroupArn=tg_arn)
            for target in response["TargetHealthDescriptions"]:
                registered_ip_list.append(target["Target"]["Id"])
        except ClientError as e:
            logger.error(
                f"Failed to get target list from target group - {tg_arn}. Error: {e}"
            )
            raise

        logger.debug(
            f"ELB IPs that are currently registered with the target group: "
            f"{registered_ip_list}. Total IP count: {len(registered_ip_list)}"
        )
        return registered_ip_list
