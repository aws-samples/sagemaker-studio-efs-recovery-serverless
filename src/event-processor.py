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
    domain_id = event.get('requestParameters')['domainId']
    profile_name = event.get('requestParameters').get('userProfileName')
    space_name = event.get('requestParameters').get('spaceName')
    if profile_name:
        role_name = event.get('requestParameters').get('userSettings')['executionRole'].rsplit("/")[-1]
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
    elif space_name:
        role_name = ""
        logger.info(f"Create Space event detected with domain {domain_id} space {space_name}")
        profile = p.Profile(
            domain_id=domain_id,
            sm_client=boto3.client('sagemaker'),
            space_name=space_name
        )
        logger.info(f"""Built profile: space {profile.space}\
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
            os.getenv('HASHKEY', "profile_name"): profile.name + profile.space, #either one is empty string,
            os.getenv('RANGEKEY', "domain_name"): profile.domain_name
        },
        expression="set replication = :rp, domain_id = :d, user_profile_name = :upn, space_name = :s, efs_sys_id =:es, efs_uid = :eu, role_name =:rn",
        attributes={
            ":rp": True,
            ":rn": profile.role,
            ":d": domain_id,
            ":upn": profile.name,
            ":s": profile.space,
            ":es": profile.efs_sys_id,
            ":eu": profile.efs_uid
        },
        ret_val='ALL_NEW'
    )
    logger.debug(f"update table {users.table.name} respose: {response}")
    logger.info(f"append to table {users_hist.table.name}")
    users_hist.put_user(
        item={
            os.getenv('HASHKEY_HIST', 'profile_name'): profile.name + profile.space, #either one is empty string
            os.getenv('RANGEKEY_HIST', 'epoctime'): int(time.time() * 1000),
            "replication": True,
            "role_name": profile.role,
            "domain_id": domain_id,
            "domain_name": profile.domain_name,
            "user_profile_name": profile.name,
            "space_name": profile.space,
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
        type=str
    )
    parser.add_argument(
        "-region",
        "--region",
        dest="region",
        type=str
    )
    parser.add_argument(
        "-profile-name",
        "--profile-name",
        dest="profile_name",
        type=str
    )
    parser.add_argument(
        "-role-name",
        "--role-name",
        dest="role_name",
        type=str
    )
    args = parser.parse_args()
    event = {
        'detail-type': 'AWS API Call via CloudTrail',
        'source': 'aws.sagemaker',
        'region': args.region,
        'detail': {
            'eventSource': 'sagemaker.amazonaws.com',
            'eventName': 'CreateSpace',
            'awsRegion': args.region,
            'requestParameters': {
                'domainId': args.domain_id,
                #'userProfileName': args.profile_name,
                'spaceName': args.space_name,
                'userSettings': {
                    'executionRole': args.role_name
                }
            }
        }
    }
    os.environ['AWS_DEFAULT_REGION'] = args.region
    lambda_handler(event, {})


