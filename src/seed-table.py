import boto3
import os
import logging
import time
from botocore.exceptions import ClientError
import string
from typing import Mapping, List
from common import cfnresponse

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_domain_ids(client)->List:
    domain_ids = []
    try:
        response = client.list_domains()
        if len(response['Domains']) == 0:
            return None
        for domain in response['Domains']:
            domain_ids.append(domain['DomainId'])
    except ClientError as e:
        logger.error(
            f"Could not get studio domain id: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
        return domain_ids
    return domain_ids

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

def list_spaces(domain_id: string, client)-> List[str]:
    users = []
    try:
        paginator = client.get_paginator('list_spaces')
        page_iterator = paginator.paginate(DomainIdEquals=domain_id,PaginationConfig={'MaxItems': 500})
        for page in page_iterator:
            for s in page['Spaces']:
                users. append(s['SpaceName'])
    except ClientError as e:
        logger.error(
            f"Could not list spaces with domain id {domain_id}: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
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

def get_space_metadata(domain_id: string, space_name: string, client):
    try:
        response = client.describe_space(
            DomainId=domain_id,
            SpaceName=space_name
        )
    except ClientError as e:
        logger.error(
            f"Could not describe space {space_name}: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
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

def get_all_spaces_metadata(domain_id: string, efs_id: string, space_names: List[str], client):
    data = []
    for name in space_names:
        response = get_space_metadata(domain_id, name, client)
        space_meta = {
            "DomainId": domain_id,
            "SpaceName": name,
            "HomeEfsFileSystemId": efs_id,
            "HomeEfsFileSystemUid": "",
            "ExecutionRole": ""
        }
        if response:
            space_meta["HomeEfsFileSystemUid"] = response['HomeEfsFileSystemUid']
            data.append(space_meta)
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
        domain_ids = get_domain_ids(sagemaker) #event.get('ResourceProperties')['DOMAIN_ID']
        dynamodb = boto3.resource('dynamodb')
        user_table = os.getenv('USERTABLE', 'studioUser')
        user_hist_table = os.getenv('HISTORYTABLE', 'studioUserHIstory')
        hist_table = dynamodb.Table(user_hist_table)
        table = dynamodb.Table(user_table)
        for domain_id in domain_ids:
            domain_metadata = get_domain_metadata(domain_id, sagemaker)
            efs_id = domain_metadata['HomeEfsFileSystemId'] #event.get('ResourceProperties')['EFS_ID']
            domain_name = domain_metadata['DomainName']
            users = list_profiles(domain_id, sagemaker)
            logger.info(f"domain {domain_name} {domain_id} has users {users}")
            spaces = list_spaces(domain_id, sagemaker)
            logger.info(f"domain {domain_name} {domain_id} has spaces {spaces}")
            data = get_all_users_metadata(domain_id, efs_id, users, sagemaker)
            data += get_all_spaces_metadata(domain_id, efs_id, spaces, sagemaker)
            logger.info(f"update table {user_table} with data: {data}")
            with table.batch_writer() as batch:
                # put in a batch
                for record in data:
                    item = {
                        os.getenv('HASHKEY_HIST'): record.get("UserProfileName", "")+record.get("SpaceName", ""), #either UserProfileName or SpaceName is empty string
                        "replication": True,
                        "role_name": record.get("ExecutionRole"),
                        "user_profile_name": record.get("UserProfileName"),
                        "space_name": record.get("SpaceName"),
                        "domain_id": record.get("DomainId"),
                        "domain_name": domain_name,
                        "efs_sys_id": record.get("HomeEfsFileSystemId"),
                        "efs_uid": record.get("HomeEfsFileSystemUid")
                    }
                    batch.put_item(Item=item)
            logger.info(f"update history table {user_hist_table}")
            with hist_table.batch_writer() as batch:
                # put in a batch
                for record in data:
                    item = {
                        os.getenv('HASHKEY_HIST'): record.get("UserProfileName", "")+record.get("SpaceName", ""), #either UserProfileName or SpaceName is empty string
                        os.getenv('RANGEKEY_HIST'): int(time.time() * 1000),
                        "replication": True,
                        "role_name": record.get("ExecutionRole"),
                        "user_profile_name": record.get("UserProfileName"),
                        "space_name": record.get("SpaceName"),
                        "domain_id": record.get("DomainId"),
                        "domain_name": domain_name,
                        "efs_sys_id": record.get("HomeEfsFileSystemId"),
                        "efs_uid": record.get("HomeEfsFileSystemUid")
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

