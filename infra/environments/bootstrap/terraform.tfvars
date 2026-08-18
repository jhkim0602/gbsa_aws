# Committed: none of these are secrets, and the deploy role's trust policy is only
# reviewable if the repository and branch it trusts are in version control.
state_bucket      = "iep-terraform-state-868216907365"
github_repository = "jhkim0602/gbsa_aws"

# The numeric form this account's OIDC tokens actually carry. Not a duplicate of the line
# above: see the `github_immutable_repository` variable for why both are trusted, and for the
# command that reads these ids back if the repository is ever recreated.
github_immutable_repository = "jhkim0602@104820436/gbsa_aws@1337672097"
