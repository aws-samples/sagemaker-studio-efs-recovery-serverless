# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import time
import boto3
import logging
from common import cfnresponse

sm_client = boto3.client('sagemaker')

def delete_apps_domain(domain_id):
    logging.info(f'Start deleting apps for domain id: {domain_id}')

    try:
        sm_client.describe_domain(DomainId=domain_id)
    except:
        logging.info(f'Cannot retrieve {domain_id}')
        return

    for p in sm_client.get_paginator('list_apps').paginate(DomainIdEquals=domain_id):
        for a in p['Apps']:
            if a['AppType'] == 'KernelGateway' and a['Status'] != 'Deleted':

                sm_client.delete_app(DomainId=a['DomainId'],
                                     UserProfileName=a['UserProfileName'],
                                     AppType=a['AppType'],
                                     AppName=a['AppName'])

    apps = 1
    while apps:
        apps = 0
        for p in sm_client.get_paginator('list_apps').paginate(DomainIdEquals=domain_id):
            apps += len(
                [a['AppName'] for a in p['Apps'] if a['AppType'] == 'KernelGateway' and a['Status'] != 'Deleted'])
        logging.info(f'Number of active KernelGateway apps: {str(apps)}')
        time.sleep(5)

    logging.info(f'KernelGateway apps for domain {domain_id} deleted')
    return

def delete_apps_user(domain_id, user_profile_name):
    logging.info(f'Start deleting apps for user: {user_profile_name}')

    try:
        sm_client.describe_user_profile(DomainId=domain_id, UserProfileName=user_profile_name)
    except:
        logging.info(f'Cannot retrieve {user_profile_name}')
        return

    for p in sm_client.get_paginator('list_apps').paginate(DomainIdEquals=domain_id, UserProfileNameEquals=user_profile_name):
        for a in p['Apps']:
            if a['AppType'] == 'KernelGateway' and a['Status'] != 'Deleted':

                sm_client.delete_app(DomainId=a['DomainId'],
                                     UserProfileName=a['UserProfileName'],
                                     AppType=a['AppType'],
                                     AppName=a['AppName'])

    apps = 1
    while apps:
        apps = 0
        for p in sm_client.get_paginator('list_apps').paginate(DomainIdEquals=domain_id, UserProfileNameEquals=user_profile_name):
            apps += len(
                [a['AppName'] for a in p['Apps'] if a['AppType'] == 'KernelGateway' and a['Status'] != 'Deleted'])
        logging.info(f'Number of active KernelGateway apps: {str(apps)}')
        time.sleep(5)

    logging.info(f'KernelGateway apps for user {user_profile_name} deleted')
    return

def delete_apps_space(domain_id, space_name):
    logging.info(f'Start deleting apps for space: {space_name}')

    try:
        sm_client.describe_space(DomainId=domain_id, SpaceName=space_name)
    except:
        logging.info(f'Cannot retrieve {space_name}')
        return

    for p in sm_client.get_paginator('list_apps').paginate(DomainIdEquals=domain_id, SpaceNameEquals=space_name):
        for a in p['Apps']:
            if a['AppType'] == 'KernelGateway' and a['Status'] != 'Deleted':

                sm_client.delete_app(DomainId=a['DomainId'],
                                     SpaceName=a['SpaceName'],
                                     AppType=a['AppType'],
                                     AppName=a['AppName'])

    apps = 1
    while apps:
        apps = 0
        for p in sm_client.get_paginator('list_apps').paginate(DomainIdEquals=domain_id, SpaceNameEquals=space_name):
            apps += len(
                [a['AppName'] for a in p['Apps'] if a['AppType'] == 'KernelGateway' and a['Status'] != 'Deleted'])
        logging.info(f'Number of active KernelGateway apps: {str(apps)}')
        time.sleep(5)

    logging.info(f'KernelGateway apps for space {space_name} deleted')
    return

def lambda_handler(event, context):
    logging.info(f'REQUEST RECEIVED: {event}')
    response_data = {}
    physicalResourceId = event.get('PhysicalResourceId')

    try:
        if event['RequestType'] in ['Create', 'Update']:
            physicalResourceId = event.get('ResourceProperties')['DomainId']

        elif event['RequestType'] == 'Delete':
            domain_id = event.get('ResourceProperties').get('DomainId')
            user_profile_name = event.get('ResourceProperties').get('UserProfileName')
            space_name = event.get('ResourceProperties').get('SpaceName')
            if user_profile_name:
                delete_apps_user(domain_id, user_profile_name)
            elif space_name:
                delete_apps_space(domain_id, space_name)
            else:
                delete_apps_domain(domain_id)
        cfnresponse.send(event, context, cfnresponse.SUCCESS, response_data, physicalResourceId=physicalResourceId)

    except Exception as exception:
        logging.error(exception)
        cfnresponse.send(event, context, cfnresponse.FAILED, {}, physicalResourceId=physicalResourceId,
                         reason=str(exception))