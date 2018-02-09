Feature: Creating, Getting, Patching and Deleting a project
  Creates a project, gets it, patches it then deletes it.
  TODO: Add DNS check that does not depend on data in the database

  Scenario: Create project
    Given I am authenticated as "admin"
    Given I set the body to:
      """
      {
        ""name": "integration-test-project",
        ""description": "Test project for integration tests.",
        ""enabled": "True""
      }
      """
    When I POST to "/projects/"
    Then the response code should be 201
    Then the response body should contain "name" that is "integration-test-project"
    Then the response body should contain "description" that is "Test project for integration tests."
    Then the response body should contain "enabled"
    Then the response body should contain "groups_link"
#    Then DNS Zone "integration-test-project" should exist

    
  Scenario: Assert I cannot create another project with the same name
    Given I am authenticated as "admin"
    Given I set the body to:
      """
      {
        ""name": "integration-test-project",
        ""description": "Test project for integration tests.",
        ""enabled": "True""
      }
      """
    When I POST to "/projects/"
    Then the response code should be 400


  Scenario: Getting a project
    Given I am authenticated as "admin"
    When I GET from "/projects/" where "name" is "integration-test-project"
    Then the response code should be 200
    Then the response body should contain "name" that is "integration-test-project"
    Then the response body should contain "description" that is "Test project for integration tests."
    Then the response body should contain "enabled"


  Scenario: Verifying auto created project groups
    Given I am authenticated as "admin"
    When I GET from "/user_management/groups/project/"
    Then the response code should be 200
    Then the response body should contain a list
    Then the response body should contain a list item where "name" is "integration-test-project-project_administrators"
    Then the response body should contain a list item where "name" is "integration-test-project-project_spectators"


  Scenario: Patching a project
    Given I am authenticated as "admin"
    Given I add param "name" with value "integration-test-project-patched" to body
    When I PATCH "/projects/" where "name" is "integration-test-project"
    Then the response code should be 200
    Then the response body should contain "name" that is "integration-test-project-patched"
#    Then DNS Zone "integration-test-project" should not exist
#    Then DNS Zone "integration-test-project-patched" should exist


  Scenario: Deleting a project
    Given I am authenticated as "admin"
    When I DELETE "/projects/" where "name" is "integration-test-project-patched"
    Then the response code should be 204
#    Then DNS Zone "integration-test-project-patched" should not exist
