/*
This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved. 
Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu

The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
*/
module "pipeline" {
  source                  = "git@github.com:mentorpal/terraform-modules//modules/trunk_cicd_pipeline?ref=tags/v1.2.1"
  codestar_connection_arn = var.codestar_connection_arn
  project_name            = "mentor-upload-processor"
  github_repo_name        = "mentor-upload-processor"
  build_cache_type        = "NO_CACHE"
  deploy_cache_type       = "NO_CACHE"
  build_compute_type      = "BUILD_GENERAL1_SMALL"
  deploys_compute_type    = "BUILD_GENERAL1_SMALL"

  build_buildspec             = "cicd/buildspec.yml"
  deploy_staging_buildspec    = "cicd/deployspec_staging.yml"
  deploy_prod_buildspec       = "cicd/deployspec_prod.yml"
  deploys_privileged_mode     = true
  export_pipeline_info        = true
  enable_status_notifications = true

  tags = {
    Source = "terraform"
  }

  providers = {
    aws = aws.us_east_1
  }
}
