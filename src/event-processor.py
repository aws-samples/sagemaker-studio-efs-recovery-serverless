import json
import boto3
import argparse
import os
from common import profile as p
from common import users as u
from common import users_history as hist
import logging
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    if 'detail' not in event:
        logger.error(f"Expected key detail in input payload but didn't exist")
        raise ValueError(f"Invalid event format: {event}")
    event = json.loads(json.dumps(event['detail']))
    logger.info(f"event detail: {event}")
    domain_id = event['requestParameters']['domainId']
    profile_name = event['requestParameters']['userProfileName']
    role_name = event['requestParameters']['userSettings']['executionRole'].rsplit("/")[-1]
    logger.info(f"Create UserProfile event detected with domain {domain_id} userprofile {profile_name} role {role_name}")
    profile = p.Profile(
        domain_id=domain_id,
        sm_client=boto3.client('sagemaker'),
        profile_name=profile_name,
        role_name=role_name
    )
    logger.info(f"""Built profile: user {profile.name}\
    role_name {profile.role}\
    domain_id {profile.domain_id}\
    home_efs_id {profile.efs_sys_id}\
    efs_uid {profile.efs_uid}""")
    users = u.Users(
        ddb_resource=boto3.resource('dynamodb'),
        table_name=os.getenv('USERTABLE', 'studioUser')
    )
    users_hist = hist.UsersHistory(
        ddb_resource=boto3.resource('dynamodb'),
        table_name=os.getenv('HISTORYTABLE', 'studioUserHistory')
    )
    logger.info(f"update table {users.table.name}")
    response = users.update_user(
        key={
            os.getenv('HASHKEY', 'username'): profile_name,
            os.getenv('RANGEKEY', 'role_name'): role_name
        },
        expression="set domain_id = :d, efs_sys_id =:es, efs_uid = :eu",
        attributes={
            ":d": domain_id,
            ":es": profile.efs_sys_id,
            ":eu": profile.efs_uid
        },
        ret_val='ALL_NEW'
    )
    logger.debug(f"update table {users.table.name} respose: {response}")
    logger.info(f"append to table {users_hist.table.name}")
    users_hist.put_user(
        item={
            os.getenv('HASHKEY_HIST', 'username'): profile_name,
            os.getenv('RANGEKEY_HIST', 'epoctime'): int(time.time() * 1000),
            "role_name": role_name,
            "domain_id": domain_id,
            "efs_sys_id": profile.efs_sys_id,
            "efs_uid": profile.efs_uid}
    )
    logger.info("Done")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-domain-id",
        "--domain-id",
        dest="domain_id",
        type=str,
        default="d-ozw90syuk8in"
    )
    parser.add_argument(
        "-region",
        "--region",
        dest="region",
        type=str,
        default='us-east-2'
    )
    parser.add_argument(
        "-profile-name",
        "--profile-name",
        dest="profile_name",
        type=str,
        default='user1'
    )
    parser.add_argument(
        "-role-name",
        "--role-name",
        dest="role_name",
        type=str,
        default='AmazonSageMaker-ExecutionRole-endtoendml'
    )
    args = parser.parse_args()
    event = {
        'detail-type': 'AWS API Call via CloudTrail',
        'source': 'aws.sagemaker',
        'region': args.region,
        'detail': {
            'eventSource': 'sagemaker.amazonaws.com',
            'eventName': 'CreateUserProfile',
            'awsRegion': args.region,
            'requestParameters': {
                'domainId': args.domain_id,
                'userProfileName': args.profile_name,
                'userSettings': {
                    'executionRole': args.role_name
                }
            }
        }
    }
    os.environ['AWS_DEFAULT_REGION'] = args.region
    lambda_handler(event, {})


