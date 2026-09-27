# AWS SOCI Index Builder

This AWS solution automates the generation of Seekable OCI (SOCI) index artifacts and stores them in Amazon ECR. It provides an easy way for customers to try SOCI technology to lazily load container images.

## Overview

The AWS SOCI Index Builder solution consists of the following components:

1. **EventBridge Rule**: Triggers when an image is pushed to ECR
2. **ECR Image Action Event Filtering Lambda**: Filters ECR image push events based on repository and tag patterns
3. **SOCI Index Generator Lambda**: Generates SOCI index artifacts for the image and pushes them back to ECR

## SOCI Index Versions

The solution supports two versions of SOCI index:

- **V1**: The original SOCI index format based on the OCI referrers API
- **V2**: An improved format that attaches the SOCI index to an image directly

## Configuration Parameters

### SociRepositoryImageTagFilters

Comma-separated list of SOCI repository image tag filters. Each filter is a repository name followed by a colon, ":" and followed by a tag. Both repository names and tags may contain wildcards denoted by an asterisk, "*".

Examples:
- `prod*:latest`: Matches all images tagged with "latest" that are pushed to any repositories that start with "prod"
- `dev:*`: Matches all images pushed to the "dev" repository
- `*:*`: Matches all images pushed to all repositories in your private registry

### SociIndexVersion

The version of SOCI index to generate:
- `V1`: Original SOCI Index format
- `V2`: Latest SOCI Index format (Recommended)

### Taskcat Configuration

The solution uses taskcat for testing CloudFormation deployments across multiple regions. The `.taskcat.yml` file configurable options:

- **Regions**: List of AWS regions where you want to deploy the stack
- **SociRepositoryImageTagFilters**: Filter pattern for ECR repositories and image tags

Example configuration:
```yaml
regions:
  - us-east-1
  - us-west-2
  - eu-west-1

parameters:
  SociRepositoryImageTagFilters: "*:*"
```

## How It Works

1. When an image is pushed to ECR, an EventBridge rule triggers the ECR Image Action Event Filtering Lambda
2. The Lambda checks if the image matches the configured filters
3. If there's a match, it invokes the SOCI Index Generator Lambda
4. The SOCI Index Generator Lambda:
   - Pulls the image from ECR
   - Generates SOCI index artifacts using the specified version (V1 or V2)
   - Pushes the SOCI index artifacts back to ECR

## Simple manual deployment
1. Run `./build-cfn.sh`. This will build all required artifacts into the directory `./upload`
2. Upload the contents of `./upload` to an S3 bucket
3. Copy the Object URL of the uploaded `SociIndexBuilder.yml` template
4. Create a new CloudFormation Stack with the Object URL of the uploaded template
5. Test: When the Stack is created, push an image to your Elastic Container Registry. The ECR Console page should list your SOCI index. You can also take a look at the created Cloud Watch log stream to verify.
