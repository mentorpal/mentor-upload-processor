/*
This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved. 
Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu

The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
*/
module "pipeline" {
  source                  = "git@github.com:mentorpal/terraform-modules//modules/gitflow_cicd_pipeline?ref=tags/v1.6.1"
  codestar_connection_arn = var.codestar_connection_arn
  project_name            = "mentor-upload-processor"
  github_repo_name        = "mentor-upload-processor"
  github_org              = "mentorpal"
  github_branch_dev       = "main"
  github_branch_release   = "release"

  enable_e2e_tests            = true
  enable_status_notifications = true
  build_buildspec             = "cicd/buildspec.yml"
  deploy_dev_buildspec        = "cicd/deployspec-dev.yml"
  deploy_qa_buildspec         = "cicd/deployspec-qa.yml"
  deploy_prod_buildspec       = "cicd/deployspec-prod.yml"

  # reference: https://github.com/cloudposse/terraform-aws-codebuild#inputs
  build_image  = "aws/codebuild/standard:5.0"
  deploy_image = "aws/codebuild/standard:5.0"
  # https://docs.aws.amazon.com/codebuild/latest/userguide/build-env-ref-compute-types.html
  build_compute_type       = "BUILD_GENERAL1_SMALL"
  deploys_compute_type     = "BUILD_GENERAL1_SMALL"
  build_cache_type         = "LOCAL"
  deploy_cache_type        = "LOCAL"
  build_local_cache_modes  = ["LOCAL_DOCKER_LAYER_CACHE", "LOCAL_SOURCE_CACHE"]
  deploy_local_cache_modes = ["LOCAL_DOCKER_LAYER_CACHE", "LOCAL_SOURCE_CACHE"]
  builds_privileged_mode   = true
  deploys_privileged_mode  = true

  tags = {
    Source = "terraform"
  }

  providers = {
    aws = aws.us_east_1
  }
}
