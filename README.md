# Amazon SageMaker Studio Domain Backup and Recovery Using Event-Driven Serverless Architecture
***
This pattern shows how to back up and recover users' work in Amazon SageMaker Studio Domain when user profiles are deleted and recreated. Currently, SageMaker Domain does not support mounting custom or additional Amazon EFS volumes based on the [Developer Guide](https://docs.aws.amazon.com/sagemaker/latest/dg/studio-tasks-manage-storage.html), which means that studio users will lose access to the data stored in their profile directory if the Studio Domain and Studio UserProfile are deleted. Losing access to removed user directories may decrease productivity of Data Scientists if backup and recovery solutions are unavailable. To solve this problem, we provide a solution to supplement [the SageMaker Studio Admin Best Practices Whitepaper](https://docs.aws.amazon.com/whitepapers/latest/sagemaker-studio-admin-best-practices/appendix.html#studio-domain-backup-and-recovery). In addition, we demonstrate an event-driven application as one approach to automate the backup and recovery process.

**Important**: this application uses various AWS services and there are costs associated with these services after the Free Tier usage - please see the [AWS Pricing page](https://aws.amazon.com/pricing/?aws-products-pricing.sort-by=item.additionalFields.productNameLowercase&aws-products-pricing.sort-order=asc&awsf.Free%20Tier%20Type=*all&awsf.tech-category=*all) for details. You are responsible for any AWS costs incurred. No warranty is implied in this example.

## Architecture
***
In case, the users and domain are accidentally deleted, [the Amazon EFS volume is detached but not deleted](https://docs.aws.amazon.com/sagemaker/latest/dg/gs-studio-delete-domain.html). A possible scenario is that we may want to revert the deletion by recreating a new domain and new user profiles. If the same users are being onboarded again, they may wish to access the files from their respective workspace in the detached volume. The following diagram illustrates the high-level workflow of Studio Domain backup and recovery with an event-driven architecture.

![architecture](backup_sagemaker_studio_efs_recovery_serverless/images/architecture.png)

The event-driven app includes the following steps:
1.	Amazon CloudWatch Events Rule uses AWS CloudTrail to track the CreateUserProfile API call, trigger the rule and invoke the AWS Lambda Function.
2.	The Lambda Function update the user table and append item in the history table in Amazon DynamoDB. 
3.	DynamoDB Streams is enabled on the user table, and the Lambda Function is set as a trigger and synchronously invoked when new stream records are available.
4.	Another Lambda Function trigger the process to restore the user files using the User Files Restore Tools in the diagram, which is described below. 

The backup and recovery workflow includes the following steps:
5.	The backup and recovery workflow consists of the AWS Step Functions, which is integrated with other AWS services including AWS DataSync, to orchestrate the recovery of the user files from the detached private home directory to a new directory in Studio Domain EFS. With The Step Functions Workflow Studio, the workflow can be implemented with a no-code, such as in this case, or a low-code for a more customized solution. The Step Function is invoked when the user profile creation event is detected by the event-driven app.
6.	For each user, the Step Functions execute the DataSync task to copy all files from their respective home directories in the detached volume to the new directory. The image below is the actual graph of the Step Functions.
![Step Functions Graph](backup_sagemaker_studio_efs_recovery_serverless/images/stepfunctions_graph.png)
7. When the users open their Studio, all of the files from respective directories in detached volume will be available to themselves.

## Tools and Services
***
- [Amazon SageMaker Studio](https://aws.amazon.com/sagemaker/studio/) - Amazon SageMaker Studio is an integrated development environment (IDE) that provides a single web-based visual interface that supports end-to-end model development and deployment.
- [AWS Step Functions](https://aws.amazon.com/step-functions/) - AWS Step Functions is a visual workflow service that helps developers use AWS services to build distributed applications, automate processes, orchestrate microservices, and create data and machine learning (ML) pipelines.
- [AWS DataSync](https://aws.amazon.com/datasync/) - AWS DataSync is a secure, online service that automates and accelerates moving data between on premises and AWS Storage services. DataSync can copy data between Amazon EFS file systems, NFS shares, SMB shares, HDFS, Amazon S3 buckets, and more.
- [AWS Lambda](https://aws.amazon.com/lambda/) - AWS Lambda is a serverless compute service that lets you run code without provisioning or managing servers, creating workload-aware cluster scaling logic, maintaining event integrations, or managing runtimes.
- [Amazon Simple Queue Service](https://aws.amazon.com/sqs/) - Amazon Simple Queue Service (SQS) is a fully managed message queuing service that enables you to decouple and scale microservices, distributed systems, and serverless applications.
- [Amazon DynamoDB](https://aws.amazon.com/dynamodb/) - Amazon DynamoDB is a fully managed, serverless, key-value NoSQL database designed to run high-performance applications at any scale.
- [AWS CloudFormation](https://aws.amazon.com/cloudformation/) - AWS CloudFormation lets you model, provision, and manage AWS and third-party resources by treating infrastructure as code.
- [Amazon CloudWatch](https://aws.amazon.com/cloudwatch/) - Amazon CloudWatch collects and visualizes real-time logs, metrics, and event data in automated dashboards to streamline your infrastructure and application maintenance.
- [AWS Systems Manager](https://aws.amazon.com/systems-manager/) - Parameter Store, a capability of AWS Systems Manager, provides secure, hierarchical storage for configuration data management and secrets management.
- [AWS CloudTrail](https://aws.amazon.com/cloudtrail/) - AWS CloudTrail monitors and records account activity across your AWS infrastructure, giving you control over storage, analysis, and remediation actions.
- [AWS IAM](https://aws.amazon.com/iam/) - With IAM, you can specify who or what can access services and resources in AWS, centrally manage fine-grained permissions, and analyze access to refine permissions across AWS.
## Requirements
***
- [Create an AWS account](https://portal.aws.amazon.com/billing/signup?redirect_url=https%3A%2F%2Faws.amazon.com%2Fregistration-confirmation#/start/email) if you do not already have one and log in. The IAM user that you use must have sufficient permissions to make necessary AWS service calls and manage AWS resources.
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) installed and configured
- [Setup AWS Credentials](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html)
- [Git Installed](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
- Python 3.9
- You need to use the existing [Amazon Virtual Private Cloud (VPC)](https://aws.amazon.com/vpc/) and [Amazon Simple Storage Service (S3)](https://aws.amazon.com/s3/) Bucket to follow the deployment step.
## Limitations
***
- The solution currently does not support cross-account backup and recovery.
- For services availability based on region, please refer to [AWS Regional Services List](https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/).
## Deployment Instructions
***
1. Create a new directory, navigate to that directory in a terminal and clone the GitHub repository:
   ```bash
   git clone https://gitlab.aws.dev/kennysat/sagemaker-studio-efs-restore.git
   ```
2. Change directory to the solution directory:
   ```bash
   cd sagemaker-studio-efs-restore
   ```
3. Display deployment script usage
   ```bash
   bash deploy.sh -h
   Usage: deploy.sh [-n <stack_name>] [-v <vpc_id>] [-s <subnet_id>] [-b <s3_buket>] [-r <aws_region>] [-d]
   Options:
   -n: specify stack name
   -v: specify your vpc id
   -s: specify subnet
   -b: specify s3 bucket name to store artifacts
   -r: specify aws region
   -d: whether to skip a creation of a new SageMaker Studio Domain (default: no)
   ```
4. To deploy the application including the new SageMaker Domain, you need to specify `vpc_id`,`subnet_id`,`s3_bucket_name`,`stack_name`, and `aws_region`:
   ```bash
   bash deploy.sh -v <vpc_id> -s <subnet_id> -b <s3_bucket_name> -n <stack_name> -r <aws_region>
   ```
5. To deploy the application using the existing SageMaker Domain, you need to specify `vpc_id`,`subnet_id`,`s3_bucket_name`,`stack_name`, `aws_region` and `d=yes.`
   ```bash
   bash deploy.sh -v <vpc_id> -s <subnet_id> -b <s3_bucket_name> -n <stack_name> -r <aws_region> -d yes
   ```
## How It Works
***
| Templates | Description |
| --- | --- |
| `ssm.yaml` | Bootstraps deployment configs in Parameter Store |
| `stepfunction.yaml` | Create a Step Functions to copy files between SageMaker Domain EFS |
| `event-app.yaml` | Create an event-driven app consisting of CloudWatch Event Rule, DynamoDB Streams, and Lambda  |
| `sagemaker-studio-domain.yaml` | Create a SageMaker Studio Domain |
| `sagemaker-studio-user.yaml` | Create a SageMaker Studio UserProfile |

| Scripts | Description |
| --- | --- |
| `seed-table.py` | This script is only used if DDBInitialSeed is set to [ENABLE](backup_sagemaker_studio_efs_recovery_serverless/template.yaml). It lists the current Studio UserProfiles and seeds the DynamoDB tables with the user metadata |
| `event-processor.py` | Process the `CreateUserProfile Event` from CloudWatch Event Rule, update the user table, and put an item in the history table |
| `ddb-stream-processor.py` | Process the `Update Event` from the DynamoDB stream and invokes the Step Functions with the Studio EFS recovery input  |
| `add-security-group.py` | This script is invoked when [SageMaker Domain CloudFormation](backup_sagemaker_studio_efs_recovery_serverless/Infrastructure/Templates/sagemaker-studio-domain.yaml) is deployed. The script updates the Security Groups for Home EFS. For DataSync Task to copy files between EFS, we need to update the Security Groups according to [the Documentation](https://docs.aws.amazon.com/datasync/latest/userguide/create-efs-location.html). Therefore, the script will update the Security Group of the specified EFS by allowing inbounds from the DataSync Security Group as a source using Port 2049.

## Testing - Scenario I (Create a New SageMaker Studio Domain)
***
Scenario I deploys all stacks, including the backup and recovery module, event-driven app, and SageMaker Domain and UserProfile. The assumption is that there are no active SageMaker Studio resources in the environment.
1. To deploy the application including new SageMaker Domain:
   ```bash
   bash deploy.sh -v <vpc_id> -s <subnet_id> -b <s3_bucket_name> -n <stack_name> -r <aws_region>
   ```
2. Check the deployment status.
   1. In [AWS CloudFormation Console](https://console.aws.amazon.com/cloudformation/home), ensure the following stacks are in **CREATE_COMPLETE** status:
      1. `<stack_name>-DemoBootstrap-*`
      2. `<stack_name>-StepFunction-*`
      3. `<stack_name>-EventApp-*`
      4. `<stack_name>-StudioDomain-*`
      5. `<stack_name>-StudioUser1-*`
      6. `<stack_name>-StudioUser2-*`
      ![CloudFomration Console](backup_sagemaker_studio_efs_recovery_serverless/images/stack-create-complete.png)
   2. If the deployment failed in any of the stacks, check the error and resolve the issues. Then, proceed to the next step only if the problems are resolved.
   3. In [Amazon DynamoDB Console](https://console.aws.amazon.com/dynamodbv2/home), select **Tables** and confirm that `studioUser` and `studioUserHistory` tables are created.
      1. From **Table**, select `studioUser` and select **Explore table items** to confirm that items for `user1` and `user2` are populated in the table.
3. Open Studio
   1. Open [the Amazon SageMaker console](https://console.aws.amazon.com/sagemaker/)
   2. On the left navigation pane, choose **Studio**
   3. On the right side **Get Started** dropdown, select `user1` and click **Open Studio** to open the studio for the user. **Note**: It may take 10-15 minutes for the studio to [launch for the first time](https://aws.amazon.com/premiumsupport/knowledge-center/sagemaker-studio-launch-issues/).
   4. Choose Amazon SageMaker Studio at the top left of the Studio interface. 
   5. On the **File** menu, choose **Terminal** to launch a new terminal within Studio.
   6. Run the following command in the terminal to create a file for testing.
        ```bash
        echo "i don't want to lose access to this file" > user1.txt
        ```
4. Delete Studio User `user1` by removing the nested stack from the parent. Comment out the below code blocks in [template.yaml](backup_sagemaker_studio_efs_recovery_serverless/template.yaml) and save the file:
    ```bash
     StudioUser1:
       Type: AWS::Serverless::Application
       DependsOn: StudioDomain
       Properties:
         Location: Infrastructure/Templates/sagemaker-studio-user.yaml
         Parameters:
           StudioUserProfileName: !Ref StudioUserProfileName1
           UID: !Ref UID
           Env: !Ref Env
           AppName: !Ref AppName
    ```
   We need to deploy the stack by running the command below to let the deletion of the stack to take an effect.
    ```bash
   bash deploy.sh -v <vpc_id> -s <subnet_id> -b <s3_bucket_name> -n <stack_name> -r <aws_region>
   ```
5. Recreate Studio User `user1` by adding back the nested stack back to the parent. Uncomment the above code block, save the file, and then deploy:
    ```bash
   bash deploy.sh -v <vpc_id> -s <subnet_id> -b <s3_bucket_name> -n <stack_name> -r <aws_region>
   ```
6. After the successful deployment, check the result of Studio User file recovery 
   1. In [AWS CloudFormation Console](https://console.aws.amazon.com/cloudformation/home), select the stack `<stack_name>-stepfunction-stack`.
   2. In the stack, select **Physical ID** of `StepFunction` under **Resources** section
   3. Select the most recent execution and confirm the execution status in **Graph view**. It should look like this:
   ![architecture](backup_sagemaker_studio_efs_recovery_serverless/images/stepfunctions_graph_success.png)
7. If you have completed step 2, open the Studio for `user1` and confirm that the `user1.txt` file is copied to the newly created directory.
8. In [AWS DataSync Console](https://console.aws.amazon.com/datasync/home), select the most recent Task ID. Select **History** and the most recent **Execution ID**. This is another way to inspect the configurations and the execution status of the DataSync task. 
   ![DataSync Console](backup_sagemaker_studio_efs_recovery_serverless/images/data-sync.png)
9. If you wish, you can delete and recreate the Studio Domain and UserProfiles for additional testing.
10. End of the steps

## Testing - Scenario II (Use the Existing Studio Domain)
***
Scenario II assumes you want to use the existing SageMaker Domain and UserProfile in the environment.
1. To deploy the application using the existing SageMaker Domain:
   ```bash
   bash deploy.sh -v <vpc_id> -s <subnet_id> -b <s3_bucket_name> -n <stack_name> -r <aws_region> -d yes
   ```
2. Check the deployment status.
   1. In [AWS CloudFormation Console](https://console.aws.amazon.com/cloudformation/home), ensure the following stacks are in `CREATE_COMPLETE` status:
      1. `<stack_name>-DemoBootstrap-*`
      2. `<stack_name>-StepFunction-*`
      3. `<stack_name>-EventApp-*`
   2. If the deployment failed in any of the stacks, check the error and resolve the issues. Then, proceed to the next step only if the problems are resolved.
3. Verify the initial data seed has been completed. In [Amazon DynamoDB Console](https://console.aws.amazon.com/dynamodbv2/home), select **Tables** and confirm that the `user` and `history` Tables are created.
   1. From **Table**, select the `studioUser,` and select **Explore table items** to confirm that items for the existing Studio are populated in the table. Then, proceed to the next step only if the seed has been completed successfully.
   2. If the tables aren't populated, check the CloudWatch Log of the corresponding Lambda Function by following the steps below.
      1. In [AWS CloudFormation Console](https://console.aws.amazon.com/cloudformation/home), select the stack `<stack_name>-EventApp-*`.
      2. In the stack, select **Physical ID** of `DDBSeedLambda` under **Resources** section
      3. Select **View CloudWatch logs** under **Monitor** section, and then check the logs from the most recent execution to troubleshoot.
4. Update the EFS Security Group.
   1. Get the `SecurityGroupId.` We will use the Security Group created in [the CloudFormation Template](backup_sagemaker_studio_efs_recovery_serverless/Infrastructure/Templates/ssm.yaml), which allows `ALL Traffic` in the Outbound Connection as a source and target for DataSync. To run the following command, you need to specify `aws_region.`
      ```bash
      echo "SecurityGroupId:" $(aws ssm get-parameter --name /network/vpc/sagemaker/securitygroups --region <aws_region> --query 'Parameter.Value')
      ```
   2. Get the `HomeEfsFileSystemId`, which is the ID of the Studio Home EFS. To run the following command, you need to specify `aws_region` and `domain_id.`
      ```bash
      echo "HomeEfsFileSystemId:" $(aws sagemaker describe-domain --domain-id <domain_id> --region <aws_region> --query 'HomeEfsFileSystemId')
      ```
   3. Finally, update the EFS Security Group by allowing inbounds from the Security Group shared with the DataSync task using Port 2049. To run the following command, you need to specify `aws_region`, `HomeEfsFileSystemId`, and `SecurityGroupId.`
      ```bash
      python3 src/add-security-group.py --efs-id <HomeEfsFileSystemId> --security-groups <SecurityGroupId> --region <aws_region>
      ```
5. Delete and recreate Studio User of your choice using the exact same UserProfile name and the execution role, and then confirm the execution status of the Step Function and recovery of Studio UserProfile directory by following the steps 6-7 in Scenario I testing.
6. End of the steps

## Testing - Scenario III (Backup and Recovery Workflow without automation)
***
Scenario III assumes you want to test the backup and recovery workflow without a full automation using the event-driven app.
   1. Comment out the below code blocks in [template.yaml](backup_sagemaker_studio_efs_recovery_serverless/template.yaml) and save the file:
      ```bash
       EventApp:
       Type: AWS::Serverless::Application
       DependsOn: StepFunction
       Properties:
         Location: Infrastructure/Templates/event-app.yaml
         Parameters:
           DDBInitialSeed: !Ref DDBInitialSeed
           UID: !Ref UID
           Env: !Ref Env
           AppName: !Ref AppName
      ```
   2. run the deployment script as shown below.
      ```bash
      bash deploy.sh -v <vpc_id> -s <subnet_id> -b <s3_bucket_name> -n <stack_name> -r <aws_region>
      ```
2. In [AWS CloudFormation Console](https://console.aws.amazon.com/cloudformation/home), ensure the following stacks are in `CREATE_COMPLETE` status:
      1. `<stack_name>-DemoBootstrap-*`
      2. `<stack_name>-StepFunction-*`
      4. `<stack_name>-StudioDomain-*`
      5. `<stack_name>-StudioUser1-*`
      6. `<stack_name>-StudioUser2-*`
3. If the deployment failed in any stacks, check the error and resolve the issues. Then, proceed to the next step only if the problems are resolved.
4. Create some test file by following step 2 of Scenario I. 
5. Identify the required recovery source information. 

   1. Get the `domain_id`. To run the following command, you need to specify `aws_region.`
   ```bash
   echo "domain_id:" $(aws sagemaker list-domains --region <aws_region> --query 'Domains[0].DomainId')
   ```
   2. Get the `HomeEfsFileSystemId`, which is the ID of the EFS. To run the following command, you need to specify `aws_region` and `domain_id` from the previous step.
   ```bash
   echo "HomeEfsFileSystemId:" $(aws sagemaker describe-domain --domain-id <domain_id> --region <aws_region> --query 'HomeEfsFileSystemId')
   ```
   3. Get the `HomeEfsFileSystemUid`, which is the ID of the user's profile in the EFS volume. To run the following command, you need to specify `aws_region` and `domain_id.`
   ```bash
   echo "HomeEfsFileSystemUid: $(aws sagemaker describe-user-profile --domain-id <domain_id> --user-profile-name user1 --region <aws_region> --query 'HomeEfsFileSystemUid')
   ```
6. Delete the UserProfile `user1` by executing the command below. To run the following command, you need to specify `stack_name.`
   ```bash
   aws cloudformation delete-stack --stack-name <stack_name>-studio-user1-stack
   ```
7. Recreate the UserProfile `user1` using the same script with the same parameter values.
   ```bash
   bash deploy.sh -v <vpc_id> -s <subnet_id> -b <s3_bucket_name> -n <stack_name> -r <aws_region>
   ```
8. Get the target `HomeEfsFileSystemUid`. The UID increments by `5` starting from `200000` by design, so we assume the Studio user can be assigned with a different UID. To run the following command, you need to specify `aws_region` and `domain_id.`
   ```bash
   echo "HomeEfsFileSystemUid: $(aws sagemaker describe-user-profile --domain-id <domain_id> --user-profile-name user1 --region <aws_region> --query 'HomeEfsFileSystemUid')   
   ```
9. For DataSync Task to copy files between EFS, we need to update the Security Groups according to [the Documentation](https://docs.aws.amazon.com/datasync/latest/userguide/create-efs-location.html). Therefore, for the demonstration, we will use the existing subnet and security group shared with SageMaker Studio in order to complete the set-up for the DataSync task.
      1. Get the `SubnetId`. To run the following command, you need to specify `domain_id` and `aws_region.`
      ```bash
      echo "SubnetId:" $(aws sagemaker describe-domain --domain-id <domain_id> --region <aws_region> --query 'SubnetIds[0]')    
      ```
      2. Get the `SecurityGroupId`. We will use the Security Group created in [the CloudFormation Template](backup_sagemaker_studio_efs_recovery_serverless/Infrastructure/Templates/ssm.yaml). To run the following command, you need to specify `aws_region.`
      ```bash
      echo "SecurityGroupId:" $(aws ssm get-parameter --name /network/vpc/sagemaker/securitygroups --region <aws_region> --query 'Parameter.Value')
      ```
      3. Finally, update the EFS Security Group by allowing inbounds from the Security Group shared with the DataSync task using Port 2049. To run the following command, you need to specify `aws_region`, `HomeEfsFileSystemId` and `SecurityGroupId.` We just need to run this once with the same `HomeEfsFileSystemId` since we have not recreated the SageMaker Domain.
      ```bash
      python3 src/add-security-group.py --efs-id <HomeEfsFileSystemId> --security-groups <Security_Group_ID> --region <aws_region>   
      ```
10. In [AWS CloudFormation Console](https://console.aws.amazon.com/cloudformation/home), select the stack `<stack_name>-StepFunction-*`.
    1. In the stack, select **Physical ID** of StepFunction under **Resources** section
    2. Select **Start Execution**
    3. Update the input json below (Specify `aws_region`, `AccountId`, `HomeEfsFileSystemId`, `HomeEfsFileSystemUid`, `SubnetId`, and `SecurityGroupId`). You can use the same value for `Source` and `Target` except `HomeEfsFileSystemUid.`
      ```bash
      {
         "Options":{
            "Gid":"NONE",
            "LogLevel":"TRANSFER",
            "OverwriteMode":"ALWAYS",
            "PosixPermissions":"NONE",
            "TransferMode":"CHANGED",
            "Uid":"NONE"
         },
         "Log":{
            "CloudWatchLogGroupArn":"arn:aws:logs:<aws_region>:<AccountId>:log-group:/aws/datasync:*"
         },
         "Source":{
            "EfsFilesystemArn":"arn:aws:elasticfilesystem:<aws_region>:<AccountId>:file-system/<HomeEfsFileSystemId>",
            "HomeEfsFileSystemUid":"<source-HomeEfsFileSystemUid>",
            "SubnetArn":"arn:aws:ec2:<aws_region>:<AccountId>:subnet/<SubnetId>",
            "SecurityGroupArns":[
               "arn:aws:ec2:<aws_region>:<AccountId>:security-group/<SecurityGroupId>"
            ]
         },
         "Target":{
            "EfsFilesystemArn":"arn:aws:elasticfilesystem:<aws_region>:<AccountId>:file-system/<HomeEfsFileSystemId>",
            "HomeEfsFileSystemUid":"<target-HomeEfsFileSystemUid>",
            "SubnetArn":"arn:aws:ec2:<aws_region>:<AccountId>:subnet/<SubnetId>",
            "SecurityGroupArns":[
               "arn:aws:ec2:<aws_region>:<AccountId>:security-group/<SecurityGroupId>"
            ]
         }
      }
      ```
11. Manually Invoke the Step Functions by providing the **input**:
    1. Select **Start Execution** after ensuring that you provided the updated Json input from the previous step.
    2. You can check the execution status in **Graph view**. It should look like the one from step 5 of Scenario I.

## Cleanup
***
Run the following commands by specifying the `aws_region` and the parent `stack_name.`
```bash
sam delete --region <aws_region> --no-prompts --stack-name <stack_name> 
```
**Note**: Please manually delete the `SageMakerSecurityGroup` after 30 min or so. Deletion of the [Elastic Network Interface (ENI)](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-eni.html) can makes the stack be in `DELETE_IN_PROGRESS` for some time, so we intentionally set the `SageMakerSecurityGroup` to be retained. Also, you need to [disassociate that security group from the security group managed by SagerMaker before you can delete it](https://aws.amazon.com/premiumsupport/knowledge-center/troubleshoot-delete-vpc-sg/#:~:text=Short%20description,the%20running%20or%20stopped%20state).

## Related Links
***
- [Studio domain backup and recovery](https://docs.aws.amazon.com/whitepapers/latest/sagemaker-studio-admin-best-practices/appendix.html#studio-domain-backup-and-recovery)
- [CloudWatch Events Rule](https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/Create-CloudWatch-Events-CloudTrail-Rule.html)
- [DynamoDB Streams and AWS Lambda triggers](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.Lambda.html)
- [cfn-response module](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-lambda-function-code-cfnresponsemodule.html)
- [DataSync Options](https://docs.aws.amazon.com/datasync/latest/userguide/API_Options.html)
- [Create EFS Location](https://docs.aws.amazon.com/datasync/latest/userguide/create-efs-location.html)
## License
***
This library is licensed under the MIT-0 License. See the LICENSE file.
