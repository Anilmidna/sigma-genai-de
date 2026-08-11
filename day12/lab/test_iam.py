import boto3

iam = boto3.client('iam')
policy = iam.get_role_policy(RoleName='sigma-lambda-role', PolicyName='sigma-platform-policy')
print(policy['PolicyDocument'])
