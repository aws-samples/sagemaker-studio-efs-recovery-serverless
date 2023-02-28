import json
import string
import boto3
from typing import Mapping, List
import argparse
from botocore.exceptions import ClientError
import os
import logging
from common import profile as p

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_params(names: List[str], client) -> Mapping:
    try:
        response = client.get_parameters(
            Names=names
        )
    except ClientError as e:
        logger.error(
            f"Could not get parameters with names {names}: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
        raise
    return response


def start_execution(arn: string, input: string, client) -> Mapping:
    try:
        response = client.start_execution(
            stateMachineArn=arn,
            input=input
        )
    except ClientError as e:
        logger.error(
            f"Could not start state machine {arn}: {e.response['Error']['Code']}:{e.response['Error']['Message']}")
        raise
    return response


def lambda_handler(event, context):
    logger.info(f"change in table detected: {event}")
    if 'Records' not in event:
        logger.error(f"Expected key Records in input payload but didn't exist")
        raise ValueError(f"Invalid input: {event}")

    event = json.loads(json.dumps(event['Records'][0]))
    if (event['eventName'] != 'MODIFY'):
        logger.info(f"nothing to do. its not MODIFY event: {event['eventName']}")
        return

    account = boto3.client('sts').get_caller_identity().get('Account')
    region = event['awsRegion']
    domain_id = event['dynamodb']['NewImage']['domain_id'].get('S')
    profile_name = event['dynamodb']['NewImage'][os.getenv('HASHKEY', 'username')].get('S')
    role_name = event['dynamodb']['NewImage'][os.getenv('RANGEKEY', 'role_name')].get('S')
    target_efs = event['dynamodb']['NewImage']['efs_sys_id'].get('S')
    target_mount = event['dynamodb']['NewImage']['efs_uid'].get('S')

    source_efs = event['dynamodb']['OldImage']['efs_sys_id'].get('S')
    source_mount = event['dynamodb']['OldImage']['efs_uid'].get('S')

    profile = p.Profile(
        domain_id=domain_id,
        sm_client=boto3.client('sagemaker'),
        profile_name=profile_name,
        role_name=role_name
    )
    if profile.error:
        '''
        If DynamoDB Streams triggers Lambda function and Lambda function fails, 
        then the Lambda invocation will be retried with the same data until successful or expired by the event source.
        '''
        logging.warning(f"could not get user profile metadata. skip user {profile_name}")
        return

    logger.info(f"""Built profile: user {profile.name}\
    role_name {profile.role}\
    domain_id {profile.domain_id}\
    home_efs_id {profile.efs_sys_id}\
    efs_uid {profile.efs_uid}""")

    names = []
    names.append(('SOURCE_SECURITY_GROUP', os.getenv('SOURCE_SECURITY_GROUP')))
    names.append(('TARGET_SECURITY_GROUP', os.getenv('TARGET_SECURITY_GROUP')))
    names.append(('SUBNET1', os.getenv('SUBNET1')))
    names.append(('STEPFUNCTION', os.getenv('STEPFUNCTION')))

    names = ['SOURCE_SECURITY_GROUP', 'TARGET_SECURITY_GROUP', 'SUBNET1', 'STEPFUNCTION']
    params = {}
    for a in names:
        if not(os.getenv(a)):
            raise ValueError(f"invalid os env parameter. key {a} does not exist or value is empty")
        params[a] = os.getenv(a)

    options = {"Gid": 'NONE', "LogLevel": "TRANSFER", "OverwriteMode": "ALWAYS", "PosixPermissions": "NONE", "TransferMode": "CHANGED", "Uid": "NONE"}
    logger.debug(f"datasync task option setting: {options}")
    input = {
        "Options": options,
        "Log": {
            "CloudWatchLogGroupArn": f"arn:aws:logs:{region}:{account}:log-group:/aws/datasync:*"
        },
        "Source": {
            "DomainID": event['dynamodb']['OldImage']['domain_id'].get('S'),
            "UserProfileName": event['dynamodb']['OldImage'][os.getenv('HASHKEY', 'username')].get('S'),
            "EfsFilesystemArn": f"arn:aws:elasticfilesystem:{region}:{account}:file-system/{source_efs}",
            "HomeEfsFileSystemUid": source_mount,
            "SubnetArn": f"arn:aws:ec2:{region}:{account}:subnet/{params['SUBNET1']}",
            "SecurityGroupArns": [f"arn:aws:ec2:{region}:{account}:security-group/{sg}" for sg in params['SOURCE_SECURITY_GROUP'].split(",")
                                  if sg]
        },
        "Target": {
            "DomainID": event['dynamodb']['NewImage']['domain_id'].get('S'),
            "UserProfileName": profile_name,
            "EfsFilesystemArn": f"arn:aws:elasticfilesystem:{region}:{account}:file-system/{target_efs}",
            "HomeEfsFileSystemUid": target_mount,
            "SubnetArn": f"arn:aws:ec2:{region}:{account}:subnet/{params['SUBNET1']}",
            "SecurityGroupArns": [f"arn:aws:ec2:{region}:{account}:security-group/{sg}" for sg in params['TARGET_SECURITY_GROUP'].split(",")
                                  if sg]
        }}
    step_function_name = params['STEPFUNCTION'].rsplit(':')[-1]
    logger.info(f"invoke stepfunction {params['STEPFUNCTION'].rsplit(':')[-1]} with input {input}")
    response = start_execution(
        arn=f"arn:aws:states:{region}:{account}:stateMachine:{step_function_name}",
        input=json.dumps(input),
        client=boto3.client('stepfunctions')
    )
    logger.info("Done")
    return

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-domain-id",
        "--domain-id",
        dest="domain_id",
        type=str,
        default="d-ejqunbmsecvq"
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
        default='demo-myapp-dev-sagemaker-user1-role'
    )
    parser.add_argument(
        "-region",
        "--region",
        dest="region",
        type=str,
        default='us-east-2'
    )
    parser.add_argument(
        "-efs-sys-id",
        "--efs-sys-id",
        dest="efs_sys_id",
        type=str,
        default='fs-012047b432ec90e24'
    )
    args = parser.parse_args()
    event = {'Records': [{
        'eventName': 'MODIFY',
        'eventSource': 'aws:dynamodb',
        'awsRegion': args.region,
        'dynamodb': {
            'ApproximateCreationDateTime': 1675224256.0,
            'Keys': {
                'role_name': {'S': args.role_name},
                'user': {'S': args.profile_name}

            },
            'NewImage': {'domain_id': {'S': args.domain_id},
                         'role_name': {'S': args.role_name},
                         'efs_uid': {'S': 'fake-new-uid'},
                         'efs_sys_id': {'S': args.efs_sys_id},
                         'username': {'S': args.profile_name}},
            'OldImage': {'domain_id': {'S': args.domain_id},
                         'role_name': {'S': args.role_name},
                         'efs_uid': {'S': 'fake-old-uid'},
                         'efs_sys_id': {'S': 'fake-old-sys-id'},
                         'username': {'S': args.profile_name}},
            'StreamViewType': 'NEW_AND_OLD_IMAGES'
        }
    }]}
    os.environ['AWS_DEFAULT_REGION'] = args.region
    os.environ['SOURCE_SECURITY_GROUP'] = 'fake-source-security-group'
    os.environ['TARGET_SECURITY_GROUP'] = 'fake-target-security-group'
    os.environ['SUBNET1'] = 'fake-subnet1'
    os.environ['STEPFUNCTION'] = 'fake-function'
    os.environ['HASHKEY'] = 'username'
    lambda_handler(event, {})
