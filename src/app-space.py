import time
import boto3
import logging
from common import cfnresponse
import json

sm_client = boto3.client('sagemaker')

def create_apps_space(domain_id, space_name):
    logging.info(f'Start creating apps for space: {space_name}')

    try:
        sm_client.describe_space(DomainId=domain_id, SpaceName=space_name)
    except:
        logging.info(f'Cannot retrieve {space_name}')
        return

    try:
        ## re-creating jupyter server with the same name fails as of 3/14/23. use timestamp to a unique name
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d-%I-%M-%S")
        app_name = f'default-{timestamp}'
        app_type = 'JupyterServer'
        response = sm_client.create_app(
            DomainId=domain_id,
            SpaceName=space_name,
            AppType=app_type,
            AppName=app_name,
            ResourceSpec={
                'InstanceType': 'system'
            }
        )
        is_created = False
        sum = 0
        wait_sec = 60
        max_wait = 600
        while not is_created:
            response = sm_client.describe_app(
                DomainId=domain_id,
                SpaceName=space_name,
                AppName=app_name,
                AppType=app_type
            )
            time.sleep(wait_sec)
            sum += wait_sec
            if response['Status'] == 'InService':
                is_created = True
            elif response['Status'] == 'Failed':
                logging.error(f'create app {space_name} for space failed: {response}')
                return
            elif sum >= max_wait:
                logging.error(f'create app {space_name} in pending state. proceeding: {response}')
                return
    except:
        logging.info(f'Could not create app for {space_name}')
        return
    logging.info(f'app for space {space_name} created')
    return response

def delete_apps_space(domain_id, space_name):
    logging.info(f'Start deleting apps for space: {space_name}')

    try:
        sm_client.describe_space(DomainId=domain_id, SpaceName=space_name)
    except:
        logging.info(f'Cannot retrieve {space_name}')
        return
    for p in sm_client.get_paginator('list_apps').paginate(DomainIdEquals=domain_id, SpaceNameEquals=space_name):
        for a in p['Apps']:
            if a['AppType'] in ['KernelGateway', 'JupyterServer'] and a['Status'] != 'Deleted':

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
    domain_id = event.get('ResourceProperties').get('DomainId')
    space_name = event.get('ResourceProperties').get('SpaceName')
    try:
        if event['RequestType'] == 'Create':
            response_data = create_apps_space(
                domain_id=domain_id,
                space_name=space_name
            )
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, physicalResourceId=physicalResourceId)
        elif event['RequestType'] == 'Delete':
            delete_apps_space(
                domain_id=domain_id,
                space_name=space_name
            )
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, physicalResourceId=physicalResourceId)
    except Exception as exception:
        logging.error(exception)
        cfnresponse.send(event, context, cfnresponse.FAILED, {}, physicalResourceId=physicalResourceId,
                         reason=str(exception))