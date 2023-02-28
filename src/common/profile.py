import json
import string
import boto3
from typing import Mapping
from botocore.exceptions import ClientError, ParamValidationError
import logging
import argparse

logger = logging.getLogger(__name__)
logger.setLevel('ERROR')

class Profile:
    def __init__(self, domain_id: string, profile_name: string, role_name: string, sm_client):
        self.client = sm_client
        self.name = profile_name
        self.role = role_name
        self.domain_id = domain_id
        self.efs_uid = ''
        self.efs_sys_id = ''
        self.metadata = None
        self.error = False
        # run build
        self.build_profile()

    def build_profile(self):
        domain = self.get_domain_metadata()
        logger.debug(f"studio domain metadata: {domain}")
        self.efs_sys_id = domain["HomeEfsFileSystemId"]
        logger.debug(f"HomeEfsFileSystemId:{self.efs_sys_id}")
        users_mata = self.get_user_metadata()
        if not(users_mata):
            logging.warning("whoopsie")
            return
        logger.debug(f"userprofile metadata:{users_mata}")
        self.efs_uid = users_mata['HomeEfsFileSystemUid']
        logger.debug(f"HomeEfsFileSystemUid:{self.efs_sys_id}")

    def get_domain_metadata(self) -> Mapping[str, str]:
        try:
            response = self.client.describe_domain(
                DomainId=self.domain_id
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationException':
                logger.error(
                    f"Could not get domain {self.domain_id} metadata: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
            self.error = True
            return
        return response

    def get_user_metadata(self) -> Mapping:
        try:
            response = self.client.describe_user_profile(
                DomainId=self.domain_id,
                UserProfileName=self.name
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationException':
                logger.error(
                    f"Could not get UserProfile {self.name} metadata: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
            elif e.response['Error']['Code'] == 'AccessDeniedException':
                logger.error(
                    f"Could not get UserProfile {self.name} metadata because access denied for DescribeUserProfile: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
            self.error = True
            return
        return response

def run_question(sm_client, args):
    print('-' * 50)
    profile = Profile(
        domain_id=args.domain_id,
        sm_client=sm_client,
        profile_name=args.profile_name,
        role_name=args.role_name
    )
    print(f"""user: {profile.name} \n
    role_name  : {profile.role} \n
    domain_id  : {profile.domain_id} \n
    home_efs_id: {profile.efs_sys_id} \n
    efs_uid    : {profile.efs_uid}""")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-domain-id",
        "--domain-id",
        dest="domain_id",
        type=str,
        description="sagemaker studio domain id"
    )
    parser.add_argument(
        "-region",
        "--region",
        dest="region",
        type=str,
        description="aws region name"
    )
    parser.add_argument(
        "-profile-name",
        "--profile-name",
        dest="profile_name",
        type=str,
        description="sagemaker userprofile name"
    )
    parser.add_argument(
        "-role-name",
        "--role-name",
        dest="role_name",
        type=str,
        description="sagemaker notebook execution role name"
    )
    args = parser.parse_args()
    run_question(boto3.client('sagemaker', args.region), args)