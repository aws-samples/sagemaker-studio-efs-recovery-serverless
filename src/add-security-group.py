import boto3
import argparse
import os
import logging
import string
from botocore.exceptions import ClientError
from common import cfnresponse

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_target_mount_id(efs_id: string, client):
    mount_id = ''
    try:
        response = client.describe_mount_targets(FileSystemId=efs_id)
        mount_id = response['MountTargets'][0]['MountTargetId']
    except ClientError as e:
        logger.error(
            f"Could not get target mount id for efs {efs_id}: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
        return
    return mount_id

def get_security_group(mount_id: string, client):
    try:
        response = client.describe_mount_target_security_groups(MountTargetId=mount_id)
    except ClientError as e:
        logger.error(
            f"Could not get security group id using target mount id {mount_id}: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
        return
    return response['SecurityGroups'][0]

def update_security_groups(source: string, target: string, client):
    try:
        ip_permission = []
        for sg in source.split(","):
            if not(sg):
                continue
            inbound = {'IpProtocol': 'tcp',
                 'FromPort': 2049,
                 'ToPort': 2049,
                 'UserIdGroupPairs': [{ 'GroupId': sg }]
            }
            ip_permission.append(inbound)
        response = client.authorize_security_group_ingress(
            GroupId=target,
            IpPermissions=ip_permission
        )
        logger.info(f'Ingress Successfully Set: {response}')
    except ClientError as e:
        logger.error(
            f"Could not update target security group {target} with source {source}: {e}")
        return

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
        efs = boto3.client('efs')
        mount_id = get_target_mount_id(event.get('ResourceProperties')['EFS_ID'], efs)
        logger.info(f"obtained target_mount_id {mount_id}")
        security_groups = get_security_group(mount_id, efs)
        logger.info(f"obtained security groups {security_groups} from target_mount_id {mount_id}")
        ec2 = boto3.client('ec2')
        response = update_security_groups(
            source=event.get('ResourceProperties')['SECUITY_GROUPS'],
            target=security_groups,
            client=ec2
        )
        if event.get("LOCAL_DEBUG"):
            print(f"Done. received Response: {response}")
            return
        cfnresponse.send(
                event,
                context,
                cfnresponse.SUCCESS,
                {},
                physicalResourceId=physicalResourceId
        )
    except Exception as e:
        if event.get("LOCAL_DEBUG"):
            print(f"Error: {e}")
            return
        cfnresponse.send(
            event,
            context,
            cfnresponse.FAILED,
            {},
            physicalResourceId=physicalResourceId,
            reason=str(e)
        )
        return
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
        type=str,
        default='us-east-2'
    )
    parser.add_argument(
        "-efs-id",
        "--efs-id",
        dest="efs_id",
        type=str
    )
    parser.add_argument(
        "-security-groups",
        "--security-groups",
        dest="security_groups",
        type=str
    )
    args = parser.parse_args()
    args.is_debug = True
    event = {
        "PhysicalResourceId": "fake",
        "LOCAL_DEBUG": args.is_debug,
        "ResourceProperties": {
        "EFS_ID": args.efs_id,
        "SECUITY_GROUPS": args.security_groups,
    }}
    os.environ['AWS_DEFAULT_REGION'] = args.region
    lambda_handler(event, {})