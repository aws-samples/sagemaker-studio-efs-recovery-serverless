#!/bin/bash
set -eo pipefail

display_usage() {
	echo  "Usage: $(basename $0) [-n <stack_name>] [-v <vpc_id>] [-s <subnet_id>] [-b <s3_buket>] [-r <aws_region>] [-d]"
	echo "Options:"
	echo "-n: specify stack name"
	echo "-v: specify your vpc id"
	echo "-s: specify subnet"
	echo "-b: specify s3 bucket name to store artifacts"
	echo "-r: specify aws region"
	echo "-d: whether to skip a creation of a new SageMaker Studio Domain (default: no)"
	}
if [ -z "$domain" ]; then directory="directory"; fi
while getopts 'n:v:s:b:r:dh' OPTION; do
	case "${OPTION}" in
		n)
			NAME=${OPTARG}
			;;
		v)
			VPC=${OPTARG}
			;;
		s)
			SUBNET=${OPTARG}
			;;
	  b)
			ARTIFACT_BUCKET=${OPTARG}
			;;
	  r)
			AWS_REGION=${OPTARG}
			;;
	  d)
			DOMAIN_SKIP=$((DOMAIN_SKIP+1))
			;;
		h)
			display_usage
			exit 0
			;;
		\?)
			display_usage
			exit 1
			;;
	esac
done
shift "$((OPTIND-1))"
DOMAIN_SKIP=${DOMAIN_SKIP:-0}
echo "#####################################################"
echo "Build a boto 3 as a Lambda layer"
echo "#####################################################"
LIB_DIR=tmp/python
LAMBDA_LAYER_NAME="boto3-layer"
mkdir -p $LIB_DIR
pip3 install boto3==1.26.59 -t $LIB_DIR
cd tmp
zip -r $LAMBDA_LAYER_NAME.zip .
rm -r ../$LIB_DIR
cd ..
echo "#####################################################"
echo "Built and Deploy"
echo "#####################################################"
sam build
if [[ "$DOMAIN_SKIP" -eq 0 ]]; then
  sam deploy \
        --region ${AWS_REGION} \
        --stack-name ${NAME} \
        --s3-bucket ${ARTIFACT_BUCKET} \
        --capabilities CAPABILITY_AUTO_EXPAND CAPABILITY_NAMED_IAM  \
        --parameter-overrides ParameterKey=VpcId,ParameterValue=${VPC} ParameterKey=SubnetId1,ParameterValue=${SUBNET}
  echo "[INFO] Deployment completed"
else
  echo '[Warning] Skip Sagemaker Domain Deployment'
  sam deploy \
        --region ${AWS_REGION} \
        --stack-name ${NAME} \
        --s3-bucket ${ARTIFACT_BUCKET} \
        --capabilities CAPABILITY_AUTO_EXPAND CAPABILITY_NAMED_IAM  \
        --parameter-overrides ParameterKey=VpcId,ParameterValue=${VPC} ParameterKey=SubnetId1,ParameterValue=${SUBNET} ParameterKey=MODE,ParameterValue=SEED ParameterKey=DDBInitialSeed,ParameterValue=ENABLED
fi
