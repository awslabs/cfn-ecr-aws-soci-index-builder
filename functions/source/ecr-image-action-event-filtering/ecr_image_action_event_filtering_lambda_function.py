# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import os
import fnmatch, re
import boto3

lambda_client = boto3.client('lambda')

def lambda_handler(event, context):
    """
    Handler - Meant to be invoked by EventBridge for ECR Image Action events.

    sample event data from EventBridge:
        {
            "version": "0",
            "id": "999cccaa-eaaa-0000-1111-123456789012",
            "detail-type": "ECR Image Action",
            "source": "aws.ecr",
            "account": "123456789012",
            "time": "2016-12-16T20:43:05Z",
            "region": "us-east-1",
            "resources": [],
            "detail": {
                "result": "SUCCESS",
                "repository-name": "repository_name",
                "image-digest": "sha256:978f5f8049d3d0de30a7fc3892aafdfb323451bf682170d99154230ddefbe91e",
                "action-type": "PUSH",
                "artifact-media-type": "application/vnd.docker.container.image.v1+json",
                "manifest-media-type": "application/vnd.docker.distribution.manifest.v2+json",
                "image-tag": "hello-world"
            }
        }
    """

    validation_error = validate_event(event)
    if validation_error != None:
        return validation_error

    repository_name = event['detail']['repository-name']
    image_digest = event['detail']['image-digest']
    image_tag = event['detail'].get('image-tag',"")
    artifact_media_type = event['detail'].get('artifact-media-type',"")

    try:
        soci_index_version = os.environ['soci_index_version']
    except:
        soci_index_version = "V2"

    # V2 index builder ignores image with no tag
    if soci_index_version == "V2" and image_tag == "":
        return log_and_generate_response(200, f'Skipping image "{repository_name} {artifact_media_type} {image_digest}" as it has no tag')

    # For SOCI V2, we create a new image index and tag it with a "-soci" suffix tag.
    # This repo tag generates a new PUSH event and will retrigger the soci index builder.
    # To prevent this recursive processing, skip image tags that end with "-soci"
    if image_tag.endswith("-soci"):
        return log_and_generate_response(200, f'Skipping image "{repository_name}:{image_tag}" as it has the "-soci" suffix')

    try:
        soci_repository_image_tag_filters = os.environ['soci_repository_image_tag_filters'].split(",")
    except:
        return log_and_generate_response(400, "Invalid environment variable; expected a comma separated list")

    for soci_repository_image_tag_filter in soci_repository_image_tag_filters:
        soci_repository_image_tag_filter_regex_pattern = fnmatch.translate(soci_repository_image_tag_filter)
        regex_matcher = re.compile(soci_repository_image_tag_filter_regex_pattern)

        if regex_matcher.fullmatch(f'{repository_name}:{image_tag}'):
            log_to_cloudwatch("Invoking SOCI index generator Lambda function")

            soci_index_generator_lambda_arn = os.environ['soci_index_generator_lambda_arn']

            response = lambda_client.invoke(
                FunctionName = soci_index_generator_lambda_arn,
                InvocationType = 'Event',
                Payload = json.dumps(event)
            )

            lambda_status_code = response['ResponseMetadata']['HTTPStatusCode']
            lambda_request_id = response['ResponseMetadata']['RequestId']

            if lambda_status_code == 202:
                return log_and_generate_response(200, f'Successfully invoked SOCI index generator Lambda function because the given event contained the image "{repository_name}:{image_tag}" with digest "{image_digest}" which matched SOCI repository image tag filter "{soci_repository_image_tag_filter}". Lambda request id: "{lambda_request_id}"')
            else:
                return log_and_generate_response(500, f'Failed to invoke SOCI index generator Lambda function. Lambda status code: "{lambda_status_code}". Lambda request id: "{lambda_request_id}"')

    return log_and_generate_response(200, f'The given event contained the image "{repository_name}:{image_tag}" with digest "{image_digest}" which did not match any SOCI repository image tag filters')

def validate_event(event):
    if event.get('source') != "aws.ecr":
        return log_and_generate_response(400, "The event's 'source' must be 'aws.ecr'")
    if event.get('account') == None:
        return log_and_generate_response(400, "The event's 'account' must not be empty")
    if event.get('detail-type') != "ECR Image Action":
        return log_and_generate_response(400, "The event's 'detail-type' must be 'ECR Image Action'")
    eventDetail = event.get('detail')
    if eventDetail == None:
        return log_and_generate_response(400, "The event's 'detail' must not be empty")
    if type(eventDetail) is not dict:
        return log_and_generate_response(400, "The event's 'detail' must be a JSON object literal")
    if eventDetail.get('action-type') != "PUSH":
        return log_and_generate_response(400, "The event's 'detail.action-type' must be 'PUSH")
    if eventDetail.get('result') != "SUCCESS":
        return log_and_generate_response(400, "The event's 'detail.result' must be 'SUCCESS'")
    if eventDetail.get('repository-name') == None:
        return log_and_generate_response(400, "The event's 'detail.repository-name' must not be empty")
    if eventDetail.get('image-digest') == None:
        return log_and_generate_response(400, "The event's 'detail.image-digest' must not be empty")

    if re.match('[0-9]{12}', event['account']) == None:
        return log_and_generate_response(400, "The event's 'account' must be a valid AWS account ID")

    if re.match('(?:[a-z0-9]+(?:[._-][a-z0-9]+)*/)*[a-z0-9]+(?:[._-][a-z0-9]+)*', eventDetail['repository-name']) == None:
        return log_and_generate_response(400, "The event's 'detail.repository-name' must be a valid repository name")

    if re.match('[A-Za-z][A-Za-z0-9]*(?:[-_+.][A-Za-z][A-Za-z0-9]*)*[:][A-Fa-f0-9]{32,}', eventDetail['image-digest']) == None:
        return log_and_generate_response(400, "The event's 'detail.image-digest' must be a valid image digest")

    # missing tag is OK
    if eventDetail.get('image-tag') != None and eventDetail['image-tag'] != "":
        if re.match('[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}', eventDetail['image-tag']) == None:
            return log_and_generate_response(400, "The event's 'detail.image-tag' must be empty or a valid image tag")

    return None

def log_and_generate_response(status_code, message):
    log_to_cloudwatch(message)

    return {
        'statusCode': status_code,
        'body': message
    }

def log_to_cloudwatch(message):
    print(message)