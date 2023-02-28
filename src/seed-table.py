import boto3
import argparse
import os
import logging
import time
from botocore.exceptions import ClientError
import string
from typing import Mapping, List
from common import cfnresponse

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_domain_id(client)->string:
    domain_id = ''
    try:
        response = client.list_domains()
        # assumption is less or equal to 1 domain per account per region
        if len(response['Domains']) == 0:
            return domain_id
        domain_id = response['Domains'][0]['DomainId']
    except ClientError as e:
        logger.error(
            f"Could not get studio domain id: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
        return domain_id
    return domain_id

def get_domain_metadata(domain_id: string, client)->Mapping[str, str]:
    try:
        response = client.describe_domain(
            DomainId=domain_id
        )
    except ClientError as e:
        logger.error(
            f"Could not get studio domain {domain_id} metatdat: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
        return
    return response

def list_profiles(domain_id: string, client)-> List[str]:
    users = []
    try:
        paginator = client.get_paginator('list_user_profiles')
        page_iterator = paginator.paginate(DomainIdEquals=domain_id,PaginationConfig={'MaxItems': 500})
        for page in page_iterator:
            for u in page['UserProfiles']:
                users. append(u['UserProfileName'])
    except ClientError as e:
        logger.error(
            f"Could not list profiles with domain id {domain_id}: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
        return
    return users

def get_user_metadata(domain_id: string, profile_name: string, client):
    try:
        response = client.describe_user_profile(
            DomainId=domain_id,
            UserProfileName=profile_name
        )
    except ClientError as e:
        logger.error(
            f"Could not describe user {profile_name}: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
        return
    return response

def get_all_users_metadata(domain_id: string, efs_id: string, profile_names: List[str], client):
    data = []
    for name in profile_names:
        response = get_user_metadata(domain_id, name, client)
        user_meta = {
            "DomainId": domain_id,
            "UserProfileName": name,
            "HomeEfsFileSystemId": efs_id,
            "HomeEfsFileSystemUid": "",
            "ExecutionRole": ""
        }
        if response:
            user_meta["HomeEfsFileSystemUid"] = response['HomeEfsFileSystemUid']
            user_meta["ExecutionRole"] = response['UserSettings']["ExecutionRole"].rsplit("role/")[-1]
            data.append(user_meta)
        else:
            continue
    return data

def lambda_handler(event, context):
    logger.info(f"received event: {event}")
    physicalResourceId = event.get('PhysicalResourceId')
    if event.get("RequestType") and event.get("RequestType") == 'Delete':
        cfnresponse.send(
            event,
            context,
            cfnresponse.SUCCESS,
            {},
            physicalResourceId=physicalResourceId
        )
    try:
        sagemaker = boto3.client('sagemaker')
        domain_id = get_domain_id(sagemaker) #event.get('ResourceProperties')['DOMAIN_ID']
        domain_metadata = get_domain_metadata(domain_id, sagemaker)
        efs_id = domain_metadata['HomeEfsFileSystemId'] #event.get('ResourceProperties')['EFS_ID']
        users = list_profiles(domain_id, sagemaker)
        logger.info(f"domain {domain_id} has users {users}")
        data = get_all_users_metadata(domain_id, efs_id, users, sagemaker)
        dynamodb = boto3.resource('dynamodb')
        user_table = os.getenv('USERTABLE', 'studioUser')
        user_hist_table = os.getenv('HISTORYTABLE', 'studioUserHIstory')
        logger.info(f"update table {user_table} with data: {data}")
        table = dynamodb.Table(user_table)
        with table.batch_writer() as batch:
            # put in a batch
            for record in data:
                item = {
                    os.getenv('HASHKEY_HIST', 'username'): record["UserProfileName"],
                    "role_name": record["ExecutionRole"],
                    "domain_id": record["DomainId"],
                    "efs_sys_id": record["HomeEfsFileSystemId"],
                    "efs_uid": record["HomeEfsFileSystemUid"]
                }
                batch.put_item(Item=item)
        logger.info(f"update history table {user_hist_table}")
        hist_table = dynamodb.Table(user_hist_table)
        with hist_table.batch_writer() as batch:
            # put in a batch
            for record in data:
                item = {
                    os.getenv('HASHKEY_HIST', 'username'): record["UserProfileName"],
                    os.getenv('RANGEKEY_HIST', 'epoctime'): int(time.time() * 1000),
                    "role_name": record["ExecutionRole"],
                    "domain_id": record["DomainId"],
                    "efs_sys_id": record["HomeEfsFileSystemId"],
                    "efs_uid": record["HomeEfsFileSystemUid"]
                }
                batch.put_item(Item=item)
        cfnresponse.send(
            event,
            context,
            cfnresponse.SUCCESS,
            {},
            physicalResourceId=physicalResourceId
        )
    except Exception as e:
        cfnresponse.send(
            event,
            context,
            cfnresponse.FAILED,
            {},
            physicalResourceId=physicalResourceId,
            reason=str(e)
        )
        return
    return

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # parser.add_argument(
    #     "-domain-id",
    #     "--domain-id",
    #     dest="domain_id",
    #     type=str,
    #     default="d-7lcx8wozqren"
    # )
    parser.add_argument(
        "-region",
        "--region",
        dest="region",
        type=str,
        default='us-east-2'
    )
    # parser.add_argument(
    #     "-efs-id",
    #     "--efs-id",
    #     dest="efs_id",
    #     type=str,
    #     default='fs-04bc5fa34400736eb'
    # )

    args = parser.parse_args()
    event = {
        "ResourceProperties": {
        # "DOMAIN_ID": args.domain_id,
        # "EFS_ID": args.efs_id
        }
    }
    os.environ['AWS_DEFAULT_REGION'] = args.region
    lambda_handler(event, {})
