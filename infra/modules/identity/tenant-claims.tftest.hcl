# The two attributes the API resolves a tenant from, and the domainless sender shape.
#
# `AwsCognitoPrincipalProvider.get_company_principal` reads `custom:company_id` and
# `custom:company_user_id` out of a GetUser response and raises PrincipalNotFoundError if
# either is missing. A pool declared without them therefore logs a user in and then rejects
# every authenticated request -- and Cognito allows no custom attribute to be added to a
# live pool, so the only remedy after an apply is to replace the pool and its users. That
# makes this worth a test rather than a review comment.

mock_provider "aws" {}

variables {
  name = "iep-probe"
}

run "pool_carries_the_tenant_claims_the_api_resolves_a_principal_from" {
  command = apply

  variables {
    sender_address    = "interviews@example.test"
    console_base_urls = ["http://localhost:5173"]
  }

  assert {
    condition = length([
      for entry in aws_cognito_user_pool.company.schema :
      entry
      if contains(["company_id", "company_user_id"], entry.name)
      && entry.attribute_data_type == "String"
      && entry.mutable == false
    ]) == 2
    error_message = "the pool must declare immutable company_id and company_user_id attributes"
  }

  # GetUser returns only attributes the app client may read, and the principal lookup reads
  # them from exactly that response, so an omitted read grant is the same defect one layer
  # down.
  assert {
    condition = alltrue([
      for name in ["custom:company_id", "custom:company_user_id"] :
      contains(aws_cognito_user_pool_client.company.read_attributes, name)
    ])
    error_message = "the app client must be allowed to read both tenant attributes"
  }

  # The scope GetUser itself requires, which is one layer further down again: the response
  # can carry both attributes and the call still fail. Without it Cognito answers
  # `NotAuthorizedException: Access Token does not have required scopes`, so a hosted login
  # mints a token that cannot read its own user and every request is a 401 -- indistinguishable
  # from a wrong password from the outside. The console requests the same string; a scope
  # allowed here but not requested there yields the identical failure.
  assert {
    condition     = contains(aws_cognito_user_pool_client.company.allowed_oauth_scopes, "aws.cognito.signin.user.admin")
    error_message = "the console client must allow the scope GetUser requires"
  }

  # A token holder that could rewrite its own company_id would move itself into another
  # tenant, which is the one boundary the whole platform rests on.
  assert {
    condition = alltrue([
      for name in ["custom:company_id", "custom:company_user_id"] :
      !contains(aws_cognito_user_pool_client.company.write_attributes, name)
    ])
    error_message = "no client may write a tenant attribute"
  }

  # An address identity has no zone, so Easy DKIM cannot be requested for it -- SES rejects
  # the request outright.
  #
  # Indexed because the SES resources are counted on whether mail is configured at all; see
  # the third run below for the case that count exists for.
  assert {
    condition     = length(aws_sesv2_email_identity.company[0].dkim_signing_attributes) == 0
    error_message = "an address identity must not request Easy DKIM"
  }

  assert {
    condition     = aws_sesv2_email_identity.company[0].email_identity == "interviews@example.test"
    error_message = "sender_address must become the verified identity"
  }

  # The From in the IAM condition and the From the application is told to use come from one
  # local, because a send whose From is outside the grant fails with an AccessDenied that
  # names neither value.
  assert {
    condition     = output.from_address == "interviews@example.test"
    error_message = "from_address must be the verified address itself, not noreply@ a domain"
  }

  assert {
    condition     = strcontains(aws_iam_role_policy.email_sender[0].policy, "interviews@example.test")
    error_message = "the send grant must be conditioned on the address actually used"
  }

  assert {
    condition = (
      contains(aws_cognito_user_pool_client.company.callback_urls, "http://localhost:5173/auth/callback")
      && length(aws_cognito_user_pool_client.company.callback_urls) == 1
    )
    error_message = "the workstation origin must be allowed to complete a login"
  }
}

run "domain_environment_keeps_dkim_and_the_noreply_sender" {
  command = apply

  variables {
    company_domain = "company.example.com"
  }

  assert {
    condition     = length(aws_sesv2_email_identity.company[0].dkim_signing_attributes) == 1
    error_message = "a domain identity must sign with Easy DKIM"
  }

  assert {
    condition     = output.from_address == "noreply@company.example.com"
    error_message = "a domain environment sends from noreply@ its own domain"
  }

  assert {
    condition = (
      contains(aws_cognito_user_pool_client.company.callback_urls, "https://company.example.com/auth/callback")
      && length(aws_cognito_user_pool_client.company.callback_urls) == 1
    )
    error_message = "company_domain must contribute its own console origin"
  }
}

# The committed dev shape: no domain to verify and no mailbox chosen yet.
#
# This module used to fail while evaluating its own locals here -- `coalesce` on two nulls,
# and `noreply@${null}` in a string template -- so the module could not be planned at all
# with the values dev is applied with, and the precondition written to explain the case never
# got to run. What is asserted below is that the absence is total rather than partial: an
# identity with a null name, or a send grant whose `ses:FromAddress` condition is null, would
# apply cleanly and read in a review as though sending had been set up.
run "no_domain_and_no_mailbox_creates_no_mail_resources_at_all" {
  command = apply

  variables {
    company_domain    = null
    sender_address    = null
    console_base_urls = ["http://localhost:5173"]
  }

  assert {
    condition = alltrue([
      length(aws_sesv2_email_identity.company) == 0,
      length(aws_sesv2_configuration_set.transactional) == 0,
      length(aws_iam_role_policy.email_sender) == 0,
    ])
    error_message = "an environment that cannot send mail must create no identity, no configuration set and no send grant"
  }

  # Null, not "noreply@null": the application root refuses to plan on a null and would send
  # the string to the task definition, where the API starts and fails at the first invitation.
  assert {
    condition = alltrue([
      output.from_address == null,
      output.email_identity == null,
    ])
    error_message = "from_address and email_identity must be null rather than a placeholder"
  }

  # The pool is not conditional on mail. The console logs in against it from a workstation
  # long before a mailbox is confirmed, and its custom attributes can never be added later.
  assert {
    condition = length([
      for name in output.pool_schema_names :
      name if contains(["company_id", "company_user_id"], name)
    ]) == 2
    error_message = "the user pool and its tenant attributes must exist without mail"
  }
}

# How CI gets a token, and the limits on the client that mints it.
#
# The console client allows `code` only, which requires a human at the hosted login UI, so the
# browser suite had no way to authenticate against a deployed environment -- it was sending
# `Bearer local-company-token`, which only the local FakePrincipalProvider resolves. This
# client closes that gap, and the assertions are mostly about how narrow it has to be.
run "the_e2e_client_authenticates_without_a_browser_and_grants_nothing_to_one" {
  command = apply

  variables {
    sender_address    = "interviews@example.test"
    console_base_urls = ["http://localhost:5173"]
    create_e2e_client = true
  }

  # The admin variant, which requires signed IAM credentials. `ALLOW_USER_PASSWORD_AUTH` would
  # let anyone holding the client id exchange a password from a browser.
  assert {
    condition = alltrue([
      contains(aws_cognito_user_pool_client.e2e[0].explicit_auth_flows, "ALLOW_ADMIN_USER_PASSWORD_AUTH"),
      !contains(aws_cognito_user_pool_client.e2e[0].explicit_auth_flows, "ALLOW_USER_PASSWORD_AUTH"),
      !contains(aws_cognito_user_pool_client.e2e[0].explicit_auth_flows, "ALLOW_USER_SRP_AUTH"),
    ])
    error_message = "the test client must use the admin password flow and no browser-reachable flow"
  }

  # No secret to leak into a log, and no hosted-login participation: without callback URLs the
  # client cannot complete an authorization-code flow even if its id became public.
  assert {
    condition = alltrue([
      aws_cognito_user_pool_client.e2e[0].generate_secret == false,
      length(aws_cognito_user_pool_client.e2e[0].callback_urls) == 0,
      aws_cognito_user_pool_client.e2e[0].allowed_oauth_flows_user_pool_client == false,
    ])
    error_message = "the test client must not be usable from a hosted login"
  }

  # The token it mints is resolved by the same GetUser lookup, which fails if either tenant
  # attribute is missing from the response -- and the response carries only what the calling
  # client may read. A client that can authenticate but not read these produces a token that
  # is rejected on every request, which reads as a broken suite rather than a missing grant.
  assert {
    condition = alltrue([
      for name in ["custom:company_id", "custom:company_user_id"] :
      contains(aws_cognito_user_pool_client.e2e[0].read_attributes, name)
    ])
    error_message = "the test client must be allowed to read both tenant attributes"
  }

  assert {
    condition = alltrue([
      for name in ["custom:company_id", "custom:company_user_id"] :
      !contains(aws_cognito_user_pool_client.e2e[0].write_attributes, name)
    ])
    error_message = "no client may write a tenant attribute"
  }

  # Two clients, not one repurposed: the console must keep the code flow it logs humans in
  # with, and must not acquire the password flow.
  assert {
    condition = alltrue([
      aws_cognito_user_pool_client.company.allowed_oauth_flows_user_pool_client == true,
      !contains(coalesce(aws_cognito_user_pool_client.company.explicit_auth_flows, []), "ALLOW_ADMIN_USER_PASSWORD_AUTH"),
    ])
    error_message = "the console client must keep the code flow and never gain the password flow"
  }

  assert {
    condition     = output.e2e_client_id == aws_cognito_user_pool_client.e2e[0].id
    error_message = "the client id must be published for the pipeline to read"
  }
}

# What prod applies. A client that exchanges a password for a token has no business existing
# beside real applicant data, and `count = 0` has to mean the output is null rather than an
# id that fails later at AdminInitiateAuth.
run "an_environment_without_the_test_client_publishes_no_id" {
  command = apply

  variables {
    company_domain    = "company.example.com"
    create_e2e_client = false
  }

  assert {
    condition = alltrue([
      length(aws_cognito_user_pool_client.e2e) == 0,
      output.e2e_client_id == null,
    ])
    error_message = "without the switch there must be no test client and no id"
  }
}
